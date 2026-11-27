"""Render the CLI report to a searchable A4 PDF."""

from html import escape
import os
from pathlib import Path

from markdown_it import MarkdownIt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import CondPageBreak, LongTable, PageBreak, Paragraph, SimpleDocTemplate, Spacer


def _register_fonts() -> None:
    candidates = (
        (Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts", "times.ttf", "timesbd.ttf"),
        (Path("/usr/share/fonts/truetype/liberation2"), "LiberationSerif-Regular.ttf", "LiberationSerif-Bold.ttf"),
        (Path("/usr/share/fonts/truetype/liberation"), "LiberationSerif-Regular.ttf", "LiberationSerif-Bold.ttf"),
        (Path("/System/Library/Fonts/Supplemental"), "Times New Roman.ttf", "Times New Roman Bold.ttf"),
        (Path("/usr/share/fonts/truetype/dejavu"), "DejaVuSerif.ttf", "DejaVuSerif-Bold.ttf"),
    )
    for directory, regular, bold in candidates:
        if (directory / regular).is_file() and (directory / bold).is_file():
            pdfmetrics.registerFont(TTFont("ReportSerif", str(directory / regular)))
            pdfmetrics.registerFont(TTFont("ReportBold", str(directory / bold)))
            pdfmetrics.registerFontFamily("ReportSerif", normal="ReportSerif", bold="ReportBold")
            pdfmetrics.registerFontFamily("ReportBold", normal="ReportBold", bold="ReportBold")
            return
    raise ValueError("Для экспорта PDF нужен шрифт Times New Roman, Liberation Serif или DejaVu Serif.")


def write_pdf(markdown: str, output: Path) -> None:
    _register_fonts()
    tokens = MarkdownIt("commonmark").enable("table").parse(markdown)
    body = ParagraphStyle("ReportBody", fontName="ReportSerif", fontSize=11, leading=14, spaceAfter=6)
    heading = ParagraphStyle("ReportHeading", parent=body, fontName="ReportBold", fontSize=16,
                             leading=20, spaceBefore=12, keepWithNext=True)
    title = ParagraphStyle("ReportTitle", parent=heading, fontSize=26, leading=32, spaceAfter=26)
    subheading = ParagraphStyle("ReportSubheading", parent=heading, fontSize=12, leading=15)
    table_heading = ParagraphStyle("ReportTableHeading", parent=heading, keepWithNext=False)
    quote = ParagraphStyle("ReportQuote", parent=body, leftIndent=14, textColor=colors.HexColor("#505963"))
    table_cell = ParagraphStyle("ReportCell", parent=body, fontSize=10, leading=12)
    table_header = ParagraphStyle("ReportHeader", parent=table_cell, fontName="ReportBold")
    severity_colors = {"Критично": "#a31621", "Существенно": "#751d29", "Низкий приоритет": "#465466"}
    sections = [tokens[index + 1].content for index, token in enumerate(tokens)
                if token.type == "heading_open" and token.tag == "h2"]
    story = [Spacer(1, 110), Paragraph("Отчёт о проверке требований", title), Paragraph("Оглавление", heading)]
    for index, section in enumerate(sections):
        story.append(Paragraph(f'<link href="#section-{index}">{escape(section)}</link>', body))
    story.append(PageBreak())

    section_index = 0
    quote_depth = 0
    rows = []
    row = None
    for index, token in enumerate(tokens):
        if token.type == "blockquote_open":
            quote_depth += 1
        elif token.type == "blockquote_close":
            quote_depth -= 1
        elif token.type == "tr_open":
            row = []
        elif token.type == "tr_close":
            rows.append(row)
            row = None
        elif token.type == "table_close":
            story.append(LongTable(rows, colWidths=[65, 88, A4[0] - 273], repeatRows=1, style=[
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#edf0f3")),
                ("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.HexColor("#c4c9cf")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            rows = []
        elif token.type in {"code_block", "fence"}:
            content = escape(token.content.rstrip()).replace("\n", "<br/>")
            if content:
                story.append(Paragraph(content, quote if quote_depth else body))
        elif token.type == "inline":
            previous = tokens[index - 1]
            content = escape(token.content if quote_depth else token.content.replace("**", ""))
            content = content.replace("\n", "<br/>")
            if row is not None:
                row.append(Paragraph(content, table_header if previous.type == "th_open" else table_cell))
            elif previous.type == "heading_open":
                if previous.tag == "h2":
                    before_table = tokens[index + 2].type == "table_open"
                    if before_table:
                        story.append(CondPageBreak(90))
                    story.append(Paragraph(f'<a name="section-{section_index}"/>{content}',
                                           table_heading if before_table else heading))
                    section_index += 1
                elif previous.tag == "h3":
                    story.append(Paragraph(content, subheading))
            elif content:
                for label, color in severity_colors.items():
                    if content.startswith(label):
                        content = f'<font color="{color}"><b>{label}</b></font>{content[len(label):]}'
                        break
                if not quote_depth and token.content.endswith("**") and "**" in token.content[:-2]:
                    label, value = token.content[:-2].split("**", 1)
                    content = f"{escape(label)}<b>{escape(value)}</b>"
                story.append(Paragraph(content, quote if quote_depth else body))

    def page_number(canvas, document):
        if document.page > 1:
            canvas.setFont("ReportSerif", 9)
            canvas.setFillColor(colors.HexColor("#505963"))
            canvas.drawRightString(A4[0] - 54, 30, str(document.page))

    document = SimpleDocTemplate(str(output), pagesize=A4, title="Отчёт о проверке требований",
                                 leftMargin=54, rightMargin=54, topMargin=54, bottomMargin=54)
    document.build(story, onLaterPages=page_number)
