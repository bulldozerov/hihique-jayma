"""Run both Gemini review passes and write the structured result."""

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from .pipeline import run_review
from .readers import read_document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Markdown or PDF specification")
    parser.add_argument("--output", required=True, type=Path, help="Review JSON file")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument(
        "--no-retries", action="store_true", help="Disable automatic Gemini retries"
    )
    parser.add_argument(
        "--max-blocks", type=int, help="Review only the first N source blocks"
    )
    args = parser.parse_args()
    if args.max_blocks is not None and args.max_blocks < 1:
        parser.error("--max-blocks must be a positive integer")
    if args.output.resolve() == args.input.resolve():
        parser.error("The output file must differ from the input file")

    load_dotenv(args.env_file)
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
    if not api_key or not model:
        parser.error("Set GEMINI_API_KEY and GEMINI_MODEL in .env or the environment")

    from .gemini import GeminiReviewer, open_client

    try:
        blocks = read_document(args.input)
        total_blocks = len(blocks)
        if args.max_blocks is not None:
            blocks = blocks[:args.max_blocks]
        with open_client(api_key, retries=not args.no_retries) as client:
            result = run_review(blocks, GeminiReviewer(client, model))
        output = {"document": args.input.name, "model": model, **result}
        if len(blocks) < total_blocks:
            output["review_scope"] = {
                "reviewed_blocks": len(blocks),
                "total_blocks": total_blocks,
            }
            if blocks[-1].page is None:
                output["review_scope"]["last_line"] = blocks[-1].end_line
            else:
                output["review_scope"]["last_page"] = blocks[-1].page
        args.output.write_text(
            json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
