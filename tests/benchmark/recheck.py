"""Apply the final API evidence filter to recorded Gemini runs."""

import argparse
import json
from pathlib import Path
import re

from validator.api_coverage import api_review_blocks, has_write_definition
from validator.readers import read_document

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    args = parser.parse_args()
    for path in sorted(args.results.glob("*.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        document = report["document"]
        directory = ROOT / "docs" if path.stem.startswith("requirements-") else Path(__file__).with_name("fixtures")
        blocks = api_review_blocks([block.to_dict() for block in read_document(directory / document)])
        sources = {block["id"]: block["text"] for block in blocks}
        kept = []
        removed = report.get("benchmark_filtered_findings", [])
        for finding in report["document_findings"]:
            operation = re.fullmatch(
                r"ТЗ требует операцию «(.+)», для неё не описан вызов API\.",
                finding["explanation"],
            )
            if (
                operation and finding["kind"] == "gap" and len(finding["block_ids"]) == 1
                and len(finding.get("conflicting_quotes", [])) == 1
                and has_write_definition(
                    operation[1], finding["conflicting_quotes"][0],
                    sources.get(finding["block_ids"][0], ""), blocks,
                )
            ):
                removed.append(finding)
            else:
                kept.append(finding)
        if removed:
            report["document_findings"] = kept
            report["benchmark_filtered_findings"] = removed
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(path.name, len(removed))


if __name__ == "__main__":
    main()
