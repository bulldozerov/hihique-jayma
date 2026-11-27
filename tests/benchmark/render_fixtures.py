"""Render the three plain-text Markdown fixtures as PDFs with a text layer."""

from html import escape
from pathlib import Path

from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate


def main():
    fonts = Path("C:/Windows/Fonts")
    pdfmetrics.registerFont(TTFont("FixtureBody", str(fonts / "arial.ttf")))
    pdfmetrics.registerFont(TTFont("FixtureBold", str(fonts / "arialbd.ttf")))
    styles = {
        level: ParagraphStyle(
            f"fixture-{level}",
            fontName="FixtureBold" if level else "FixtureBody",
            fontSize=size,
            leading=size + 4,
            spaceBefore=10 if level else 0,
            spaceAfter=9,
        )
        for level, size in enumerate((11, 22, 16, 11))
    }
    for source in sorted(Path(__file__).with_name("fixtures").glob("*.md")):
        story = []
        for line in source.read_text(encoding="utf-8-sig").splitlines():
            if line.strip():
                level = len(line) - len(line.lstrip("#"))
                story.append(Paragraph(escape(line[level:].strip()), styles[level]))
        SimpleDocTemplate(str(source.with_suffix(".pdf")), invariant=True).build(story)


if __name__ == "__main__":
    main()
