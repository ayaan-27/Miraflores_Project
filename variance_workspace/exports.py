from io import BytesIO, StringIO
import csv
from html import escape
from pathlib import Path
import json

import reportlab
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

from .data import CATALOG, dollars


def journal_csv(state):
    output = StringIO(); writer = csv.writer(output)
    writer.writerow(["period", "account", "name", "debit", "credit", "status"])
    for row in state["analysis"]["journal"]:
        writer.writerow([CATALOG["period"], row["account"], row["name"], dollars(row["debit_cents"]), dollars(row["credit_cents"]), "DRAFT - NOT POSTED"])
    return output.getvalue().encode()


def review_json(state):
    return json.dumps({"sample_data": True, "entity": CATALOG["entity"], "period": CATALOG["period"], "notice": "Reviewer names are entered, not authenticated. No entry has been posted. This is not an immutable audit record.", **state}, indent=2).encode()


def workpaper(state):
    if "CloseSans" not in pdfmetrics.getRegisteredFontNames():
        font_dir = Path(reportlab.__file__).parent / "fonts"
        pdfmetrics.registerFont(TTFont("CloseSans", str(font_dir / "Vera.ttf")))
        pdfmetrics.registerFont(TTFont("CloseSansBold", str(font_dir / "VeraBd.ttf")))
    normal = ParagraphStyle("body", fontName="CloseSans", fontSize=10, leading=15, spaceAfter=8)
    heading = ParagraphStyle("heading", parent=normal, fontName="CloseSansBold", fontSize=12, spaceBefore=10, spaceAfter=8)
    title = ParagraphStyle("title", parent=heading, fontSize=17, leading=22)
    story = []
    def add(value, style=normal): story.append(Paragraph(escape(str(value)).replace("\n", "<br/>"), style))
    a = state["analysis"]; account = a["account"]
    add("Month-end review | " + account["name"], title)
    add(f"Entity: {CATALOG['entity']} | Period: {CATALOG['period']} | USD")
    add("Sample documents and transactions. Accounting treatments follow the supplied illustrative close policy. Document authenticity and reviewer identity are not verified.")
    add(f"September: {dollars(account['previous_cents'])} | October: {dollars(account['current_cents'])} | Change: {dollars(account['change_cents'])}")
    add("Conclusion", heading)
    add(a["outcome"].replace("_", " ").capitalize())
    if state.get("memo"):
        add(state["memo"]["summary"])
        add("Explanation sources: " + ", ".join(state["memo"]["source_ids"]))
    for check in a["findings"]:
        add(check["name"] + (" - consistent" if check["passed"] else " - unresolved"), heading)
        add(check["detail"]); add("Sources: " + ", ".join(check["source_ids"]))
    if a["journal"]:
        add("Proposed journal | not posted", heading)
        for row in a["journal"]:
            add(f"{row['account']} {row['name']}: debit USD {dollars(row['debit_cents'])}; credit USD {dollars(row['credit_cents'])}")
        add(f"Account balance after the proposed adjustment: USD {dollars(a['adjusted_cents'])}.")
    if a["allocation"]:
        add("Allocation schedule", heading)
        for row in a["allocation"]: add(f"{row['period']}: USD {dollars(row['expense_cents'])}")
    add("Reviewer history", heading)
    for item in state.get("history", []):
        add(f"{item['reviewer']} | {item['action'].replace('_',' ')} | round {item['round']} | {item['at']}")
        add(item["note"])
    if not state.get("history"): add("No reviewer decision has been recorded.")
    add("Evidence register", heading)
    for identifier, source in a["sources"].items():
        add(identifier + " | " + source.get("filename", source.get("title", "Ledger query")))
        if source.get("sha256"): add("SHA-256: " + source["sha256"])
        if source.get("ledger_sha256"): add("Ledger SHA-256: " + source["ledger_sha256"])
    add("No accounting entry, email, or external financial action has been initiated.")
    buffer = BytesIO()
    SimpleDocTemplate(buffer, pagesize=(612, 792), rightMargin=48, leftMargin=48, topMargin=42, bottomMargin=42, title="Month-end review workpaper").build(story)
    return buffer.getvalue()
