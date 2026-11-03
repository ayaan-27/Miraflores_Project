"""A readable review artifact generated from the persisted case, not model HTML."""

from datetime import datetime
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph


def render_workpaper(run: dict) -> bytes:
    fonts = Path(reportlab.__file__).parent / "fonts"
    if "ReviewSans" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("ReviewSans", str(fonts / "Vera.ttf")))
        pdfmetrics.registerFont(TTFont("ReviewSansBold", str(fonts / "VeraBd.ttf")))
        pdfmetrics.registerFontFamily(
            "ReviewSans", normal="ReviewSans", bold="ReviewSansBold"
        )
    body = ParagraphStyle(
        "body", fontName="ReviewSans", fontSize=9.5, leading=14, spaceAfter=8
    )
    heading = ParagraphStyle(
        "heading",
        parent=body,
        fontName="ReviewSansBold",
        fontSize=11,
        spaceBefore=13,
        spaceAfter=8,
        keepWithNext=True,
    )
    title = ParagraphStyle(
        "title", parent=heading, fontSize=17, leading=22, spaceAfter=12
    )
    small = ParagraphStyle(
        "small",
        parent=body,
        fontSize=8,
        leading=12,
        textColor=colors.HexColor("#626b61"),
    )
    output = BytesIO()
    story = []

    def text(value, style=body):
        story.append(Paragraph(escape(str(value)).replace("\n", "<br/>"), style))

    text("LedgerLens — Invoice Investigation Workpaper", title)
    invoice = run["invoice"]
    controls = run["controls"]
    text(
        f"Vendor: {invoice['vendor']['value']} | Invoice: {invoice['invoice_number']['value']}"
    )
    text(
        f"Purchase order: {invoice['po_number']['value']} | Invoice amount: USD {controls['invoice_amount']} | Round: {run['round']}"
    )
    text(
        f"Run: {run['id']} | Status: {run['status']} | Model: {run['model']} ({run['mode']})",
        small,
    )
    text(
        "Generated: "
        + datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M %Z"),
        small,
    )
    text(
        "Demonstration system records and policies are synthetic. This workpaper is a review artifact, not a completed audit, an authenticated approval, or a payment instruction.",
        small,
    )

    text("1. Computed recommendation", heading)
    text("HOLD" if controls["recommendation"] == "hold" else "READY FOR HUMAN REVIEW")
    text(
        f"Receiving-supported value: USD {controls['receiving_supported_amount']}. Value without receiving support: USD {controls['unsupported_amount']}."
    )
    text(controls["notice"], small)
    if run.get("completion"):
        text("Human outcome: " + run["completion"]["result"].replace("_", " "))

    text("2. Financial controls and source references", heading)
    for finding in controls["findings"]:
        text(f"{finding['title']} — {finding['result'].upper()}", heading)
        text(finding["detail"])
        text("Sources: " + ", ".join(finding["source_ids"]), small)

    if run.get("memo"):
        text("3. Model-drafted review narrative", heading)
        text(run["memo"]["summary"])
        for finding in run["memo"]["findings"]:
            text(finding["title"], heading)
            text(finding["explanation"])
            text("Sources: " + ", ".join(finding["source_ids"]), small)
        text(
            "Source-ID existence and the control recommendation were checked in code. Narrative interpretation still requires human review.",
            small,
        )
        text("Evidence request draft (not sent)", heading)
        text(run["memo"]["client_request"])

    text("4. Reviewer history", heading)
    if not run["review_history"]:
        text("No reviewer decision has been recorded.")
    for decision in run["review_history"]:
        text(
            f"Round {decision['round']}: {decision['reviewer']} — {decision['action'].replace('_', ' ')}"
        )
        text(decision["note"])
        text(decision["at"], small)
    text(
        "Reviewer names are entered in an unauthenticated demonstration session; this is not a verified identity or immutable audit log.",
        small,
    )

    text("5. Evidence register", heading)
    for identifier, source in controls["sources"].items():
        text(
            f"{identifier} — {source['kind'].replace('_', ' ')} — {source['title']}",
            small,
        )
    text(
        "The JSON review pack contains the detailed source metadata, extraction quotes, tool inputs and outputs, and recorded events. Original PDFs remain available from this workspace's Evidence view.",
        small,
    )

    def footer(canvas, doc):
        canvas.setFont("ReviewSans", 8)
        canvas.setFillColor(colors.HexColor("#626b61"))
        canvas.drawString(
            46, 26, "LedgerLens | Review artifact | No payment or message initiated"
        )
        canvas.drawRightString(letter[0] - 46, 26, str(doc.page))

    document = SimpleDocTemplate(
        output,
        pagesize=letter,
        leftMargin=46,
        rightMargin=46,
        topMargin=42,
        bottomMargin=48,
        title="Invoice Investigation Workpaper",
        author="LedgerLens",
    )
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
