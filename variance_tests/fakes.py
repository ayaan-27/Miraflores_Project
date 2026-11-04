"""Explicit test double. Never selected by the application."""
from variance_workspace.model import Choice, Memo

class Planner:
    name = "Test planner"
    calls = 0

    def choose(self, state, available):
        self.calls += 1
        return Choice(action=available[0], purpose="Inspect the next available evidence source.")

    def memo(self, analysis):
        self.calls += 1
        return Memo(summary="The evidence and policy checks identify the next review step. A reviewer must decide whether the support is sufficient.", source_ids=list(analysis["sources"])[:2])
