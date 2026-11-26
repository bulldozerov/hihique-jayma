"""Convert a Markdown specification to JSON blocks with source line ranges."""

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from markdown_it import MarkdownIt


@dataclass
class DocumentBlock:
    id: str
    kind: str
    section: list[str]
    start_line: int
    end_line: int
    text: str
    source: str


def parse_markdown(markdown: str) -> list[DocumentBlock]:
    """Return blocks in source order, with one-based inclusive line ranges."""
    markdown = markdown.replace("\r\n", "\n").replace("\r", "\n")
    lines = markdown.split("\n")
    tokens = MarkdownIt("commonmark").enable("table").parse(markdown)
    blocks: list[DocumentBlock] = []
    headings: list[tuple[int, str]] = []
    columns: list[str] = []
    list_depth = 0

    def add_block(kind: str, line_map: list[int], content: str) -> None:
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
                columns = cells
                add_block("table_header", token.map, " | ".join(columns))
            else:
                content = "\n".join(
                    f"{column}: {cell}"
                    for column, cell in zip(columns, cells, strict=True)
                )
                add_block("table_row", token.map, content)
        elif token.type in {"fence", "code_block", "html_block"}:
            kind = "html" if token.type == "html_block" else "code"
            add_block(kind, token.map, token.content)

    return blocks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Markdown specification")
    parser.add_argument("--output", type=Path, help="Write JSON to this file")
    args = parser.parse_args()
    if args.input.suffix.lower() != ".md":
        parser.error("Expected a .md input file")
    if args.output and args.output.resolve() == args.input.resolve():
        parser.error("The output file must differ from the input file")

    try:
        blocks = parse_markdown(args.input.read_text(encoding="utf-8-sig"))
        output = json.dumps([asdict(block) for block in blocks], ensure_ascii=False, indent=2)
        if args.output:
            args.output.write_text(output + "\n", encoding="utf-8")
        else:
            sys.stdout.reconfigure(encoding="utf-8")
            print(output)
    except (OSError, UnicodeError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
