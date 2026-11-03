"""Financial controls are computed from sources; a language model cannot override them."""

from __future__ import annotations

from decimal import Decimal

from .evidence import CATALOG, normalize_identifier, source_registry
from .models import Invoice, decimal_amount, integer_quantity


def evaluate_controls(state: dict) -> dict:
    invoice = Invoice.model_validate(state["invoice"])
    total = decimal_amount(invoice.total.value)
    invoice_id = state["document"]["source_id"]
    sources = source_registry(state)
    vendor_key = normalize_identifier(invoice.vendor.value)
    po = next(
        (r for r in CATALOG["purchase_orders"] if r["id"] == invoice.po_number.value),
        None,
    )
    vendor = next(
        (
            r
            for r in CATALOG["vendors"]
            if normalize_identifier(r["name"]) == vendor_key
        ),
        None,
    )
    receiving = [r for r in sources.values() if r["kind"] == "receiving_report"]
    paid = [
        r
        for r in CATALOG["payments"]
        if normalize_identifier(r["vendor"]) == vendor_key
        and normalize_identifier(r["invoice_number"])
        == normalize_identifier(invoice.invoice_number.value)
        and r["status"] in ["paid", "pending"]
    ]
    findings = []

    def add(code, title, passed, detail, ids, policy):
        findings.append(
            {
                "code": code,
                "title": title,
                "result": "pass" if passed else "fail",
                "detail": detail,
                "source_ids": list(dict.fromkeys([invoice_id, *ids, policy])),
            }
        )

    calculated = sum(
        (
            integer_quantity(line.quantity.value)
            * decimal_amount(line.unit_price.value)
            for line in invoice.lines
        ),
        Decimal("0.00"),
    )
    line_sums_ok = all(
        integer_quantity(line.quantity.value) * decimal_amount(line.unit_price.value)
        == decimal_amount(line.line_total.value)
        for line in invoice.lines
    )
    add(
        "INVOICE_ARITHMETIC",
        "Invoice arithmetic",
        line_sums_ok and calculated == total,
        f"Calculated line total ${calculated:,.2f}; stated invoice total ${total:,.2f}. Taxes, discounts, and shipping adjustments are outside this prototype.",
        [],
        "POL-01",
    )
    po_valid = bool(
        po
        and po["status"] == "approved"
        and normalize_identifier(po["vendor"]) == vendor_key
        and po["currency"] == invoice.currency.value
    )
    add(
        "APPROVED_PO",
        "Approved purchase order",
        po_valid,
        f"{po['id']} is approved for the same vendor and currency."
        if po_valid
        else "No approved purchase order for this vendor and currency was found.",
        [po["source_id"]] if po else [],
        "POL-01",
    )

    supported = Decimal("0.00")
    for line in invoice.lines:
        sku, qty, price = (
            line.sku.value,
            integer_quantity(line.quantity.value),
            decimal_amount(line.unit_price.value),
        )
        po_line = (
            next((r for r in po["lines"] if r["sku"] == sku), None)
            if po_valid
            else None
        )
        price_ok = bool(po_line and price == decimal_amount(po_line["unit_price"]))
        quantity_ok = bool(po_line and qty <= po_line["quantity"])
        add(
            "PO_LINE:" + sku,
            "Order match · " + sku,
            price_ok and quantity_ok,
            f"Invoice: {qty} units at ${price:,.2f}. "
            + (
                f"Approved order: {po_line['quantity']} units at ${Decimal(po_line['unit_price']):,.2f}."
                if po_line
                else "No approved order line found."
            ),
            [po["source_id"]] if po else [],
            "POL-01",
        )
        reports = [
            r
            for r in receiving
            if r["sku"] == sku and r["po_number"] == invoice.po_number.value
        ]
        received_qty = sum(r["received_quantity"] for r in reports)
        add(
            "RECEIVING:" + sku,
            "Receiving evidence · " + sku,
            received_qty >= qty,
            f"Billed {qty} units; receiving reports support {received_qty} units. "
            + (
                "The billed quantity is supported."
                if received_qty >= qty
                else f"Evidence for {qty - received_qty} units is still missing."
            ),
            [r["source_id"] for r in reports],
            "POL-01",
        )
        if price_ok and po_line:
            supported += min(qty, received_qty, po_line["quantity"]) * price

    bank_ok = bool(
        vendor
        and vendor["status"] == "active"
        and vendor["approved_bank_last4"] == invoice.bank_last4.value
    )
    add(
        "VENDOR_BANK",
        "Vendor payment details",
        bank_ok,
        f"Invoice account ending {invoice.bank_last4.value}; "
        + (
            f"approved vendor account ending {vendor['approved_bank_last4']}."
            if vendor
            else "no approved vendor record found."
        )
        + (
            ""
            if bank_ok
            else " Independent verification through an existing trusted contact is required."
        ),
        [vendor["source_id"]] if vendor else [],
        "POL-02",
    )
    add(
        "DUPLICATE_PAYMENT",
        "Prior payment check",
        not paid,
        "A matching vendor invoice already appears as paid or pending. Hold for review; this is not a fraud determination."
        if paid
        else "No matching paid or pending vendor invoice was found in the synthetic payment register.",
        [p["source_id"] for p in paid],
        "POL-03",
    )

    # A negative search is backed by an explicit query-snapshot source, not an invented payment.
    if not paid:
        query_id = "PAYMENT-SEARCH-" + normalize_identifier(
            invoice.invoice_number.value
        )
        sources[query_id] = {
            "source_id": query_id,
            "kind": "query_result",
            "title": "Payment register query",
            "vendor": invoice.vendor.value,
            "invoice_number": invoice.invoice_number.value,
            "matches": [],
            "scope": "Synthetic demonstration register only",
        }
        findings[-1]["source_ids"].insert(1, query_id)

    failed = [finding for finding in findings if finding["result"] == "fail"]
    return {
        "findings": findings,
        "recommendation": "hold" if failed else "ready_for_review",
        "failed_controls": len(failed),
        "invoice_amount": f"{total:.2f}",
        "receiving_supported_amount": f"{min(supported, total):.2f}",
        "unsupported_amount": f"{max(total - supported, Decimal('0.00')):.2f}",
        "sources": sources,
        "notice": "Receiving support is not a partial-payment authorization. No payment is initiated.",
    }
