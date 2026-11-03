"""Create a standard Word submission and export the same document to PDF.

Optional document tooling: python-docx==1.2.0 and LibreOffice (soffice).
Neither is required to run the LedgerLens application.
"""

from pathlib import Path
import argparse
import re
import shutil
import subprocess
import tempfile

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--input", default="docs/written-submission.md")
arguments = parser.parse_args()
INPUT_PATH = ROOT / arguments.input
DOCX_PATH = INPUT_PATH.with_suffix(".docx")
PDF_PATH = INPUT_PATH.with_suffix(".pdf")
FONT = "Arial"


def add_hyperlink(paragraph, url):
    """Use a real Word hyperlink so both the DOCX and exported PDF are clickable."""
    relationship = paragraph.part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), relationship)
    run = OxmlElement("w:r")
    properties = OxmlElement("w:rPr")
    style = OxmlElement("w:rStyle")
    style.set(qn("w:val"), "Hyperlink")
    properties.append(style)
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "0563C1")
    properties.append(color)
    run.append(properties)
    text = OxmlElement("w:t")
    text.text = url
    run.append(text)
    link.append(run)
    paragraph._p.append(link)


def add_inline(paragraph, text):
    for index, segment in enumerate(re.split(r"\*\*(.*?)\*\*", text)):
        if index % 2:
            paragraph.add_run(segment).bold = True
        else:
            for part in re.split(r"(https://[^\s]+)", segment):
                if part.startswith("https://"):
                    add_hyperlink(paragraph, part)
                elif part:
                    paragraph.add_run(part)


document = Document()
section = document.sections[0]
section.page_width = Inches(8.5)
section.page_height = Inches(11)
section.top_margin = section.bottom_margin = Inches(1)
section.left_margin = section.right_margin = Inches(1)
section.footer_distance = Inches(0.5)

for name, size, bold in [
    ("Normal", 11, False),
    ("Title", 16, True),
    ("Heading 1", 12, True),
]:
    style = document.styles[name]
    style.font.name = FONT
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.color.rgb = RGBColor(0, 0, 0)
    properties = style._element.get_or_add_rPr()
    fonts = properties.rFonts
    for key in list(fonts.attrib):
        if "theme" in key.lower():
            del fonts.attrib[key]
    fonts.set(qn("w:eastAsia"), FONT)
    # Clear decorative defaults inherited from the installed Word template.
    for key in ["spacing", "kern"]:
        for element in properties.findall(qn("w:" + key)):
            properties.remove(element)
    paragraph_properties = style._element.get_or_add_pPr()
    for border in paragraph_properties.findall(qn("w:pBdr")):
        paragraph_properties.remove(border)
    paragraph_format = style.paragraph_format
    paragraph_format.line_spacing = 1.15
    paragraph_format.space_after = Pt(6)
    paragraph_format.widow_control = True

document.styles["Title"].paragraph_format.space_after = Pt(8)
heading_format = document.styles["Heading 1"].paragraph_format
heading_format.space_before = Pt(12)
heading_format.space_after = Pt(6)
heading_format.keep_with_next = True

content = INPUT_PATH.read_text(encoding="utf-8")
for block in content.strip().split("\n\n"):
    block = block.strip()
    if block.startswith("# "):
        lines = block.splitlines()
        document.add_paragraph(lines[0][2:], "Title")
        for line in lines[1:]:
            add_inline(document.add_paragraph(), line)
    elif block.startswith("## "):
        document.add_paragraph(block[3:], "Heading 1")
    else:
        add_inline(document.add_paragraph(), block.replace("\n", " "))

footer = section.footer.paragraphs[0]
footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = footer.add_run()
run.font.name = FONT
run.font.size = Pt(9)
field = OxmlElement("w:fldSimple")
field.set(qn("w:instr"), "PAGE")
run._r.addnext(field)

document.core_properties.title = content.splitlines()[0].removeprefix("# ")
document.core_properties.author = "Ayaan Khan"
document.core_properties.subject = (
    "MiraFlores case study submission for GreenGrowth CPAs"
)
document.core_properties.comments = ""
document.save(DOCX_PATH)
print(DOCX_PATH)

soffice = shutil.which("soffice") or shutil.which("libreoffice")
if not soffice:
    raise SystemExit("DOCX created. Install LibreOffice to export the matching PDF.")

with tempfile.TemporaryDirectory(prefix="ledgerlens-word-") as temp:
    temporary = Path(temp)
    subprocess.run(
        [
            soffice,
            f"-env:UserInstallation={temporary.joinpath('profile').as_uri()}",
            "--headless",
            "--convert-to",
            "pdf:writer_pdf_Export",
            "--outdir",
            str(temporary),
            str(DOCX_PATH),
        ],
        check=True,
        timeout=60,
    )
    generated = temporary / PDF_PATH.name
    if not generated.exists() or generated.stat().st_size == 0:
        raise SystemExit(
            "Word export did not produce a PDF; the previous PDF was preserved."
        )
    shutil.copyfile(generated, PDF_PATH)
print(PDF_PATH)
