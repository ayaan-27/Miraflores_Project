from __future__ import annotations

from datetime import datetime, timezone
import json
import operator
import re
import sqlite3
from typing import Annotated, TypedDict
from uuid import uuid4

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, interrupt

from .controls import evaluate, validate_reply
from .data import read_pdf
from .tools import make_tools


def now():
    return datetime.now(timezone.utc).isoformat()


def event(stage, title, data=None):
    return {"stage": stage, "title": title, "data": data or {}, "at": now()}


class State(TypedDict, total=False):
    account_code: str
    account: dict
    round: int
    calls: int
    observations: list
    tool_sources: dict
    action: dict
    analysis: dict
    memo: dict | None
    memo_error: str
    status: str
    decision: dict
    completion: dict
    trace: Annotated[list, operator.add]
    history: Annotated[list, operator.add]


def validate_decision(state, raw):
    if not isinstance(raw, dict) or raw.get("action") not in {"approve", "hold", "request_evidence"}:
        raise ValueError("Choose a valid review action.")
    reviewer, note = str(raw.get("reviewer", "")).strip(), str(raw.get("note", "")).strip()
    if not 2 <= len(reviewer) <= 80 or not 8 <= len(note) <= 1000:
        raise ValueError("Enter your name and a decision note of at least eight characters.")
    if raw["action"] == "approve" and (not state["analysis"]["approval_allowed"] or any(not f["passed"] for f in state["analysis"]["findings"])):
        raise ValueError("Approval is blocked while required evidence or financial checks are unresolved.")
    if raw["action"] == "request_evidence" and (not state["analysis"].get("missing_document_id") or state["round"] >= 3):
        raise ValueError("No further evidence request is available; record a hold.")
    return {"action": raw["action"], "reviewer": reviewer, "note": note, "round": state["round"], "at": now()}


def build_graph(workspace, model, saver):
    def triage(state):
        account = workspace.account(state["account_code"])
        if not account["material"]:
            raise ValueError("This account is below the review threshold.")
        return {"account": account, "round": 1, "calls": 0, "observations": [], "tool_sources": {}, "status": "investigating", "trace": [event(1, "Account movement selected for investigation", account)]}

    def plan(state):
        if state["calls"] >= 8:
            raise ValueError("The eight-decision investigation limit was reached.")
        used = {item["tool"] for item in state["observations"]}
        available = [name for name in ["ledger", "vendors", "invoice", "policy"] if name not in used]
        required = {"ledger", "invoice", "policy"}
        invoice = next((o["summary"] for o in state["observations"] if o["tool"] == "invoice"), {})
        if invoice and invoice.get("kind") == "Invoice":
            required.add("support")
            if "support" not in used:
                available.append("support")
        if required <= used:
            available.append("finish")
        decision = model.choose(state, available)
        if decision.action not in available:
            raise ValueError("The model selected an unavailable or repeated tool.")
        return {"action": decision.model_dump(), "calls": state["calls"] + 1, "trace": [event(2, decision.purpose, {"action": decision.action, "round": state["round"]})]}

    def act(state):
        name = state["action"]["action"]
        output = make_tools(workspace, state["account_code"])[name].invoke({})
        return {"observations": [*state["observations"], {"tool": name, "summary": output["summary"]}], "tool_sources": {**state["tool_sources"], **output["sources"]}, "trace": [event(2, "Evidence query completed", {"tool": name, "result": output, "round": state["round"]})]}

    def verify(state):
        analysis = evaluate(workspace, state["account_code"])
        memo, error = None, ""
        for attempt in range(2):
            try:
                candidate = model.memo(analysis)
                if set(candidate.source_ids) - set(analysis["sources"]):
                    raise ValueError("The explanation cites an unknown source.")
                if re.search(r"\d|\b(?:has been|was) (?:posted|paid|approved)\b", candidate.summary, re.I):
                    raise ValueError("The explanation contains a figure or an unsupported action claim.")
                memo = candidate.model_dump()
                break
            except ValueError as failure:
                error = str(failure)[:300]
        return {"analysis": analysis, "memo": memo, "memo_error": "" if memo else error, "status": "awaiting_review", "trace": [event(3, "Financial checks and allocation computed", {"outcome": analysis["outcome"], "adjustment_cents": analysis["adjustment_cents"], "explanation_accepted": bool(memo)}), event(4, "Waiting for a reviewer")]}

    def review(state):
        raw = interrupt({"kind": "review", "outcome": state["analysis"]["outcome"], "approval_allowed": state["analysis"]["approval_allowed"]})
        decision = validate_decision(state, raw)
        return {"decision": decision, "history": [decision], "status": "awaiting_evidence" if decision["action"] == "request_evidence" else "completed", "trace": [event(4, "Reviewer decision recorded", decision)]}

    def evidence(state):
        raw = interrupt({"kind": "evidence", "document_id": state["analysis"]["missing_document_id"]})
        document = workspace.document(raw.get("document_id", "")) if isinstance(raw, dict) else None
        if not document or document["id"] != state["analysis"]["missing_document_id"]:
            raise ValueError("The expected evidence document was not supplied.")
        return {"round": state["round"] + 1, "calls": 0, "observations": [], "tool_sources": {}, "status": "investigating", "trace": [event(1, "New evidence accepted; investigation resumed", {"document_id": document["id"], "sha256": document["sha256"]})]}

    def complete(state):
        return {"status": "completed", "completion": {"outcome": "workpaper_approved" if state["decision"]["action"] == "approve" else "held", "journal_posted": False, "at": now()}, "trace": [event(4, "Workpaper approved" if state["decision"]["action"] == "approve" else "Hold recorded", {"journal_posted": False})]}

    graph = StateGraph(State)
    for name, node in [("triage", triage), ("plan", plan), ("act", act), ("verify", verify), ("review", review), ("evidence", evidence), ("complete", complete)]:
        graph.add_node(name, node)
    graph.add_edge(START, "triage")
    graph.add_edge("triage", "plan")
    graph.add_conditional_edges("plan", lambda s: "verify" if s["action"]["action"] == "finish" else "act")
    graph.add_edge("act", "plan")
    graph.add_edge("verify", "review")
    graph.add_conditional_edges("review", lambda s: "evidence" if s["decision"]["action"] == "request_evidence" else "complete")
    graph.add_edge("evidence", "plan")
    graph.add_edge("complete", END)
    return graph.compile(checkpointer=saver)


