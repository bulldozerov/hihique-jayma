"""Build the report metadata, summary and Markdown export."""

from datetime import datetime
from importlib.metadata import version
from pathlib import Path
import subprocess


SEVERITY = {"critical": "Критично", "major": "Существенно", "minor": "Низкий приоритет"}
KINDS = {
    "ambiguity": "Двусмысленность", "unverifiable": "Непроверяемость",
    "incomplete": "Неполнота", "design_constraint": "Ограничение реализации",
    "contradiction": "Противоречие", "gap": "Пробел", "duplication": "Дублирование",
}


def build_report(document: str, model: str, result: dict) -> dict:
    root = Path(__file__).resolve().parents[2]
    revision = None
    if (root / ".git").exists():
        try:
            revision = subprocess.check_output(
                ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                text=True, stderr=subprocess.DEVNULL, timeout=3,
            ).strip()
        except (OSError, subprocess.SubprocessError):
            pass

    findings = [
        {**finding, "block_ids": requirement["block_ids"]}
        for requirement in result["requirements"] for finding in requirement["findings"]
    ] + result["document_findings"]
    critical = [finding for finding in findings if finding["severity"] == "critical"]
    priority = critical or [finding for finding in findings if finding["severity"] == "major"]
    if critical:
        readiness = "Начинать разработку и тестирование по затронутым сценариям рано. Сначала исправьте критичные дефекты."
    elif result.get("review_warnings") or not result["requirements"]:
        readiness = "Готовность к разработке и тестированию не подтверждена. Проверьте полноту прогона."
    elif priority:
        readiness = "Разработку и тестирование можно начать по однозначным требованиям. Сначала уточните существенные замечания в затронутых сценариях."
    else:
        readiness = "По результатам прогона разработку и тестирование можно начинать."
        priority = findings

    return {
        "document": document,
        "model": model,
        "run_date": datetime.now().astimezone().isoformat(timespec="seconds"),
        "agent_version": revision or f'v{version("hihique-requirements-validator")}',
        **result,
        "summary": {
            "requirements": len(result["requirements"]), "violations": len(findings),
            "critical": critical, "readiness": readiness, "priorities": priority[:3],
        },
    }


def markdown_report(report: dict) -> str:
    lines = ["# Отчёт о проверке требований", "", "## Паспорт прогона", ""]

    def section(title: str) -> None:
        lines.extend([f"## {title}", ""])

    def sources(ids: list[str]) -> None:
        for block_id in dict.fromkeys(ids):
            block = report["evidence"][block_id]
            location = (
                f'стр. {block["page"]}' if block.get("page")
                else f'строки {block["start_line"]}–{block["end_line"]}'
            )
            lines.extend([f"**{block_id}, {location}**", ""])
            lines.extend(f"> {line}" for line in block["source"].splitlines())
            lines.append("")

    def finding(item: dict, include_sources: bool = True) -> None:
        label = f'{SEVERITY[item["severity"]]} · {KINDS[item["kind"]]}'
        lines.extend([f'- **{label}** — {item["explanation"]}', ""])
        for quote in item.get("conflicting_quotes", []):
            lines.extend(f"> {line}" for line in quote.splitlines())
            lines.append("")
        if include_sources:
            sources(item["block_ids"])

    def cell(value: str) -> str:
        return " ".join(value.splitlines()).replace("|", r"\|")

    for label, key in (
        ("Документ", "document"), ("Дата прогона", "run_date"),
        ("Модель", "model"), ("Версия агента", "agent_version"),
    ):
        lines.append(f'- {label} — **{report[key]}**')
    if scope := report.get("review_scope"):
        lines.append(f'- Блоков проверено — {scope["reviewed_blocks"]} из {scope["total_blocks"]}.')
    lines.append("")
    section("Карта требований")
    lines.extend(["| ID отчёта | ID в документе | Краткая формулировка |", "| --- | --- | --- |"])
    for item in report["requirements"]:
        lines.append(f'| {item["id"]} | {cell(item["source_id"] or "—")} | {cell(item["statement"])} |')
    lines.append("")
    section("Проверка отдельных требований")
    for item in report["requirements"]:
        lines.extend([f'### {item["id"]} — {item["statement"]}', ""])
        if not item["findings"]:
            lines.extend(["Замечаний нет.", ""])
        for defect in item["findings"]:
            finding(defect, include_sources=False)
        sources(item["block_ids"])
    section("Проверка набора требований")
    if not report["document_findings"]:
        lines.extend(["Замечаний по набору не найдено.", ""])
    for item in report["document_findings"]:
        finding(item)
    if checks := report.get("acceptance_checks"):
        section("Проверка критериев приёмки")
        verdicts = {"match": "Совпадает", "mismatch": "Расхождение", "undetermined": "Не определено"}
        for check in checks:
            lines.extend([f'- {verdicts[check["verdict"]]} — {check["derived_result"]}', ""])
            sources([check["block_id"]])
    if warnings := report.get("review_warnings"):
        section("Предупреждения прогона")
        lines.extend(f"- {warning}" for warning in warnings)
        lines.append("")
    section("Сводка")
    summary = report["summary"]
    lines.extend([f'Требований — {summary["requirements"]}. Нарушений — {summary["violations"]}. '
                  f'Критичных — {len(summary["critical"])}.', ""])
    for item in summary["critical"]:
        finding(item)
    section("Итог")
    lines.extend([summary["readiness"], ""])
    for item in summary["priorities"]:
        lines.append(f'- {item["explanation"]} ({", ".join(item["block_ids"])}).')
    return "\n".join(lines).rstrip() + "\n"
