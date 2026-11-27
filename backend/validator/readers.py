"""Read Markdown and PDF specifications as blocks with source locations."""

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class DocumentBlock:
    id: str
    kind: str
    section: list[str]
    start_line: int
    end_line: int
    text: str
    source: str
    page: int | None = None
    cells: dict[str, str] | None = None
    role: str | None = None
    continuation_of: str | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        if self.page is None:
            del data["page"]
        for field in ("cells", "role", "continuation_of"):
            if data[field] is None:
                del data[field]
        return data


def read_document(path: Path) -> list[DocumentBlock]:
    if path.suffix.lower() == ".md":
        return parse_markdown(path.read_text(encoding="utf-8-sig"))
    if path.suffix.lower() == ".pdf":
        return parse_pdf(path)
    raise ValueError("Expected a .md or .pdf input file")


def _pdf_acceptance_rows(source: str, baselines: list[tuple[float, str]]):
    lines = source.splitlines()
    if len(lines) < 4:
        return []
    header = re.fullmatch(
        r"\s*Исходные(?: условия)?\s{2,}(?P<action>Действие)\s{2,}"
        r"(?P<result>Ожидаемый(?: результат)?)\s*",
        lines[0],
        re.IGNORECASE,
    )
    if not header:
        return []
    action, result = header.start("action"), header.start("result")
    columns = ("Исходные условия", "Действие", "Ожидаемый результат")
    header_lines = 1
    if not lines[0].strip().endswith("результат"):
        if lines[1][:action].strip() != "условия" or lines[1][result:].strip() != "результат":
            return []
        header_lines = 2

    # Match layout lines to PDF baselines before using gaps to distinguish
    # separate rows from wrapped lines. Fall back if the mapping is ambiguous.
    compact = ["".join(line.split()) for line in lines]
    baseline_text = [line for _, line in baselines]
    starts = [
        i for i in range(len(baselines) - len(lines) + 1)
        if baseline_text[i:i + len(lines)] == compact
    ]
    if len(starts) != 1:
        return []
    heights = [y for y, _ in baselines[starts[0]:starts[0] + len(lines)]]
    gaps = [b - a for a, b in zip(heights, heights[1:])]
    if not gaps or min(gaps) <= 0:
        return []
    row_starts = [i for i, gap in enumerate(gaps, 1) if gap > min(gaps) * 1.3]
    if not row_starts or row_starts[0] != header_lines:
        return []

    rows = []
    for start, end in zip(row_starts, row_starts[1:] + [len(lines)]):
        spans = [(line[:action], line[action:result], line[result:]) for line in lines[start:end]]
        if not all(cell.strip() for cell in spans[0]):
            return []
        cells = {
            name: " ".join(cell.strip() for cell in values if cell.strip())
            for name, values in zip(columns, zip(*spans))
        }
        rows.append((start, end, cells))
    return rows


def _pdf_table_rows(source: str, baselines: list[tuple[float, str]]):
    lines = source.splitlines()
    if len(lines) < 3:
        return []
    columns = list(re.finditer(r"\S(?:.*?\S)?(?=\s{2,}|$)", lines[0]))
    if len(columns) < 2:
        return []
    names = tuple(match.group() for match in columns)
    starts = [match.start() for match in columns]
    ends = starts[1:] + [None]
    compact = ["".join(line.split()) for line in lines]
    baseline_text = [line for _, line in baselines]
    matches = [
        i for i in range(len(baselines) - len(lines) + 1)
        if baseline_text[i:i + len(lines)] == compact
    ]
    if len(matches) != 1:
        return []
    heights = [y for y, _ in baselines[matches[0]:matches[0] + len(lines)]]
    gaps = [b - a for a, b in zip(heights, heights[1:])]
    if not gaps or min(gaps) <= 0:
        return []

    def split_line(line):
        return [line[start:end].strip() for start, end in zip(starts, ends)]

    # Use only recognized table headers. Column boundaries come from the PDF.
    headers = {
        ("Поле", "Значение"),
        ("Parameter", "Format", "Size", "Mandatory", "Logic", "Description", "DB field"),
        ("Parameter", "Format", "Logic", "Description", "DB field"),
    }
    names = tuple(name.replace("ﬁ", "fi") for name in names)
    if names not in headers:
        return []
    row_starts = [i for i, gap in enumerate(gaps, 1) if gap > min(gaps) * 1.3]
    if not row_starts:
        row_starts = list(range(1, len(lines)))
    if row_starts[0] != 1:
        return []
    rows = []
    for start, end in zip(row_starts, row_starts[1:] + [len(lines)]):
        spans = [split_line(line) for line in lines[start:end]]
        if not all(spans[0][:2]):
            return []
        cells = {
            name: " ".join(value for value in values if value)
            for name, values in zip(names, zip(*spans))
        }
        rows.append((start, end, cells))
    return rows


