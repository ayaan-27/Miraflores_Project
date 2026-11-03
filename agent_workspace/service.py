from __future__ import annotations

import asyncio

from langgraph.types import Command

from .graph import build_graph
from .models import ReviewerDecision


class RunService:
    def __init__(self, model, store, checkpointer):
        self.model = model
        self.store = store
        self.graph = build_graph(model, store, checkpointer)
        self.tasks: dict[str, asyncio.Task] = {}

    def config(self, run_id):
        return {"configurable": {"thread_id": run_id}, "recursion_limit": 100}

    async def start(self, document: dict, case_id=None, synthetic=False):
        if not self.model.available:
            raise ValueError(
                "The local model is not installed. Download the official open weights before starting a run."
            )
        if sum(not task.done() for task in self.tasks.values()) >= 2:
            raise ValueError(
                "Two investigations are already queued. Wait for a run to pause or finish."
            )
        identifier = await self.store.new_run(case_id)
        self._schedule(
            identifier,
            {"run_id": identifier, "document": document, "synthetic": synthetic},
        )
        return identifier

    def _schedule(self, run_id, value):
        if run_id in self.tasks and not self.tasks[run_id].done():
            raise ValueError("This investigation is already running.")
        self.tasks[run_id] = asyncio.create_task(self._execute(run_id, value))

    async def _execute(self, run_id, value):
        await self.store.set_status(run_id, "running")
        try:
            await self.graph.ainvoke(value, self.config(run_id))
            snapshot = await self.graph.aget_state(self.config(run_id))
            if "review_gate" in snapshot.next:
                await self.store.set_status(run_id, "awaiting_review")
                await self.store.emit(
                    run_id,
                    4,
                    "paused",
                    "Investigation paused for an identified human reviewer",
                )
            elif "await_evidence" in snapshot.next:
                await self.store.set_status(run_id, "awaiting_evidence")
                await self.store.emit(
                    run_id,
                    4,
                    "paused",
                    "Evidence request prepared; waiting for a receiving report",
                    {"notice": "No email has been sent."},
                )
            else:
                await self.store.set_status(run_id, "completed")
        except asyncio.CancelledError:
            await self.store.set_status(
                run_id,
                "stopped",
                "Execution stopped. The last checkpoint was preserved.",
            )
            raise
        except Exception as error:
            # Local inference uses no credentials. Still avoid serializing arbitrary provider payloads.
            if isinstance(error, ValueError):
                detail = str(error)[:400]
            else:
                detail = f"Execution failed ({type(error).__name__}). Inspect the local service configuration, then retry the persisted checkpoint."
            await self.store.set_status(run_id, "failed", detail)
            await self.store.emit(
                run_id,
                0,
                "error",
                "The run stopped without issuing a recommendation",
                {"detail": detail},
            )

    async def view(self, run_id):
        run = await self.store.get_run(run_id)
        if not run:
            return None
        snapshot = await self.graph.aget_state(self.config(run_id))
        state = snapshot.values or {}
        return {
            **run,
            "mode": self.model.mode,
            "model": self.model.name,
            "invoice": state.get("invoice"),
            "document": state.get("document"),
            "round": state.get("round", 1),
            "controls": state.get("controls"),
            "memo": state.get("memo"),
            "review_history": state.get("review_history", []),
            "completion": state.get("completion"),
            "receiving_replies": state.get("receiving_replies", []),
            "synthetic": state.get("synthetic", False),
            "evidence_error": state.get("evidence_error"),
            "next_nodes": list(snapshot.next),
            "events": await self.store.events(run_id),
        }

    async def review(self, run_id, decision: ReviewerDecision):
        view = await self.view(run_id)
        if not view or view["status"] != "awaiting_review":
            raise ValueError("This run is not awaiting a review decision.")
        if decision.action == "approve" and view["controls"]["failed_controls"]:
            raise ValueError(
                "Approval is blocked while required financial controls fail."
            )
        if decision.action == "request_evidence" and view["round"] >= 3:
            raise ValueError(
                "The three-round evidence limit was reached; place the invoice on hold."
            )
        self._schedule(run_id, Command(resume=decision.model_dump()))

    async def reply(self, run_id, document: dict):
        view = await self.view(run_id)
        if not view or view["status"] != "awaiting_evidence":
            raise ValueError("This run is not waiting for additional evidence.")
        self._schedule(run_id, Command(resume={"document": document}))

    async def retry(self, run_id):
        run = await self.store.get_run(run_id)
        if not run or run["status"] not in ["failed", "stopped"]:
            raise ValueError("Only a stopped or failed run can be retried.")
        self._schedule(run_id, None)

    async def close(self):
        for task in self.tasks.values():
            if not task.done():
                task.cancel()
        await asyncio.gather(*self.tasks.values(), return_exceptions=True)
        if hasattr(self.model, "aclose"):
            await self.model.aclose()
