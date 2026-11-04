"""Authoritative close calculations. Model text cannot change these results."""
from __future__ import annotations

import calendar
from datetime import date

from .data import CATALOG, cents, dollars, value


def month_index(d: date) -> int:
    return d.year * 12 + d.month - 1


def schedule(amount: int, start: str, end: str, period: str) -> dict:
    try:
        first, last, close = date.fromisoformat(start), date.fromisoformat(end), date.fromisoformat(period + "-01")
    except ValueError:
        raise ValueError("The service dates must be valid ISO dates.") from None
    if first > last or first.day != 1 or last.day != calendar.monthrange(last.year, last.month)[1]:
        raise ValueError("Partial-month or reversed service dates need manual review.")
    months = month_index(last) - month_index(first) + 1
    if not 1 <= months <= 60:
        raise ValueError("Service periods longer than 60 months need manual review.")
    base, remainder = divmod(amount, months)
    rows = []
    for i in range(months):
        index = month_index(first) + i
        rows.append({"period": f"{index // 12:04d}-{index % 12 + 1:02d}", "expense_cents": base + int(i < remainder)})
    recognized = sum(r["expense_cents"] for r in rows if r["period"] <= period)
    current = sum(r["expense_cents"] for r in rows if r["period"] == period)
    return {"rows": rows, "months": months, "recognized_cents": recognized, "current_expense_cents": current, "future_cents": amount - recognized}


def validate_reply(workspace, state: dict, record: dict):
    expected = state["analysis"].get("missing_document_id")
    if not expected or record["id"] != expected:
        raise ValueError(f"This case is waiting for {expected or 'a different document'}.")
    if value(record, "Entity") != CATALOG["entity"]:
        raise ValueError("The document belongs to a different entity.")
    driver = state["analysis"].get("driver")
    if not driver:
        raise ValueError("The missing posting could not be identified; review this case manually.")
    if value(record, "Vendor").casefold() != driver["vendor"].casefold():
        raise ValueError("The document vendor does not match the posting.")
    if value(record, "Currency") != "USD" or cents(value(record, "Amount")) != driver["amount_cents"]:
        raise ValueError("The document amount or currency does not match the posting.")
    if expected != driver["document_id"]:
        if value(record, "Document type") != "Service agreement" or value(record, "Invoice ID") != driver["document_id"]:
            raise ValueError("The agreement does not refer to this invoice.")
        if value(record, "Authorized").casefold() != "yes":
            raise ValueError("The agreement does not contain the required authorization field.")
        schedule(driver["amount_cents"], value(record, "Service start"), value(record, "Service end"), CATALOG["period"])
    if workspace.document(record["id"]):
        raise ValueError("This document is already present; it cannot replace previously used evidence.")


