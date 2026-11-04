from __future__ import annotations

from langchain_core.tools import tool
from .data import CATALOG, value, dollars


def make_tools(workspace, account):
    def source_summary(doc):
        if not doc:
            return None
        return {"id": doc["id"], "kind": doc["kind"], "fields": {k: v["value"] for k, v in doc["fields"].items()}}

    def driver_source():
        drivers = workspace.drivers(account)
        return workspace.document(drivers[0]["document_id"]) if len(drivers) == 1 else None

    @tool
    def ledger() -> dict:
        """Compare the selected account's actual September and October ledger rows."""
        source = workspace.ledger_source(account)
        drivers = workspace.drivers(account)
        return {"summary": {"totals": workspace.account(account), "new_postings": drivers[:8], "new_posting_count": len(drivers)}, "sources": {source["id"]: source}, "query": "SELECT * FROM transactions WHERE account=? AND substr(date,1,7) IN (?,?)", "parameters": [account, CATALOG["previous_period"], CATALOG["period"]]}

    @tool
    def vendors() -> dict:
        """Break the account movement down by vendor using a scoped SQLite query."""
        rows = workspace.query("SELECT vendor, substr(date,1,7) period, SUM(amount_cents) amount_cents FROM transactions WHERE account=? GROUP BY vendor,period ORDER BY vendor,period", (account,))
        return {"summary": {"vendor_totals": rows}, "sources": {}, "query": "SELECT vendor,period,SUM(amount_cents) FROM transactions WHERE account=? GROUP BY vendor,period", "parameters": [account]}

    @tool
    def invoice() -> dict:
        """Read the actual PDF supporting the new posting, including source-quoted fields."""
        drivers = workspace.drivers(account)
        doc = driver_source()
        if not doc:
            return {"summary": {"found": False, "reason": "Posting source missing or the movement has multiple drivers", "new_posting_count": len(drivers)}, "sources": {}}
        return {"summary": source_summary(doc), "sources": {doc["id"]: doc}}

    @tool
    def support() -> dict:
        """Look up the invoice's supporting service agreement; return missing evidence explicitly."""
        doc = driver_source()
        agreement_id = value(doc, "Agreement ID") if doc and doc["kind"] == "Invoice" else None
        agreement = workspace.document(agreement_id) if agreement_id else None
        return {"summary": source_summary(agreement) if agreement else {"found": False, "missing_document_id": agreement_id, "reason": "Service dates are not supplied; request the agreement before deciding treatment."}, "sources": {agreement["id"]: agreement} if agreement else {}}

    @tool
    def policy() -> dict:
        """Read the supplied close policy covering accrual, prepaids, bonuses, and review."""
        doc = workspace.document("POL-CLOSE")
        return {"summary": source_summary(doc), "sources": {doc["id"]: doc} if doc else {}}

    return {t.name: t for t in [ledger, vendors, invoice, support, policy]}
