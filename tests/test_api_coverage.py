import unittest
from pathlib import Path

from validator.api_coverage import api_checklist, api_review_blocks, check_api_coverage, has_write_definition
from validator.readers import read_document


class Reviewer:
    def __init__(self, response):
        self.response = response

    def request(self, stage, prompt, schema):
        return schema.model_validate(self.response)


class ApiCoverageTests(unittest.TestCase):
    def test_explicit_replacement_only_covers_writing_the_same_resource(self):
        declaration = "Экран читает сохранённую подписку. Изменения экран сохраняет через API."
        blocks = [{"text": "PUT /report-subscription заменяет сохранённую подписку."}]
        self.assertTrue(has_write_definition(
            "Сохранение изменений", "Изменения экран сохраняет через API.", declaration, blocks
        ))
        self.assertFalse(has_write_definition(
            "Чтение сохранённой подписки", "Экран читает сохранённую подписку.", declaration, blocks
        ))
        self.assertFalse(has_write_definition(
            "Сохранение расписания", "Экран сохраняет расписание.", declaration, blocks
        ))

    def test_reports_missing_checklist_entries_with_local_evidence(self):
        blocks = [
            {"id": "B001", "section": ["Integration"], "text": "The app reads settings."},
            {"id": "B002", "section": ["API"], "text": "Success codes: HTTP 200 and HTTP 201."},
        ]
        response = {"checks": [
            {"id": "A01", "outcome": "missing", "definition_block_id": None},
            {"id": "A02", "outcome": "defined", "definition_block_id": "B002"},
            {"id": "A03", "outcome": "missing", "definition_block_id": None},
        ]}
        findings = list(check_api_coverage(blocks, Reviewer(response)))
        self.assertEqual([bid for bid, _, _ in findings], ["B001", "B002"])
        self.assertIn("201", findings[1][2])
        with self.assertRaisesRegex(ValueError, "every checklist item"):
            list(check_api_coverage(blocks, Reviewer({"checks": response["checks"][:-1]})))

    def test_original_markdown_and_pdf_include_read_and_201(self):
        root = Path(__file__).resolve().parents[1]
        inventories = []
        for extension in ("md", "pdf"):
            blocks = read_document(root / "docs" / f"requirements.{extension}")
            items = api_checklist(api_review_blocks([b.to_dict() for b in blocks]))
            identities = [item.get("operation", item.get("status")) for item in items]
            self.assertIn("чтение", identities)
            self.assertIn(201, identities)
            inventories.append(identities)
        self.assertEqual(*inventories)

    def test_replay_markdown_gemini_response(self):
        self.assert_replayed_findings("md", [
            None, "B034", "B103", "B103", "B103", "B103", "B115", "B115", None,
        ], "B034", "B103")

    def test_replay_pdf_gemini_response(self):
        self.assert_replayed_findings("pdf", [
            None, "B038", "B103", None, "B104", "B109", "B110", "B111", "B117",
        ], "B038", "B096")

    def assert_replayed_findings(self, extension, definitions, read_block, status_block):
        root = Path(__file__).resolve().parents[1]
        blocks = read_document(root / "docs" / f"requirements.{extension}")
        selected = api_review_blocks([b.to_dict() for b in blocks])
        response = {"checks": [
            {
                "id": f"A{index:02d}",
                "outcome": "defined" if definition else "missing",
                "definition_block_id": definition,
            }
            for index, definition in enumerate(definitions, 1)
        ]}
        findings = list(check_api_coverage(selected, Reviewer(response)))
        self.assertEqual([bid for bid, _, _ in findings], [read_block, status_block])
        self.assertIn("чтение", findings[0][2])
        self.assertIn("201", findings[1][2])
