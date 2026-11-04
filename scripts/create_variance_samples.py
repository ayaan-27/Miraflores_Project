"""Generate the small, explicitly synthetic month-end dataset and source PDFs."""
from pathlib import Path
import csv
import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

ROOT = Path(__file__).resolve().parents[1] / "variance_samples"
ROOT.mkdir(exist_ok=True)
accounts = {"6100": "Software", "6200": "Payroll", "6300": "Professional fees", "6400": "Travel"}
catalog = {"entity": "Northbank Studio", "currency": "USD", "period": "2026-10", "previous_period": "2026-09", "materiality": "5000.00", "percentage_threshold": "0.20", "accounts": accounts, "documents": {}}

def pdf(doc_id, filename, kind, fields, available=True):
    p = ROOT / filename
    c = canvas.Canvas(str(p), pagesize=letter, invariant=1)
    c.setTitle(doc_id + " | Sample data")
    c.setFont("Helvetica", 9); c.drawString(48, 752, "SAMPLE DATA - FICTIONAL ENTITY AND RECORDS")
    c.setFont("Helvetica-Bold", 19); c.drawString(48, 710, kind)
    c.setFont("Helvetica", 11)
    lines = [("Document ID", doc_id), ("Entity", catalog["entity"]), ("Document type", kind), *fields]
    for i, (label, value) in enumerate(lines): c.drawString(48, 676 - i * 25, f"{label}: {value}")
    c.save()
    catalog["documents"][doc_id] = {"id": doc_id, "file": filename, "kind": kind, "available": available}

pdf("INV-SW-102", "software-invoice.pdf", "Invoice", [("Vendor", "OrbitCloud"), ("Invoice date", "2026-10-03"), ("Amount", "24000.00"), ("Currency", "USD"), ("Description", "Annual workspace license renewal"), ("Agreement ID", "AGR-SW-2026")])
pdf("AGR-SW-2026", "software-contract.pdf", "Service agreement", [("Vendor", "OrbitCloud"), ("Invoice ID", "INV-SW-102"), ("Amount", "24000.00"), ("Currency", "USD"), ("Service start", "2026-10-01"), ("Service end", "2027-09-30"), ("Authorized", "Yes")], False)
pdf("MEMO-BONUS-OCT", "bonus-approval.pdf", "Payroll memo", [("Vendor", "PeopleOps"), ("Amount", "18000.00"), ("Currency", "USD"), ("Earned period", "2026-10"), ("Approval", "Approved"), ("Description", "One-time performance bonus")])
pdf("INV-FEE-108", "consulting-invoice.pdf", "Invoice", [("Vendor", "Northline Advisory"), ("Invoice date", "2026-10-20"), ("Amount", "8000.00"), ("Currency", "USD"), ("Description", "Additional implementation work"), ("Agreement ID", "AGR-FEE-2026")])
pdf("AGR-FEE-2026", "consulting-agreement.pdf", "Service agreement", [("Vendor", "Northline Advisory"), ("Invoice ID", "INV-FEE-108"), ("Amount", "8000.00"), ("Currency", "USD"), ("Service start", "2026-10-01"), ("Service end", "2026-10-31"), ("Authorized", "Yes")], False)
pdf("POL-CLOSE", "close-policy.pdf", "Close policy", [("Basis", "Accrual"), ("Prepaid threshold", "1200.00"), ("Allocation", "Equal monthly allocation over full calendar months"), ("Partial months", "Manual review required"), ("Bonuses", "Expense in the earned period with approval"), ("Duplicate postings", "Hold for investigation"), ("Journal posting", "Human approval required; no automatic posting")])
pdf("AGR-SW-WRONG", "wrong-contract.pdf", "Service agreement", [("Vendor", "Different Vendor"), ("Invoice ID", "INV-SW-102"), ("Amount", "24000.00"), ("Currency", "USD"), ("Service start", "2026-10-01"), ("Service end", "2027-09-30"), ("Authorized", "Yes")], False)

rows = []
def row(key, period, account, vendor, description, debit, doc):
    rows.append(dict(id=key, date=period + "-25", account=account, vendor=vendor, description=description, debit=debit, credit="0.00", currency="USD", document_id=doc))
for period, suffix in [("2026-09", "S"), ("2026-10", "O")]:
    row("SW-"+suffix+"1", period, "6100", "OrbitCloud", "Monthly workspace seats", "1200.00", "SEATS-"+suffix)
    row("SW-"+suffix+"2", period, "6100", "DevTools", "Monthly developer tools", "800.00", "TOOLS-"+suffix)
    row("PAY-"+suffix, period, "6200", "PeopleOps", "Regular payroll", "40000.00", "PAYROLL-"+suffix)
    row("FEE-"+suffix, period, "6300", "Northline Advisory", "Retainer", "6000.00", "RETAINER-"+suffix)
    row("TRV-"+suffix, period, "6400", "Travel suppliers", "Travel expense", "3200.00" if suffix=="S" else "3300.00", "TRAVEL-"+suffix)
row("SW-O3", "2026-10", "6100", "OrbitCloud", "Annual workspace license renewal", "24000.00", "INV-SW-102")
row("PAY-O2", "2026-10", "6200", "PeopleOps", "One-time performance bonus", "18000.00", "MEMO-BONUS-OCT")
row("FEE-O2", "2026-10", "6300", "Northline Advisory", "Additional implementation work", "8000.00", "INV-FEE-108")
with (ROOT / "ledger.csv").open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
with (ROOT / "invalid-ledger.csv").open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows([rows[0], rows[0]])
(ROOT / "invalid-document.pdf").write_text("This sample is deliberately not a PDF.\n")
(ROOT / "catalog.json").write_text(json.dumps(catalog, indent=2) + "\n")
print("Created the sample ledger, policy, invoices, agreements, bonus memo, and invalid inputs.")