class Service:
    def __init__(self, workspace, model):
        self.workspace, self.model = workspace, model
        self.checkpoint_connection = sqlite3.connect(workspace.directory / "checkpoints.db", check_same_thread=False)
        self.saver = SqliteSaver(self.checkpoint_connection)
        self.graph = build_graph(workspace, model, self.saver)

    def config(self, identifier):
        if not re.fullmatch(r"[a-f0-9]{32}", identifier):
            raise ValueError("Invalid investigation ID.")
        return {"configurable": {"thread_id": identifier}, "recursion_limit": 80}

    def run(self, identifier, payload, callback=None):
        try:
            for update in self.graph.stream(payload, self.config(identifier), stream_mode="updates"):
                if callback:
                    callback(update)
            with self.workspace.conn:
                self.workspace.conn.execute("UPDATE runs SET error=NULL WHERE id=?", (identifier,))
        except Exception as error:
            detail = str(error)[:400] if isinstance(error, ValueError) else "The investigation stopped. Its last checkpoint is retained; retry after checking the server."
            with self.workspace.conn:
                self.workspace.conn.execute("UPDATE runs SET error=? WHERE id=?", (detail, identifier))
            raise ValueError(detail) from error
        return self.view(identifier)

    def start(self, account, callback=None):
        if not self.workspace.account(account)["material"]:
            raise ValueError("This account is below the review threshold.")
        identifier = uuid4().hex
        with self.workspace.conn:
            self.workspace.conn.execute("INSERT INTO runs VALUES (?,?,?,NULL)", (identifier, account, now()))
        self.run(identifier, {"account_code": account}, callback)
        return identifier

    def latest(self, account):
        row = self.workspace.conn.execute("SELECT id FROM runs WHERE account=? ORDER BY created_at DESC LIMIT 1", (account,)).fetchone()
        return row[0] if row else None

    def view(self, identifier):
        registry = self.workspace.conn.execute("SELECT * FROM runs WHERE id=?", (identifier,)).fetchone()
        if not registry:
            raise ValueError("Investigation not found.")
        snapshot = self.graph.get_state(self.config(identifier))
        return {"id": identifier, "error": registry["error"], "model": self.model.name, **snapshot.values, "next_nodes": list(snapshot.next)}

    def review(self, identifier, decision, callback=None):
        state = self.view(identifier)
        if state.get("status") != "awaiting_review" or state["next_nodes"] != ["review"]:
            raise ValueError("This case is not awaiting a reviewer decision.")
        validate_decision(state, decision)
        return self.run(identifier, Command(resume=decision), callback)

    def reply(self, identifier, data, filename, callback=None):
        state = self.view(identifier)
        if state.get("status") != "awaiting_evidence" or state["next_nodes"] != ["evidence"]:
            raise ValueError("This case is not waiting for additional evidence.")
        record = read_pdf(data, filename)
        validate_reply(self.workspace, state, record)
        self.workspace.save_document(data, filename)
        return self.run(identifier, Command(resume={"document_id": record["id"]}), callback)

    def retry(self, identifier, callback=None):
        state = self.view(identifier)
        if not state.get("error"):
            raise ValueError("Only a stopped investigation can be retried.")
        return self.run(identifier, None, callback)