def _pdf_layout_spans(text, line_styles, body_size):
    start = None
    lines = []
    rank = None
    for line_number, line in enumerate(text.splitlines(), start=1):
        styles = line_styles.get("".join(line.split()), set())
        heading_rank = None
        if len(styles) == 1:
            size, bold = next(iter(styles))
            if (
                size > body_size * 1.05
                or (bold and size >= body_size and line == line.lstrip() and not line.strip().isdigit())
            ):
                heading_rank = size
        if lines and (not line.strip() or heading_rank != rank):
            yield start, "\n".join(lines), rank
            lines = []
        if line.strip():
            if not lines:
                start, rank = line_number, heading_rank
            lines.append(line)
    if lines:
        yield start, "\n".join(lines), rank


def parse_pdf(path: Path) -> list[DocumentBlock]:
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError

    blocks: list[DocumentBlock] = []
    headings: list[tuple[float, str]] = []
    try:
        with path.open("rb") as stream:
            document = PdfReader(stream)
            page_layouts = []
            font_sizes = Counter()
            for page_number, page in enumerate(document.pages, start=1):
                text = page.extract_text(extraction_mode="layout")
                fragments: dict[float, list[tuple[float, str]]] = {}
                line_styles: dict[str, set[tuple[float, bool]]] = {}

                def collect(fragment, matrix, position, font, size):
                    compact = "".join(fragment.split())
                    if compact:
                        x, y = position[4:6]
                        x, y = (
                            x * matrix[0] + y * matrix[2] + matrix[4],
                            x * matrix[1] + y * matrix[3] + matrix[5],
                        )
                        y = round(y, 1)
                        fragments.setdefault(y, []).append((x, compact))
                        effective_size = round(size * (matrix[2] ** 2 + matrix[3] ** 2) ** 0.5, 2)
                        font_sizes[effective_size] += len(compact)
                        bold = "bold" in str(font.get("/BaseFont", "") if font else "").lower()
                        line_styles.setdefault(compact, set()).add((effective_size, bold))

                page.extract_text(visitor_text=collect)
                baselines = [
                    (y, "".join(fragment for _, fragment in sorted(parts)))
                    for y, parts in sorted(fragments.items())
                ]
                # PDF transformations can make the y-coordinate increase or decrease
                # down the page. Table matching uses the order of the layout text.
                page_layouts.append((page_number, text, baselines, line_styles))

            body_size = font_sizes.most_common(1)[0][0] if font_sizes else 0
            for page_number, text, baselines, line_styles in page_layouts:
                reverse_baselines = [(-y, line) for y, line in reversed(baselines)]
                for start_line, source, size in _pdf_layout_spans(text, line_styles, body_size):
                    if size is not None:
                        title = " ".join(source.split())
                        while headings and headings[-1][0] <= size:
                            headings.pop()
                        headings.append((size, title))
                        blocks.append(DocumentBlock(
                            f"B{len(blocks) + 1:03d}", "heading",
                            [title for _, title in headings], start_line,
                            start_line + source.count("\n"), title, source, page_number,
                        ))
                        continue
                    section = [title for _, title in headings]
                    rows = _pdf_acceptance_rows(source, baselines) or _pdf_acceptance_rows(source, reverse_baselines)
                    role = "acceptance_case" if rows else None
                    if not rows:
                        rows = _pdf_table_rows(source, baselines) or _pdf_table_rows(source, reverse_baselines)
                    if rows:
                        lines = source.splitlines()
                        header_end = rows[0][0]
                        blocks.append(DocumentBlock(
                            f"B{len(blocks) + 1:03d}", "table_header", section,
                            start_line, start_line + header_end - 1,
                            " | ".join(rows[0][2]), "\n".join(lines[:header_end]), page_number,
                        ))
                        for start, end, cells in rows:
                            blocks.append(DocumentBlock(
                                f"B{len(blocks) + 1:03d}", "table_row", section,
                                start_line + start, start_line + end - 1,
                                "\n".join(f"{key}: {value}" for key, value in cells.items()),
                                "\n".join(lines[start:end]), page_number, cells, role,
                            ))
                        continue
                    items = list(re.finditer(r"(?m)^[ \t]*(?:[•●▪]\s+|\d+\.[ \t]+)", source))
                    if items and items[0].start() == 0:
                        for item, end in zip(items, [m.start() for m in items[1:]] + [len(source)]):
                            span = source[item.start():end].rstrip("\r\n")
                            line = start_line + source.count("\n", 0, item.start())
                            content = re.sub(r"^[ \t]*[•●▪][ \t]+", "", span)
                            blocks.append(DocumentBlock(
                                id=f"B{len(blocks) + 1:03d}", kind="list_item", section=section,
                                start_line=line, end_line=line + span.count("\n"),
                                text=" ".join(content.split()), source=span, page=page_number,
                            ))
                        continue
                    previous = blocks[-1] if blocks else None
                    continuation = (
                        previous.id if previous and previous.kind == "list_item"
                        and previous.page == page_number - 1
                        and previous.text[-1:] not in ".!?:;"
                        and source.lstrip()[:1].islower()
                        else None
                    )
                    blocks.append(
                        DocumentBlock(
                            id=f"B{len(blocks) + 1:03d}",
                            kind="continuation" if continuation else "pdf_text",
                            section=section,
                            start_line=start_line,
                            end_line=start_line + source.count("\n"),
                            text=source,
                            source=source,
                            page=page_number,
                            continuation_of=continuation,
                        )
                    )
    except PyPdfError as error:
        raise ValueError(f"Could not read PDF: {error}") from error
    if not blocks:
        raise ValueError("PDF has no extractable text. Use a PDF with a text layer.")
    return blocks


