"""Run three Gemini reviews per format for each benchmark document."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import time

from dotenv import load_dotenv

from validator.gemini import GeminiReviewer, open_client
from validator.pipeline import run_review
from validator.readers import read_document

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).with_name("fixtures")


class CheckpointReviewer:
    def __init__(self, reviewer, path):
        self.reviewer = reviewer
        self.path = path
        self.responses = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def request(self, stage, prompt, schema):
        fingerprint = sha256(
            f"{self.reviewer.model}\n{schema.__name__}\n{stage}\n{prompt}".encode()
        ).hexdigest()
        if fingerprint in self.responses:
            return schema.model_validate(self.responses[fingerprint])
        response = self.reviewer.request(stage, prompt, schema)
        self.responses[fingerprint] = response.model_dump()
        self.path.parent.mkdir(exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.responses, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.path)
        return response


def run_case(path, repeat, output, key, model):
    target = output / f"{path.stem}-{path.suffix[1:]}-{repeat}.json"
    if target.exists():
        return target.name
    blocks = read_document(path)
    started = time.monotonic()
    checkpoint = output / ".checkpoints" / target.name
    try:
        with open_client(key) as client:
            review = run_review(blocks, CheckpointReviewer(GeminiReviewer(client, model), checkpoint))
    except ValueError:
        checkpoint.unlink(missing_ok=True)
        raise
    result = {
        "document": path.name,
        "model": model,
        "repeat": repeat,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "seconds": round(time.monotonic() - started, 2),
        "block_count": len(blocks),
        **review,
    }
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    checkpoint.unlink(missing_ok=True)
    return target.name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--document", help="Run only a specific filename, including its extension")
    parser.add_argument("--repeat", type=int, choices=(1, 2, 3), help="Run only one repetition")
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be positive")
    args.output.mkdir(parents=True, exist_ok=True)
    load_dotenv(ROOT / ".env")
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
    if not key or not model:
        parser.error("GEMINI_API_KEY and GEMINI_MODEL must be configured")

    paths = [
        *sorted(FIXTURES.glob("*.md")), *sorted(FIXTURES.glob("*.pdf")),
        ROOT / "docs/requirements.md", ROOT / "docs/requirements.pdf",
    ]
    if args.document:
        paths = [path for path in paths if path.name == args.document]
        if not paths:
            parser.error("Unknown benchmark document")
    repeats = (args.repeat,) if args.repeat else range(1, 4)
    failed = False
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        pending = {
            executor.submit(run_case, path, repeat, args.output, key, model): (path.name, repeat)
            for path in paths for repeat in repeats
        }
        for future in as_completed(pending):
            try:
                print(f"OK {future.result()}", flush=True)
            except (OSError, RuntimeError, ValueError) as error:
                name, repeat = pending[future]
                print(f"ERROR {name} #{repeat}: {error}", file=sys.stderr, flush=True)
                failed = True
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