def evaluate(workspace, account_code: str) -> dict:
    account = workspace.account(account_code)
    result = {"outcome": "hold", "approval_allowed": False, "account": account, "findings": [], "journal": [], "allocation": [], "adjustment_cents": 0, "adjusted_cents": account["current_cents"], "missing_document_id": None, "driver": None}
    ledger = workspace.ledger_source(account_code)
    sources = {ledger["id"]: ledger}
    result["sources"] = sources

    def finding(name, ok, detail, ids):
        result["findings"].append({"name": name, "passed": bool(ok), "detail": detail, "source_ids": ids})

    rows = workspace.ledger_rows(account_code, CATALOG["period"])
    duplicates = [r["document_id"] for r in rows if sum(s["document_id"] == r["document_id"] for s in rows) > 1]
    finding("Posting uniqueness", not duplicates, "No repeated document reference in the selected period." if not duplicates else "A document is referenced by multiple postings: " + ", ".join(sorted(set(duplicates))), [ledger["id"]])
    if duplicates:
        return result
    drivers = workspace.drivers(account_code)
    clear_driver = len(drivers) == 1 and drivers[0]["amount_cents"] == account["change_cents"] and drivers[0]["amount_cents"] > 0
    finding("Variance bridge", clear_driver, "One additional posting reconciles the full account movement." if clear_driver else "The movement has multiple or changing components; automatic treatment is withheld.", [ledger["id"]])
    if not clear_driver:
        return result
    driver = drivers[0]
    result["driver"] = driver
    invoice = workspace.document(driver["document_id"])
    if not invoice:
        result.update(outcome="evidence_needed", missing_document_id=driver["document_id"])
        finding("Posting support", False, "The posting's source document is missing.", [ledger["id"]])
        return result
    sources[invoice["id"]] = invoice
    supported = value(invoice, "Entity") == CATALOG["entity"] and value(invoice, "Vendor").casefold() == driver["vendor"].casefold() and value(invoice, "Currency") == "USD" and cents(value(invoice, "Amount")) == driver["amount_cents"]
    finding("Posting support", supported, "Source entity, vendor, currency, and amount agree with the posting." if supported else "The source does not agree with the posting.", [ledger["id"], invoice["id"]])
    if not supported:
        return result
    policy = workspace.document("POL-CLOSE")
    if not policy or value(policy, "Basis") != "Accrual":
        finding("Accounting policy", False, "The required accrual policy is unavailable.", [ledger["id"]])
        return result
    sources[policy["id"]] = policy
    if invoice["kind"] == "Payroll memo":
        ok = value(invoice, "Earned period") == CATALOG["period"] and value(invoice, "Approval") == "Approved"
        finding("Earned-period support", ok, "The approved one-time bonus was earned in October." if ok else "Bonus approval or earned period does not support this close.", [invoice["id"], policy["id"]])
        if ok:
            result.update(outcome="explained", approval_allowed=True)
        return result
    if invoice["kind"] != "Invoice":
        finding("Document type", False, "This source type needs manual review.", [invoice["id"]])
        return result
    agreement_id = value(invoice, "Agreement ID")
    contract = workspace.document(agreement_id)
    if not contract:
        result.update(outcome="evidence_needed", missing_document_id=agreement_id)
        finding("Service-period support", False, f"{agreement_id} is missing. Service dates are needed before proposing a treatment.", [invoice["id"], policy["id"]])
        return result
    sources[contract["id"]] = contract
    match = value(contract, "Entity") == CATALOG["entity"] and value(contract, "Vendor").casefold() == driver["vendor"].casefold() and value(contract, "Invoice ID") == driver["document_id"] and value(contract, "Currency") == "USD" and cents(value(contract, "Amount")) == driver["amount_cents"] and value(contract, "Authorized") == "Yes"
    finding("Agreement match", match, "The agreement matches the posting and contains the sample authorization field." if match else "The agreement does not match the posting or required authorization field.", [contract["id"], invoice["id"]])
    if not match:
        return result
    try:
        allocation = schedule(driver["amount_cents"], value(contract, "Service start"), value(contract, "Service end"), CATALOG["period"])
    except ValueError as error:
        finding("Service allocation", False, str(error), [contract["id"], policy["id"]])
        return result
    if allocation["recognized_cents"] != allocation["current_expense_cents"]:
        finding("Prior-period effects", False, "This agreement spans an earlier close; retrospective allocation needs manual review.", [contract["id"], policy["id"]])
        return result
    future = allocation["future_cents"]
    above_threshold = driver["amount_cents"] >= cents(value(policy, "Prepaid threshold"))
    adjustment = future if above_threshold else 0
    finding("Service allocation", True, f"{allocation['months']} full calendar month(s); USD {dollars(allocation['current_expense_cents'])} relates to October and USD {dollars(future)} to later periods. The supplied policy threshold is USD {value(policy, 'Prepaid threshold')}.", [contract["id"], policy["id"]])
    result.update(outcome="adjustment_proposed" if adjustment else "explained", approval_allowed=True, adjustment_cents=adjustment, adjusted_cents=account["current_cents"] - adjustment, allocation=allocation["rows"])
    if adjustment:
        result["journal"] = [{"account": "1500", "name": "Prepaid services", "debit_cents": adjustment, "credit_cents": 0}, {"account": account_code, "name": account["name"], "debit_cents": 0, "credit_cents": adjustment}]
    if sum(r["debit_cents"] for r in result["journal"]) != sum(r["credit_cents"] for r in result["journal"]):
        raise ValueError("The proposed journal does not balance.")
    return result
