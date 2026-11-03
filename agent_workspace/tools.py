"""Read-only, scoped investigation tools. No arbitrary SQL or external messaging."""

from __future__ import annotations

import re

from langchain_core.tools import tool

from .evidence import CATALOG, normalize_identifier, source_registry


TOOL_NAMES = [
    "lookup_purchase_order",
    "lookup_receiving",
    "lookup_vendor",
    "search_prior_payments",
    "search_policy",
]


def make_tools(state: dict):
    invoice = state["invoice"]
    po_number = invoice["po_number"]["value"]
    vendor_name = invoice["vendor"]["value"]
    invoice_number = invoice["invoice_number"]["value"]

    @tool
    def lookup_purchase_order(order_number: str) -> dict:
        """Read the current invoice's purchase order, including approved quantities and prices."""
        if order_number != po_number:
            return {
                "error": "This tool is scoped to the current invoice's purchase order."
            }
        record = next(
            (r for r in CATALOG["purchase_orders"] if r["id"] == order_number), None
        )
        return {
            "record": record,
            "source_ids": [record["source_id"]] if record else [],
            "synthetic": True,
        }

    @tool
    def lookup_receiving(order_number: str) -> dict:
        """Find original and subsequently supplied receiving evidence for this purchase order."""
        if order_number != po_number:
            return {
                "error": "This tool is scoped to the current invoice's purchase order."
            }
        records = [
            s
            for s in source_registry(state).values()
            if s["kind"] == "receiving_report" and s["po_number"] == order_number
        ]
        return {
            "records": records,
            "source_ids": [r["source_id"] for r in records],
            "synthetic": state["synthetic"],
        }

    @tool
    def lookup_vendor(name: str) -> dict:
        """Inspect the approved vendor master and compare bank details; never modify the record."""
        if normalize_identifier(name) != normalize_identifier(vendor_name):
            return {"error": "This tool is scoped to the current invoice's vendor."}
        record = next(
            (
                r
                for r in CATALOG["vendors"]
                if normalize_identifier(r["name"]) == normalize_identifier(name)
            ),
            None,
        )
        return {
            "record": record,
            "source_ids": [record["source_id"]] if record else [],
            "synthetic": True,
        }

    @tool
    def search_prior_payments(name: str, number: str) -> dict:
        """Search the demonstration payment register for the same vendor and invoice number."""
        if normalize_identifier(name) != normalize_identifier(
            vendor_name
        ) or normalize_identifier(number) != normalize_identifier(invoice_number):
            return {
                "error": "Search is scoped to the current vendor and invoice number."
            }
        records = [
            r
            for r in CATALOG["payments"]
            if normalize_identifier(r["vendor"]) == normalize_identifier(name)
            and normalize_identifier(r["invoice_number"])
            == normalize_identifier(number)
        ]
        return {
            "records": records,
            "source_ids": [r["source_id"] for r in records],
            "scope": "Synthetic demonstration register only",
        }

    @tool
    def search_policy(query: str) -> dict:
        """Retrieve relevant control-policy excerpts with source IDs using a keyword query."""
        tokens = set(re.findall(r"[a-z]+", query.casefold()))
        scored = [
            (
                len(
                    tokens
                    & set(
                        re.findall(r"[a-z]+", (p["title"] + " " + p["text"]).casefold())
                    )
                ),
                p,
            )
            for p in CATALOG["policies"]
        ]
        records = [
            record for score, record in sorted(scored, key=lambda x: -x[0]) if score > 0
        ][:3]
        return {
            "records": records,
            "source_ids": [r["source_id"] for r in records],
            "synthetic": True,
        }

    return [
        lookup_purchase_order,
        lookup_receiving,
        lookup_vendor,
        search_prior_payments,
        search_policy,
    ]
