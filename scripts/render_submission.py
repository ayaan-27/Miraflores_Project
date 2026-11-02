"""Render the four-page written submission. Optional dependency: reportlab.
The application itself does not require Python packages.
"""
from pathlib import Path
import html
import re
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, KeepTogether
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import reportlab

fonts = Path(reportlab.__file__).parent/'fonts'
pdfmetrics.registerFont(TTFont('Vera',str(fonts/'Vera.ttf')))
pdfmetrics.registerFont(TTFont('VeraBold',str(fonts/'VeraBd.ttf')))
pdfmetrics.registerFontFamily('Vera',normal='Vera',bold='VeraBold',italic='Vera',boldItalic='VeraBold')

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'docs/written-submission.pdf'
md = (ROOT/'docs/written-submission.md').read_text()
parts = re.split(r'(?m)^## ', md)
styles = {
    'eyebrow':ParagraphStyle('eyebrow',fontName='Helvetica-Bold',fontSize=8,leading=12,textColor=colors.HexColor('#78915b'),spaceAfter=9),
    'title':ParagraphStyle('title',fontName='Helvetica-Bold',fontSize=26,leading=31,textColor=colors.HexColor('#214d3c'),spaceAfter=9),
    'subtitle':ParagraphStyle('subtitle',fontName='Helvetica',fontSize=9,leading=13,textColor=colors.HexColor('#718078'),spaceAfter=22),
    'heading':ParagraphStyle('heading',fontName='Helvetica-Bold',fontSize=17,leading=23,textColor=colors.HexColor('#214d3c'),spaceAfter=15),
    'body':ParagraphStyle('body',fontName='Vera',fontSize=10.2,leading=15,textColor=colors.HexColor('#30463a'),spaceAfter=11,alignment=TA_LEFT),
}
for style in styles.values():
    if style.fontName == 'Helvetica':style.fontName='Vera'
    if style.fontName == 'Helvetica-Bold':style.fontName='VeraBold'
def inline(text):
    text=html.escape(text)
    text=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',text)
    text=re.sub(r'`(.+?)`',r'<font name="Courier">\1</font>',text)
    # Standard PDF fonts do not contain every mathematical/arrows glyph.
    return text.replace('→','&gt;').replace('≥','&gt;=').replace('–','-').replace('—','-')

story=[]
for i,part in enumerate(parts[1:]):
    if i:story.append(PageBreak())
    story.append(Paragraph('LEDGERLENS / CANDIDATE CASE STUDY',styles['eyebrow']))
    if not i:
        story.append(Paragraph('Evidence before confidence.',styles['title']))
        story.append(Paragraph('Ayaan Khan | MiraFlores case study | Prepared for GreenGrowth CPAs',styles['subtitle']))
        story.append(Paragraph('<b>Live prototype:</b> <link href="https://ayaan-27.github.io/Miraflores_Project/" color="#214d3c">ayaan-27.github.io/Miraflores_Project/</link><br/><b>Source and README:</b> <link href="https://github.com/ayaan-27/Miraflores_Project" color="#214d3c">github.com/ayaan-27/Miraflores_Project</link>',styles['subtitle']))
    heading,content=part.split('\n',1)
    story.append(Paragraph(inline(heading),styles['heading']))
    for para in content.strip().split('\n\n'):
        story.append(Paragraph(inline(para.strip().replace('\n',' ')),styles['body']))

def decorate(canvas,doc):
    canvas.setTitle('LedgerLens - Written Submission - Ayaan Khan')
    canvas.setAuthor('Ayaan Khan (AI-assisted draft)')
    width,height=A4
    canvas.setStrokeColor(colors.HexColor('#dfe6d8'))
    canvas.line(43,42,width-43,42)
    canvas.setFont('Vera',7)
    canvas.setFillColor(colors.HexColor('#819173'))
    canvas.drawString(43,28,'Independent prototype | Synthetic data | No customer impact claimed')
    canvas.drawRightString(width-43,28,str(doc.page))

doc=SimpleDocTemplate(str(OUT),pagesize=A4,rightMargin=43,leftMargin=43,topMargin=38,bottomMargin=57)
doc.build(story,onFirstPage=decorate,onLaterPages=decorate)
print(OUT)
