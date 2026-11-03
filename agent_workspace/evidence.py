from __future__ import annotations

from io import BytesIO
from pathlib import Path
import hashlib
import json
import re

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "agent_samples"
CATALOG = json.loads((SAMPLES / "catalog.json").read_text())
MAX_PDF_BYTES = 2_000_000


def extract_pdf(data: bytes) -> list[str]:
    if len(data) > MAX_PDF_BYTES or not data.startswith(b"%PDF-"):
        raise ValueError("Provide a PDF file smaller than 2 MB.")
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            raise ValueError("Encrypted PDFs are not supported.")
        if not 1 <= len(reader.pages) <= 10:
            raise ValueError("PDFs must contain 1–10 pages.")
        pages = [p.extract_text() or "" for p in reader.pages]
    except ValueError:
        raise
    except Exception as error:
        raise ValueError("The PDF could not be read.") from error
    if not any(page.strip() for page in pages):
        raise ValueError(
            "No readable text found. Scanned images need OCR, which is outside this version."
        )
    if sum(map(len, pages)) > 12_000:
        raise ValueError(
            "Keep PDFs under 12,000 extracted characters to fit the local model's context budget."
        )
    return pages


def source_id_for_invoice(data: bytes) -> str:
    return "INVOICE-" + hashlib.sha256(data).hexdigest()[:12]


def normalize_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def source_registry(state: dict) -> dict[str, dict]:
    sources = {
        state["document"]["source_id"]: {
            "source_id": state["document"]["source_id"],
            "title": state["document"]["filename"],
            "kind": "invoice_pdf",
            "pages": state["document"]["pages"],
            "document_id": state["document"]["id"],
        }
    }
    invoice = state.get("invoice")
    if not invoice:
        return sources
    po_number = invoice["po_number"]["value"]
    vendor = normalize_identifier(invoice["vendor"]["value"])
    for kind, records in [
        ("purchase_order", CATALOG["purchase_orders"]),
        ("receiving_report", CATALOG["receiving_reports"]),
        ("vendor_master", CATALOG["vendors"]),
        ("payment_register", CATALOG["payments"]),
        ("policy", CATALOG["policies"]),
    ]:
        for record in records:
            relevant = (
                kind == "policy"
                or kind == "purchase_order"
                and record["id"] == po_number
                or kind == "receiving_report"
                and record["po_number"] == po_number
                or kind in ["vendor_master", "payment_register"]
                and normalize_identifier(record.get("name", record.get("vendor", "")))
                == vendor
            )
            if relevant:
                sources[record["source_id"]] = {
                    **record,
                    "kind": kind,
                    "title": record.get("title", record["source_id"]),
                }
    for reply in state.get("receiving_replies", []):
        sources[reply["source_id"]] = {
            **reply,
            "kind": "receiving_report",
            "title": reply["report_number"],
            "synthetic": state.get("synthetic", False),
        }
    return sources
