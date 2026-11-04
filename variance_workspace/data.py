from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
from io import BytesIO, StringIO
import json
from pathlib import Path
import re
import sqlite3

from pypdf import PdfReader

SAMPLES = Path(__file__).resolve().parents[1] / "variance_samples"
CATALOG = json.loads((SAMPLES / "catalog.json").read_text())


def cents(value: str) -> int:
    if not re.fullmatch(r"\d{1,9}(?:\.\d{1,2})?", value):
        raise ValueError("Amounts must be plain nonnegative USD numbers with at most two decimals.")
    return int(Decimal(value) * 100)


def dollars(value: int) -> str:
    return f"{Decimal(value) / 100:.2f}"


def parse_ledger(data: bytes) -> list[dict]:
    if len(data) > 1_000_000:
        raise ValueError("Keep the ledger under 1 MB.")
    try:
        reader = csv.DictReader(StringIO(data.decode("utf-8-sig")), strict=True)
        required = {"id", "date", "account", "vendor", "description", "debit", "credit", "currency", "document_id"}
        if set(reader.fieldnames or []) != required:
            raise ValueError("Use the sample ledger's nine column headers.")
        result, ids = [], set()
        for number, raw in enumerate(reader, 2):
            if len(result) >= 2000:
                raise ValueError("Keep the ledger under 2,000 rows.")
            if None in raw or any(v is None or not v.strip() or len(v) > 300 for v in raw.values()):
                raise ValueError(f"Row {number}: missing, extra, or oversized field.")
            r = {k: v.strip() for k, v in raw.items()}
            if not re.fullmatch(r"[\w-]{1,64}", r["id"]) or r["id"] in ids:
                raise ValueError(f"Row {number}: duplicate or invalid transaction ID.")
            ids.add(r["id"])
            try:
                if date.fromisoformat(r["date"]).isoformat() != r["date"]:
                    raise ValueError()
            except ValueError:
                raise ValueError(f"Row {number}: use a valid YYYY-MM-DD date.") from None
            if r["date"][:7] not in {CATALOG["period"], CATALOG["previous_period"]}:
                raise ValueError(f"Row {number}: this close compares September and October 2026 only.")
            if r["account"] not in CATALOG["accounts"] or r["currency"] != "USD":
                raise ValueError(f"Row {number}: use a supplied expense account and USD.")
            debit, credit = cents(r.pop("debit")), cents(r.pop("credit"))
            if bool(debit) == bool(credit):
                raise ValueError(f"Row {number}: enter either a debit or a credit, not both or neither.")
            r["amount_cents"] = debit - credit
            result.append(r)
    except (UnicodeDecodeError, csv.Error):
        raise ValueError("The ledger must be a readable UTF-8 CSV.") from None
    if not result or {r["date"][:7] for r in result} != {CATALOG["period"], CATALOG["previous_period"]}:
        raise ValueError("Include expense transactions for both September and October 2026.")
    return result


def read_pdf(data: bytes, filename: str) -> dict:
    if len(data) > 2_000_000 or not data.startswith(b"%PDF-"):
        raise ValueError("Choose a readable PDF under 2 MB.")
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted or not 1 <= len(reader.pages) <= 10:
            raise ValueError("Use an unencrypted PDF with 1–10 pages.")
        pages = [p.extract_text() or "" for p in reader.pages]
    except ValueError:
        raise
    except Exception:
        raise ValueError("This PDF could not be read.") from None
    if not any(p.strip() for p in pages) or sum(map(len, pages)) > 12_000:
        raise ValueError("Use a text-based PDF with fewer than 12,000 extracted characters. Scanned images require OCR.")
    fields = {}
    for i, page in enumerate(pages, 1):
        for line in page.splitlines():
            if ": " in line:
                key, value = line.split(": ", 1)
                if key in fields:
                    raise ValueError(f"The PDF contains an ambiguous {key} field.")
                fields[key] = {"value": value.strip(), "page": i, "quote": line}
    for key in ["Document ID", "Entity", "Document type"]:
        if key not in fields or not fields[key]["value"]:
            raise ValueError(f"The PDF needs a labeled {key} field, as in the sample files.")
    identifier = fields["Document ID"]["value"]
    if not re.fullmatch(r"[A-Za-z0-9-]{1,64}", identifier):
        raise ValueError("The document ID is invalid.")
    return {"id": identifier, "filename": Path(filename).name, "kind": fields["Document type"]["value"], "pages": pages, "fields": fields, "sha256": hashlib.sha256(data).hexdigest()}


