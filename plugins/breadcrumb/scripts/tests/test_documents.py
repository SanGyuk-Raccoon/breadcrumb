from __future__ import annotations

import unittest

from support import copied_fixture, work_body

from internal.documents import parse_work_body


class WorkDocumentTests(unittest.TestCase):
    def test_three_statuses_and_todo_counts(self) -> None:
        issues = copied_fixture("work_issues.json")
        backlog = parse_work_body(issues[0]["body"])
        active = parse_work_body(issues[1]["body"])
        complete = parse_work_body(issues[2]["body"])

        self.assertTrue(backlog.valid)
        self.assertEqual((backlog.status, backlog.resolved, backlog.unresolved), ("backlog", 0, 1))
        self.assertTrue(active.valid)
        self.assertEqual((active.status, active.resolved, active.unresolved), ("in-progress", 1, 1))
        self.assertTrue(complete.valid)
        self.assertEqual((complete.status, complete.resolved, complete.unresolved), ("complete", 2, 0))

    def test_complete_and_in_progress_must_match_todo(self) -> None:
        complete = parse_work_body(work_body("complete", ["- [ ] Still open."]))
        active = parse_work_body(work_body("in-progress", ["- [x] Already done."]))
        self.assertIn("status_todo_mismatch", {item.code for item in complete.errors})
        self.assertIn("status_todo_mismatch", {item.code for item in active.errors})

    def test_backlog_allows_any_todo_count(self) -> None:
        empty = parse_work_body(work_body("backlog"))
        mixed = parse_work_body(
            work_body("backlog", ["- [x] Captured context.", "- [ ] Start later."])
        )
        self.assertTrue(empty.valid)
        self.assertTrue(mixed.valid)

    def test_heading_contract_is_fixed(self) -> None:
        body = work_body("complete")
        variants = (
            body.replace("## Goal", "## Objective"),
            body.replace("## Goal", "## Goal\n\n## Goal", 1),
            body.replace("## Goal", "## Design", 1),
            "preface\n" + body,
        )
        for variant in variants:
            with self.subTest():
                self.assertFalse(parse_work_body(variant).valid)

    def test_narrative_markdown_is_opaque(self) -> None:
        body = work_body("complete").replace(
            "Background text.",
            "### Detail\n\n```md\n## Not a real heading\n- [ ] Not a Todo\n```",
        )
        result = parse_work_body(body)
        self.assertTrue(result.valid, result.errors)
        self.assertEqual(result.unresolved, 0)

    def test_todo_accepts_uppercase_checked_but_rejects_prose(self) -> None:
        checked = parse_work_body(work_body("complete", ["- [X] Done."]))
        prose = parse_work_body(work_body("in-progress", ["Decide this."]))
        self.assertTrue(checked.valid)
        self.assertIn("invalid_todo", {item.code for item in prose.errors})

    def test_future_schema_is_preserved_and_rejected(self) -> None:
        result = parse_work_body(work_body("complete", schema_version="2"))
        self.assertEqual(result.schema_version, 2)
        self.assertIn("unsupported_schema_version", {item.code for item in result.errors})

    def test_status_has_only_two_ordered_fields(self) -> None:
        body = work_body("complete")
        unknown = body.replace("- Status: complete", "- Extra: value\n- Status: complete")
        reversed_fields = body.replace(
            "- Schema Version: 1\n- Status: complete",
            "- Status: complete\n- Schema Version: 1",
        )
        self.assertIn("unknown_field", {item.code for item in parse_work_body(unknown).errors})
        self.assertIn(
            "invalid_field_order",
            {item.code for item in parse_work_body(reversed_fields).errors},
        )


if __name__ == "__main__":
    unittest.main()