def parse_markdown(markdown: str) -> list[DocumentBlock]:
    """Return blocks in source order, with one-based inclusive line ranges."""
    from markdown_it import MarkdownIt

    markdown = markdown.replace("\r\n", "\n").replace("\r", "\n")
    lines = markdown.split("\n")
    tokens = MarkdownIt("commonmark").enable("table").parse(markdown)
    blocks: list[DocumentBlock] = []
    headings: list[tuple[int, str]] = []
    columns: list[str] = []
    list_depth = 0

    def add_block(
        kind: str, line_map: list[int], content: str, cells: dict[str, str] | None = None
    ) -> None:
        role = None
        if kind == "table_row" and cells and set(cells) == {
            "Исходные условия", "Действие", "Ожидаемый результат"
        }:
            role = "acceptance_case"
        start, end = line_map
        blocks.append(
            DocumentBlock(
                id=f"B{len(blocks) + 1:03d}",
                kind=kind,
                section=[title for _, title in headings],
                start_line=start + 1,
                end_line=end,
                text=content,
                source="\n".join(lines[start:end]),
                cells=cells,
                role=role,
            )
        )

    for index, token in enumerate(tokens):
        if token.type == "list_item_open":
            list_depth += 1
        elif token.type == "list_item_close":
            list_depth -= 1
        elif token.map is None:
            continue
        elif token.type == "heading_open":
            level = int(token.tag[1:])
            title = tokens[index + 1].content
            while headings and headings[-1][0] >= level:
                headings.pop()
            headings.append((level, title))
            add_block("heading", token.map, title)
        elif token.type == "paragraph_open":
            kind = "list_item" if list_depth else "paragraph"
            add_block(kind, token.map, tokens[index + 1].content)
        elif token.type == "tr_open":
            cells = []
            for cell_index in range(index + 1, len(tokens)):
                cell_token = tokens[cell_index]
                if cell_token.type == "tr_close":
                    break
                if cell_token.type == "inline":
                    cells.append(cell_token.content)

            if tokens[index + 1].type == "th_open":
                columns = []
                for position, cell in enumerate(cells, start=1):
                    title = " ".join(cell.replace("**", "").split()) or f"Колонка {position}"
                    if title in columns:
                        title = f"{title} ({position})"
                        while title in columns:
                            title += "*"
                    columns.append(title)
                add_block("table_header", token.map, " | ".join(columns))
            else:
                content = "\n".join(
                    f"{column}: {cell}"
                    for column, cell in zip(columns, cells, strict=True)
                )
                add_block("table_row", token.map, content, dict(zip(columns, cells, strict=True)))
        elif token.type in {"fence", "code_block", "html_block"}:
            kind = "html" if token.type == "html_block" else "code"
            add_block(kind, token.map, token.content)

    return blocks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Markdown or PDF specification")
    parser.add_argument("--output", type=Path, help="Write JSON to this file")
    args = parser.parse_args()
    if args.output and args.output.resolve() == args.input.resolve():
        parser.error("The output file must differ from the input file")

    try:
        blocks = read_document(args.input)
        output = json.dumps([block.to_dict() for block in blocks], ensure_ascii=False, indent=2)
        if args.output:
            args.output.write_text(output + "\n", encoding="utf-8")
        else:
            sys.stdout.reconfigure(encoding="utf-8")
            print(output)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
