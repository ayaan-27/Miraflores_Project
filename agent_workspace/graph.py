"""Four-stage LangGraph workflow with actual tool choices and persisted interrupts."""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt

from .controls import evaluate_controls
from .evidence import normalize_identifier, source_registry
from .models import (
    ReviewerDecision,
    integer_quantity,
    validate_citations,
    validate_invoice,
)
from .store import now
from .tools import make_tools, TOOL_NAMES


class InvestigationState(TypedDict, total=False):
    run_id: str
    document: dict
    synthetic: bool
    invoice: dict
    action: dict
    tool_results: list[dict]
    iterations: int
    round: int
    feedback: str
    controls: dict | None
    memo: dict | None
    receiving_replies: list[dict]
    review_history: list[dict]
    decision: dict | None
    completion: dict
    needs_more_tools: bool
    pending_document: dict | None
    evidence_error: str | None


def build_graph(model, store, checkpointer):
    async def extract(state: InvestigationState):
        await store.emit(
            state["run_id"],
            1,
            "started",
            "Reading the invoice PDF",
            {"filename": state["document"]["filename"], "model": model.name},
        )
        invoice = await model.extract_invoice(state["document"])
        validate_invoice(invoice, state["document"]["pages"])
        await store.emit(
            state["run_id"],
            1,
            "completed",
            "Extracted fields checked against the actual PDF",
            {
                "invoice_number": invoice.invoice_number.value,
                "source_id": state["document"]["source_id"],
                "usage": model.last_usage,
            },
        )
        return {
            "invoice": invoice.model_dump(),
            "tool_results": [],
            "iterations": 0,
            "round": 1,
            "receiving_replies": [],
            "review_history": [],
            "feedback": "",
        }

    async def plan(state: InvestigationState):
        if state["iterations"] >= 8:
            raise ValueError(
                "The investigation reached its eight-decision limit without complete tool coverage."
            )
        decision = await model.investigate(
            state, state["tool_results"], state.get("feedback", "")
        )
        if decision.action != "finish" and decision.action in {
            result["tool"] for result in state["tool_results"]
        }:
            raise ValueError(
                "The model repeated an already completed tool; no unbounded loop was allowed."
            )
        await store.emit(
            state["run_id"],
            2,
            "plan",
            decision.purpose,
            {
                "action": decision.action,
                "query": decision.query,
                "round": state["round"],
                "usage": model.last_usage,
            },
        )
        return {"action": decision.model_dump(), "iterations": state["iterations"] + 1}

    async def execute_tool(state: InvestigationState):
        tools = {tool.name: tool for tool in make_tools(state)}
        action = state["action"]["action"]
        invoice = state["invoice"]
        arguments = {
            "lookup_purchase_order": {"order_number": invoice["po_number"]["value"]},
            "lookup_receiving": {"order_number": invoice["po_number"]["value"]},
            "lookup_vendor": {"name": invoice["vendor"]["value"]},
            "search_prior_payments": {
                "name": invoice["vendor"]["value"],
                "number": invoice["invoice_number"]["value"],
            },
            "search_policy": {
                "query": state["action"]["query"]
                or "purchase order receiving bank duplicate evidence"
            },
        }[action]
        result = await tools[action].ainvoke(arguments)
        if result.get("error"):
            raise ValueError(result["error"])
        observation = {"tool": action, "arguments": arguments, "result": result}
        await store.emit(state["run_id"], 2, "tool", action, observation)
        return {"tool_results": [*state["tool_results"], observation]}

    async def challenge(state: InvestigationState):
        missing = set(TOOL_NAMES) - {result["tool"] for result in state["tool_results"]}
        if missing:
            feedback = (
                "The control reviewer requires these missing evidence checks before finishing: "
                + ", ".join(sorted(missing))
            )
            await store.emit(
                state["run_id"],
                3,
                "returned",
                "Investigation returned for missing checks",
                {"missing_tools": sorted(missing)},
            )
            return {"needs_more_tools": True, "feedback": feedback}
        await store.emit(
            state["run_id"],
            3,
            "started",
            "Recomputing the financial controls from the source records",
        )
        controls = evaluate_controls(state)
        error = ""
        memo = None
        for attempt in range(2):
            candidate = await model.verify(state, controls, error)
            try:
                if candidate.recommended_action != controls["recommendation"]:
                    raise ValueError(
                        "The memo recommendation must equal the computed control result."
                    )
                for finding in candidate.findings:
                    if not set(finding.source_ids) <= set(controls["sources"]):
                        raise ValueError(
                            "A finding referenced a source that does not exist in the evidence registry."
                        )
                memo = candidate
                break
            except ValueError as exception:
                error = str(exception)
                await store.emit(
                    state["run_id"],
                    3,
                    "returned",
                    "Unsupported draft returned to the verifier",
                    {"issue": error, "attempt": attempt + 1},
                )
        if memo is None:
            raise ValueError(
                "The model could not produce a source-valid review memo within two attempts."
            )
        await store.emit(
            state["run_id"],
            3,
            "completed",
            "Source references and control recommendation verified",
            {
                "recommendation": controls["recommendation"],
                "failed_controls": controls["failed_controls"],
                "unsupported_amount": controls["unsupported_amount"],
                "usage": model.last_usage,
            },
        )
        return {
            "controls": controls,
            "memo": memo.model_dump(),
            "needs_more_tools": False,
            "feedback": "",
        }

    async def review_gate(state: InvestigationState):
        raw = interrupt(
            {
                "type": "review_decision",
                "recommendation": state["controls"]["recommendation"],
                "failed_controls": state["controls"]["failed_controls"],
                "invoice_number": state["invoice"]["invoice_number"]["value"],
                "allowed_actions": ["request_evidence", "hold"]
                + (["approve"] if not state["controls"]["failed_controls"] else []),
            }
        )
        decision = ReviewerDecision.model_validate(raw)
        if decision.action == "approve" and state["controls"]["failed_controls"]:
            raise ValueError(
                "A reviewer cannot approve while a required financial control fails."
            )
        if decision.action == "request_evidence" and state["round"] >= 3:
            raise ValueError(
                "Three evidence rounds reached. Hold this invoice for investigation outside the prototype."
            )
        record = {**decision.model_dump(), "at": now(), "round": state["round"]}
        await store.emit(
            state["run_id"], 4, "decision", "Human reviewer decision recorded", record
        )
        return {
            "decision": record,
            "review_history": [*state["review_history"], record],
        }

    async def await_evidence(state: InvestigationState):
        raw = interrupt(
            {
                "type": "evidence_reply",
                "request": state["memo"]["client_request"],
                "validation_error": state.get("evidence_error"),
                "notice": "Provide an additional receiving-report PDF for this invoice's purchase order. No request has been sent.",
            }
        )
        return {"pending_document": raw["document"]}

    async def validate_evidence(state: InvestigationState):
        try:
            return await accept_evidence(state)
        except ValueError as error:
            detail = str(error)[:400]
            await store.emit(
                state["run_id"],
                1,
                "rejected",
                "Additional evidence rejected; the prior review is preserved",
                {"detail": detail},
            )
            return {"evidence_error": detail, "pending_document": None}

    async def accept_evidence(state: InvestigationState):
        document = state["pending_document"]
        reply = await model.extract_receiving(document)
        validate_citations(reply, document["pages"])
        if reply.po_number.value != state["invoice"]["po_number"]["value"]:
            raise ValueError("The reply refers to a different purchase order.")
        if reply.sku.value not in {
            line["sku"]["value"] for line in state["invoice"]["lines"]
        }:
            raise ValueError("The reply refers to a SKU outside this invoice.")
        if "report" not in reply.report_number.citation.quote.casefold():
            raise ValueError(
                "The report number must be supported by an actual receiving-report label."
            )
        quantity = integer_quantity(reply.received_quantity.value)
        current = source_registry(state)
        report_number = normalize_identifier(reply.report_number.value)
        if any(
            normalize_identifier(source.get("report_number", source["source_id"]))
            == report_number
            for source in current.values()
        ):
            raise ValueError(
                "This receiving report already exists. It cannot be counted twice."
            )
        if any(
            source.get("document_id") == document["id"]
            or source.get("document_hash") == document["source_id"]
            for source in state.get("receiving_replies", [])
        ):
            raise ValueError("This source document has already been used as evidence.")
        record = {
            "source_id": "RECEIVING-" + document["id"][:12],
            "report_number": reply.report_number.value,
            "po_number": reply.po_number.value,
            "sku": reply.sku.value,
            "received_quantity": quantity,
            "document_id": document["id"],
            "document_hash": document["source_id"],
            "pages": document["pages"],
            "extraction": reply.model_dump(),
        }
        await store.emit(
            state["run_id"],
            1,
            "evidence",
            "New receiving evidence validated; investigation will run again",
            {
                "source_id": record["source_id"],
                "report_number": record["report_number"],
                "additional_quantity": quantity,
                "round": state["round"] + 1,
            },
        )
        return {
            "receiving_replies": [*state["receiving_replies"], record],
            "round": state["round"] + 1,
            "iterations": 0,
            "tool_results": [],
            "controls": None,
            "memo": None,
            "decision": None,
            "feedback": "A human supplied new receiving evidence. Recheck all controls against the expanded source set.",
            "pending_document": None,
            "evidence_error": None,
        }

    async def finalize(state: InvestigationState):
        result = (
            "release_recommended"
            if state["decision"]["action"] == "approve"
            else "held"
        )
        completion = {
            "result": result,
            "at": now(),
            "notice": "No payment, email, ledger entry, or vendor update was initiated.",
        }
        await store.emit(
            state["run_id"], 4, "completed", "Review pack finalized", completion
        )
        return {"completion": completion}

    graph = StateGraph(InvestigationState)
    for name, node in [
        ("extract", extract),
        ("plan", plan),
        ("tools", execute_tool),
        ("challenge", challenge),
        ("review_gate", review_gate),
        ("await_evidence", await_evidence),
        ("validate_evidence", validate_evidence),
        ("finalize", finalize),
    ]:
        graph.add_node(name, node)
    graph.add_edge(START, "extract")
    graph.add_edge("extract", "plan")
    graph.add_conditional_edges(
        "plan", lambda s: "challenge" if s["action"]["action"] == "finish" else "tools"
    )
    graph.add_edge("tools", "plan")
    graph.add_conditional_edges(
        "challenge", lambda s: "plan" if s["needs_more_tools"] else "review_gate"
    )
    graph.add_conditional_edges(
        "review_gate",
        lambda s: "await_evidence"
        if s["decision"]["action"] == "request_evidence"
        else "finalize",
    )
    graph.add_edge("await_evidence", "validate_evidence")
    graph.add_conditional_edges(
        "validate_evidence",
        lambda s: "await_evidence" if s.get("evidence_error") else "plan",
    )
    graph.add_edge("finalize", END)
    return graph.compile(checkpointer=checkpointer)
