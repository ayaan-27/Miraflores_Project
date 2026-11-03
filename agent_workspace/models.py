from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Literal
import re

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Citation(StrictModel):
    page: int = Field(ge=1, le=10)
    quote: str = Field(min_length=1, max_length=700)


class ExtractedField(StrictModel):
    value: str = Field(min_length=1, max_length=200)
    citation: Citation


class InvoiceLine(StrictModel):
    sku: ExtractedField
    quantity: ExtractedField
    unit_price: ExtractedField
    line_total: ExtractedField


class Invoice(StrictModel):
    vendor: ExtractedField
    invoice_number: ExtractedField
    po_number: ExtractedField
    invoice_date: ExtractedField
    currency: ExtractedField
    total: ExtractedField
    bank_last4: ExtractedField
    lines: list[InvoiceLine] = Field(min_length=1, max_length=20)


class ReceivingReply(StrictModel):
    report_number: ExtractedField
    po_number: ExtractedField
    sku: ExtractedField
    received_quantity: ExtractedField


class MemoFinding(StrictModel):
    title: str = Field(min_length=1, max_length=100)
    explanation: str = Field(min_length=1, max_length=700)
    source_ids: list[str] = Field(min_length=1, max_length=8)


class ReviewMemo(StrictModel):
    recommended_action: Literal["hold", "ready_for_review"]
    summary: str = Field(min_length=1, max_length=1800)
    findings: list[MemoFinding] = Field(min_length=1, max_length=12)
    next_actions: list[str] = Field(min_length=1, max_length=8)
    client_request: str = Field(min_length=1, max_length=3000)


class ReviewerDecision(StrictModel):
    action: Literal["approve", "request_evidence", "hold"]
    note: str = Field(min_length=5, max_length=1000)
    reviewer: str = Field(min_length=2, max_length=80)


class EvidenceResponse(StrictModel):
    document_id: str = Field(pattern=r"^[a-f0-9]{32}$")


class AgentDecision(StrictModel):
    action: Literal[
        "lookup_purchase_order",
        "lookup_receiving",
        "lookup_vendor",
        "search_prior_payments",
        "search_policy",
        "finish",
    ]
    purpose: str = Field(min_length=1, max_length=200)
    query: str = Field(default="", max_length=180)


def decimal_amount(value: str) -> Decimal:
    if not re.fullmatch(r"\d{1,9}(?:\.\d{1,2})?", value):
        raise ValueError(
            "Amounts must be nonnegative decimal strings with at most two decimal places."
        )
    amount = Decimal(value)
    if amount <= 0:
        raise ValueError("Invoice amounts must be greater than zero.")
    return amount.quantize(Decimal("0.01"))


def integer_quantity(value: str) -> int:
    if not re.fullmatch(r"[1-9]\d{0,5}", value):
        raise ValueError("This prototype supports positive whole-item quantities only.")
    return int(value)


def clean_text(value: str) -> str:
    return " ".join(value.casefold().split())


def validate_citations(model: BaseModel, pages: list[str]) -> None:
    """Every extracted value must occur in its actual quoted source page."""
    for name in type(model).model_fields:
        value = getattr(model, name)
        if isinstance(value, ExtractedField):
            if value.citation.page > len(pages):
                raise ValueError(f"{name}: cited page does not exist.")
            quote = clean_text(value.citation.quote)
            if quote not in clean_text(pages[value.citation.page - 1]):
                raise ValueError(f"{name}: quote was not found in the source PDF.")
            needle = clean_text(value.value)
            if name == "bank_last4" and not re.search(
                r"(?<!\d)" + re.escape(needle) + r"(?!\d)", quote
            ):
                raise ValueError(
                    "bank_last4: the literal account suffix is unsupported by its source quote."
                )
            if re.fullmatch(r"\d+(?:\.\d{1,2})?", needle):
                # Numeric token boundaries prevent citing 12000 as support for 120.
                tokens = re.findall(r"\d[\d,]*(?:\.\d+)?", quote)
                try:
                    found = any(
                        Decimal(t.replace(",", "")) == Decimal(needle) for t in tokens
                    )
                except InvalidOperation:
                    found = False
                if not found:
                    raise ValueError(
                        f"{name}: extracted number is unsupported by its source quote."
                    )
            elif needle not in quote:
                raise ValueError(
                    f"{name}: extracted value {value.value!r} is unsupported by source quote {value.citation.quote[:160]!r}."
                )
        elif isinstance(value, BaseModel):
            validate_citations(value, pages)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, BaseModel):
                    validate_citations(item, pages)


