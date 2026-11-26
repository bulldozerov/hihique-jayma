"""Run both Gemini review passes and write the structured result."""

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from .pipeline import run_review
from .readers import parse_markdown


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Markdown specification")
    parser.add_argument("--output", required=True, type=Path, help="Review JSON file")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()
    if args.input.suffix.lower() != ".md":
        parser.error("Expected a .md input file")
    if args.output.resolve() == args.input.resolve():
        parser.error("The output file must differ from the input file")

    load_dotenv(args.env_file)
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model = os.getenv("GEMINI_MODEL", "gemini-4-hydrogen").strip()
    if not api_key or not model:
        parser.error("Set GEMINI_API_KEY and GEMINI_MODEL in .env or the environment")

    from .gemini import GeminiReviewer, open_client

    try:
        blocks = parse_markdown(args.input.read_text(encoding="utf-8-sig"))
        with open_client(api_key) as client:
            result = run_review(blocks, GeminiReviewer(client, model))
        output = {"document": args.input.name, "model": model, **result}
        args.output.write_text(
            json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
