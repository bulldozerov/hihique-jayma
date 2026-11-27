"""Summarize manually annotated document findings against the benchmark rubric."""

from collections import Counter
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    expected = load(ROOT / "expected.json")
    annotations = load(ROOT / "annotations.json")
    paired = set(annotations["before"]).intersection(annotations["after"])
    print(f"{len(paired)} matched runs per phase")
    for phase, runs in annotations.items():
        paths = sorted((ROOT / "results" / phase).glob("*.json"))
        assert set(runs) == {path.stem for path in paths}
        totals = Counter()
        print(f"\n{phase}")
        for path in paths:
            case, fmt, _ = path.stem.rsplit("-", 2)
            report = load(path)
            labels = runs[path.stem]
            gold = set(expected[case])
            assert len(labels) == len(report["document_findings"]), path
            assert set(labels) <= gold | {"extra", "unsupported"}, path
            if path.stem not in paired:
                continue
            totals[("runs", fmt)] += 1
            totals[("expected", fmt)] += len(gold)
            totals[("found", fmt)] += len(gold.intersection(labels))
            totals[("unsupported", fmt)] += labels.count("unsupported")
            totals[("duplicate", fmt)] += sum(labels.count(tag) > 1 for tag in gold)
            totals[("warnings", fmt)] += len(report.get("review_warnings", []))
            totals[("filtered", fmt)] += len(report.get("benchmark_filtered_findings", []))
            totals[("clean_flags", fmt)] += case == "booking" and bool(
                labels or any(item["findings"] for item in report["requirements"])
            )
            for tag in gold.intersection(labels):
                totals[(case, tag)] += 1
            totals[("case runs", case)] += 1
        for fmt in ("md", "pdf"):
            print(
                f"  {fmt}: {totals['runs', fmt]} runs, "
                f"{totals['found', fmt]}/{totals['expected', fmt]} targets, "
                f"{totals['unsupported', fmt]} unsupported findings, "
                f"{totals['duplicate', fmt]} duplicated targets, "
                f"{totals['warnings', fmt]} warnings, "
                f"{totals['filtered', fmt]} rejected write-operation flags, "
                f"{totals['clean_flags', fmt]} clean controls flagged"
            )
        for case, gold in expected.items():
            for tag in gold:
                print(f"  {case}/{tag}: {totals[case, tag]}/{totals['case runs', case]}")


if __name__ == "__main__":
    main()