def validate_invoice(invoice: Invoice, pages: list[str]) -> None:
    from datetime import date

    validate_citations(invoice, pages)
    if invoice.currency.value != "USD":
        raise ValueError("Only USD invoices are supported in this first version.")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", invoice.invoice_date.value):
        raise ValueError(
            "Invoice dates must be extracted as literal YYYY-MM-DD values."
        )
    date.fromisoformat(invoice.invoice_date.value)
    if not re.fullmatch(r"\d{4}", invoice.bank_last4.value):
        raise ValueError(
            "A four-digit bank account suffix is required for the bank-details control."
        )
    decimal_amount(invoice.total.value)
    skus = set()
    for line in invoice.lines:
        if line.sku.value in skus:
            raise ValueError(
                "Repeated SKU lines require manual normalization in this prototype."
            )
        skus.add(line.sku.value)
        integer_quantity(line.quantity.value)
        decimal_amount(line.unit_price.value)
        decimal_amount(line.line_total.value)


SOURCE_LABELS = {
    "vendor": ["Vendor:", "Supplier:"],
    "invoice_number": ["Invoice number:", "Invoice #:", "Invoice no:"],
    "po_number": ["Purchase order:", "PO number:", "PO #:"],
    "invoice_date": ["Invoice date:"],
    "currency": ["Currency:"],
    "total": ["Invoice total:", "Total due:"],
    "bank_last4": ["Bank account ending:", "Account ending:"],
    "sku": ["SKU:", "Product code:", "Item code:"],
    "quantity": ["Quantity:", "Qty:"],
    "unit_price": ["Unit price:", "Unit cost:"],
    "line_total": ["Line total:", "Extended amount:"],
    "report_number": ["Report number:", "Receiving report:"],
    "received_quantity": ["Additional quantity received:", "Received quantity:"],
}


def ground_source_quotes(model: BaseModel, pages: list[str]) -> list[dict]:
    """Locate a unique labeled line for an already extracted value; never invent a value.

    Ambiguous or absent matches are left unchanged for the strict validator to
    accept or reject. The original model output and all changes are traceable.
    """
    changes = []
    for name in type(model).model_fields:
        value = getattr(model, name)
        if isinstance(value, ExtractedField):
            matches = []
            labels = SOURCE_LABELS.get(name, [])
            for page_number, page in enumerate(pages, 1):
                for line in page.splitlines():
                    if not any(
                        clean_text(line).startswith(clean_text(label))
                        for label in labels
                    ):
                        continue
                    candidate = value.model_copy(deep=True)
                    candidate.citation = Citation(page=page_number, quote=line)
                    # Reuse the exact original field validator through a typed one-field wrapper.
                    from pydantic import create_model

                    wrapper = create_model(
                        "SourceField", **{name: (ExtractedField, ...)}
                    )
                    try:
                        validate_citations(wrapper(**{name: candidate}), pages)
                    except ValueError:
                        continue
                    matches.append(candidate.citation)
            if len(matches) == 1 and matches[0] != value.citation:
                changes.append(
                    {
                        "field": name,
                        "value": value.value,
                        "before": value.citation.model_dump(),
                        "after": matches[0].model_dump(),
                        "method": "unique_labeled_pdf_line",
                    }
                )
                value.citation = matches[0]
        elif isinstance(value, BaseModel):
            changes.extend(ground_source_quotes(value, pages))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, BaseModel):
                    changes.extend(ground_source_quotes(item, pages))
    return changes