def value(document: dict, key: str) -> str:
    try:
        return document["fields"][key]["value"]
    except KeyError:
        raise ValueError(f"{document.get('id', 'Document')} is missing the {key} field.") from None


class Workspace:
    def __init__(self, directory: Path, ledger: bytes | None = None):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(directory / "workspace.db", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS transactions (id TEXT PRIMARY KEY, date TEXT, account TEXT, vendor TEXT, description TEXT, currency TEXT, document_id TEXT, amount_cents INTEGER);
            CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, record TEXT NOT NULL, pdf BLOB NOT NULL);
            CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, account TEXT, created_at TEXT, error TEXT);
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT);
        """)
        if not self.conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]:
            data = ledger if ledger is not None else (SAMPLES / "ledger.csv").read_bytes()
            records = parse_ledger(data)
            with self.conn:
                self.conn.executemany("INSERT INTO transactions VALUES (:id,:date,:account,:vendor,:description,:currency,:document_id,:amount_cents)", records)
                self.conn.execute("INSERT OR REPLACE INTO metadata VALUES ('ledger_sha256',?)", (hashlib.sha256(data).hexdigest(),))
            for doc in CATALOG["documents"].values():
                if doc["available"]:
                    self.save_document((SAMPLES / doc["file"]).read_bytes(), doc["file"])
        self.ledger_hash = self.conn.execute("SELECT value FROM metadata WHERE key='ledger_sha256'").fetchone()[0]

    def query(self, sql: str, args=()) -> list[dict]:
        if not sql.lstrip().upper().startswith("SELECT "):
            raise ValueError("Only scoped read queries are permitted.")
        return [dict(row) for row in self.conn.execute(sql, args).fetchall()]

    def accounts(self) -> list[dict]:
        rows = self.query("SELECT account, substr(date,1,7) period, SUM(amount_cents) total FROM transactions GROUP BY account, period")
        result = []
        for code, name in CATALOG["accounts"].items():
            totals = {r["period"]: r["total"] for r in rows if r["account"] == code}
            previous, current = totals.get(CATALOG["previous_period"], 0), totals.get(CATALOG["period"], 0)
            delta = current - previous
            ratio = abs(Decimal(delta) / previous) if previous else None
            material = abs(delta) >= cents(CATALOG["materiality"]) and (ratio is None or ratio >= Decimal(CATALOG["percentage_threshold"]))
            result.append({"code": code, "name": name, "previous_cents": previous, "current_cents": current, "change_cents": delta, "change_ratio": float(ratio) if ratio is not None else None, "material": material})
        return result

    def account(self, code):
        try:
            return next(r for r in self.accounts() if r["code"] == code)
        except StopIteration:
            raise ValueError("Unknown account.") from None

    def ledger_rows(self, account, period):
        if account not in CATALOG["accounts"] or period not in {CATALOG["period"], CATALOG["previous_period"]}:
            raise ValueError("The ledger query is outside this close.")
        return self.query("SELECT * FROM transactions WHERE account=? AND substr(date,1,7)=? ORDER BY ABS(amount_cents) DESC,id", (account, period))

    def drivers(self, account):
        current = self.ledger_rows(account, CATALOG["period"])
        previous = self.ledger_rows(account, CATALOG["previous_period"])
        baseline = {(r["vendor"], r["description"], r["amount_cents"]) for r in previous}
        return [r for r in current if (r["vendor"], r["description"], r["amount_cents"]) not in baseline]

    def document(self, identifier):
        row = self.conn.execute("SELECT record FROM documents WHERE id=?", (identifier,)).fetchone()
        return json.loads(row[0]) if row else None

    def pdf(self, identifier):
        row = self.conn.execute("SELECT pdf FROM documents WHERE id=?", (identifier,)).fetchone()
        if not row:
            raise ValueError("Document not found.")
        return row[0]

    def save_document(self, data, filename):
        record = read_pdf(data, filename)
        with self.conn:
            self.conn.execute("INSERT OR REPLACE INTO documents VALUES (?,?,?)", (record["id"], json.dumps(record), data))
        return record

    def ledger_source(self, account):
        return {"id": "LEDGER-" + self.ledger_hash[:10] + "-" + account, "kind": "Ledger query", "title": "September and October expense entries", "ledger_sha256": self.ledger_hash, "rows": self.ledger_rows(account, CATALOG["previous_period"]) + self.ledger_rows(account, CATALOG["period"])}
