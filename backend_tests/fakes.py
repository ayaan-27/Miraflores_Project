"""Deterministic test double only. Never imported by the running application."""

from agent_workspace.models import (
    AgentDecision,
    Citation,
    ExtractedField,
    Invoice,
    InvoiceLine,
    ReceivingReply,
    ReviewMemo,
    MemoFinding,
)
from agent_workspace.tools import TOOL_NAMES


class FixtureModel:
    available = True
    name = "Fixture model — tests only"
    mode = "test_double"
    last_usage = {}

    def field(self, pages, label):
        for page, text in enumerate(pages, 1):
            for line in text.splitlines():
                if line.startswith(label + ": "):
                    return ExtractedField(
                        value=line.split(": ", 1)[1],
                        citation=Citation(page=page, quote=line),
                    )
        raise ValueError("Missing source label: " + label)

    async def extract_invoice(self, document, feedback=None):
        pages = document["pages"]
        f = lambda key: self.field(pages, key)
        return Invoice(
            vendor=f("Vendor"),
            invoice_number=f("Invoice number"),
            po_number=f("Purchase order"),
            invoice_date=f("Invoice date"),
            currency=f("Currency"),
            total=f("Invoice total"),
            bank_last4=f("Bank account ending"),
            lines=[
                InvoiceLine(
                    sku=f("SKU"),
                    quantity=f("Quantity"),
                    unit_price=f("Unit price"),
                    line_total=f("Line total"),
                )
            ],
        )

    async def investigate(self, state, results, feedback=""):
        used = {r["tool"] for r in results}
        # Changed-bank fixtures deliberately inspect the vendor first, demonstrating route variation in tests.
        order = TOOL_NAMES.copy()
        if state["invoice"]["vendor"]["value"] == "Northstar Services LLC":
            order.remove("lookup_vendor")
            order.insert(0, "lookup_vendor")
        action = next((tool for tool in order if tool not in used), "finish")
        return AgentDecision(
            action=action,
            purpose="Test fixture requests " + action,
            query="receiving bank duplicate evidence",
        )

    async def verify(self, state, controls, previous_error=""):
        failed = [f for f in controls["findings"] if f["result"] == "fail"]
        selected = failed or controls["findings"][:1]
        return ReviewMemo(
            recommended_action=controls["recommendation"],
            summary="Hold pending receiving evidence."
            if failed
            else "Required controls passed; human review is still required.",
            findings=[
                MemoFinding(
                    title=f["title"],
                    explanation=f["detail"],
                    source_ids=f["source_ids"],
                )
                for f in selected
            ],
            next_actions=["Review the source evidence."],
            client_request="Please provide the remaining receiving evidence."
            if failed
            else "No additional evidence requested.",
        )

    async def extract_receiving(self, document, feedback=None):
        f = lambda key: self.field(document["pages"], key)
        return ReceivingReply(
            report_number=f("Report number"),
            po_number=f("Purchase order"),
            sku=f("SKU"),
            received_quantity=f("Additional quantity received"),
        )
