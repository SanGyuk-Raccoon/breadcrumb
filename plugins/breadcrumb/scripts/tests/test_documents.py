from __future__ import annotations

import unittest

from support import copied_fixture, work_body

from internal.documents import parse_work_body


def add_decision_brief(body: str, identifier: str = "T1") -> str:
    return body.replace(
        "Use the existing component.",
        "Use the existing component.\n\n"
        f"#### {identifier} — Retry policy\n\n"
        "- Why: callers need one policy.\n"
        "- Options: bounded or unbounded retries.\n"
        "- Recommendation: use bounded retries.\n"
        "- Uncertainty: the production limit is not measured yet.\n"
        f"- Reply example: `{identifier}: bounded`.",
    )


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

    def test_todo_items_are_structured_with_canonical_ids(self) -> None:
        body = work_body(
            "in-progress",
            [
                "- [ ] T1: Action: Measure retry behavior.",
                "- [X] T2: Decision: Confirm the limit.",
            ],
        )
        result = parse_work_body(body)
        lines = body.splitlines()

        self.assertTrue(result.valid, result.errors)
        self.assertEqual(result.warnings, ())
        self.assertEqual(
            [item.as_dict() for item in result.items],
            [
                {
                    "id": "T1",
                    "checked": False,
                    "text": "Action: Measure retry behavior.",
                    "line": lines.index("- [ ] T1: Action: Measure retry behavior.")
                    + 1,
                },
                {
                    "id": "T2",
                    "checked": True,
                    "text": "Decision: Confirm the limit.",
                    "line": lines.index("- [X] T2: Decision: Confirm the limit.")
                    + 1,
                },
            ],
        )
        self.assertEqual(
            result.projection()["todo"]["items"],
            [item.as_dict() for item in result.items],
        )

    def test_duplicate_todo_id_is_an_error(self) -> None:
        body = work_body(
            "in-progress",
            [
                "- [ ] T1: Action: Choose the policy.",
                "- [x] T1: Action: Confirm the policy.",
            ],
        )
        result = parse_work_body(body)
        duplicate = next(
            item for item in result.errors if item.code == "duplicate_todo_id"
        )

        self.assertFalse(result.valid)
        self.assertEqual(
            duplicate.line,
            body.splitlines().index("- [x] T1: Action: Confirm the policy.") + 1,
        )
        self.assertEqual(result.warnings, ())

    def test_todo_without_kind_remains_valid_with_warning(self) -> None:
        body = work_body("in-progress", ["- [ ] T1: Legacy Todo."])
        result = parse_work_body(body)

        self.assertTrue(result.valid, result.errors)
        self.assertEqual(result.items[0].text, "Legacy Todo.")
        self.assertEqual(
            [warning.code for warning in result.warnings], ["missing_todo_kind"]
        )

    def test_todo_without_id_remains_valid_with_warning(self) -> None:
        body = work_body("backlog", ["- [ ] Legacy Todo."])
        result = parse_work_body(body)

        self.assertTrue(result.valid, result.errors)
        self.assertEqual(
            result.items[0].as_dict(),
            {
                "id": None,
                "checked": False,
                "text": "Legacy Todo.",
                "line": body.splitlines().index("- [ ] Legacy Todo.") + 1,
            },
        )
        self.assertEqual(
            [warning.as_dict() for warning in result.warnings],
            [
                {
                    "code": "missing_todo_id",
                    "message": (
                        "Todo item does not start with a canonical "
                        "T<number>: identifier"
                    ),
                    "line": body.splitlines().index("- [ ] Legacy Todo.") + 1,
                }
            ],
        )

    def test_non_positive_or_padded_todo_id_is_not_canonical(self) -> None:
        for item in ("- [ ] T0: Invalid ID.", "- [ ] T01: Padded ID."):
            with self.subTest(item=item):
                result = parse_work_body(work_body("backlog", [item]))
                self.assertTrue(result.valid, result.errors)
                self.assertIsNone(result.items[0].id)
                self.assertEqual(
                    {warning.code for warning in result.warnings},
                    {"missing_todo_id"},
                )

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

    def test_decision_brief_and_stable_todo_id_fit_schema_one(self) -> None:
        body = add_decision_brief(
            work_body("in-progress", ["- [ ] T1: Decision: Choose the retry policy."])
        )
        result = parse_work_body(body)
        self.assertTrue(result.valid, result.errors)
        self.assertEqual(result.warnings, ())
        self.assertEqual(result.unresolved, 1)

    def test_unresolved_action_does_not_require_a_decision_brief(self) -> None:
        result = parse_work_body(
            work_body("in-progress", ["- [ ] T1: Action: Run the compatibility suite."])
        )

        self.assertTrue(result.valid, result.errors)

    def test_unresolved_decision_requires_a_same_id_brief(self) -> None:
        result = parse_work_body(
            work_body("in-progress", ["- [ ] T1: Decision: Choose the retry policy."])
        )

        self.assertIn("missing_decision_brief", {item.code for item in result.errors})

        wrong_id = parse_work_body(
            add_decision_brief(
                work_body(
                    "in-progress",
                    ["- [ ] T1: Decision: Choose the retry policy."],
                ),
                "T2",
            )
        )
        self.assertIn(
            "missing_decision_brief", {item.code for item in wrong_id.errors}
        )

    def test_duplicate_decision_briefs_are_rejected(self) -> None:
        body = add_decision_brief(
            work_body("in-progress", ["- [ ] T1: Decision: Choose the retry policy."])
        )
        brief = body.split("#### T1 — Retry policy", 1)[1].split("## Verification", 1)[0]
        body = body.replace(
            "## Verification",
            f"#### T1 — Duplicate policy{brief}\n## Verification",
            1,
        )
        result = parse_work_body(body)

        self.assertIn("duplicate_decision_brief", {item.code for item in result.errors})

    def test_decision_brief_requires_each_non_empty_field(self) -> None:
        required = (
            "Why",
            "Options",
            "Recommendation",
            "Uncertainty",
            "Reply example",
        )
        base = add_decision_brief(
            work_body("in-progress", ["- [ ] T1: Decision: Choose the retry policy."])
        )
        for field in required:
            with self.subTest(field=field):
                body = base.replace(f"- {field}:", f"- {field} removed:", 1)
                result = parse_work_body(body)
                self.assertIn(
                    "invalid_decision_brief", {item.code for item in result.errors}
                )

        empty = base.replace(
            "- Why: callers need one policy.", "- Why:   ", 1
        )
        duplicate = base.replace(
            "- Why: callers need one policy.",
            "- Why: callers need one policy.\n- Why: duplicate reason.",
            1,
        )
        for body in (empty, duplicate):
            with self.subTest(malformed="empty-or-duplicate"):
                self.assertIn(
                    "invalid_decision_brief",
                    {item.code for item in parse_work_body(body).errors},
                )

    def test_completed_decision_does_not_force_historical_brief_rewrite(self) -> None:
        result = parse_work_body(
            work_body("complete", ["- [x] T1: Decision: Use bounded retries."])
        )

        self.assertTrue(result.valid, result.errors)
        self.assertEqual(result.warnings, ())

    def test_decision_brief_heading_inside_a_fence_is_ignored(self) -> None:
        body = work_body(
            "in-progress", ["- [ ] T1: Decision: Choose the retry policy."]
        ).replace(
            "Use the existing component.",
            "```md\n#### T1 — Retry policy\n"
            "- Why: example only.\n"
            "- Options: one or two.\n"
            "- Recommendation: one.\n"
            "- Uncertainty: unknown.\n"
            "- Reply example: `T1: one`.\n```",
        )
        result = parse_work_body(body)

        self.assertIn("missing_decision_brief", {item.code for item in result.errors})

    def test_complete_requires_every_core_section(self) -> None:
        content = {
            "Background": "Background text.",
            "Goal": "Goal text.",
            "Requirements": "- Required behavior.",
            "Design": "Use the existing component.",
            "Verification": "Run unit tests.",
        }
        for section, value in content.items():
            with self.subTest(section=section):
                body = work_body(
                    "complete", ["- [x] T1: Action: Finish planning."]
                ).replace(value, "", 1)
                result = parse_work_body(body)
                self.assertIn(
                    "empty_required_section", {item.code for item in result.errors}
                )

    def test_complete_rejects_only_exact_reserved_section_placeholders(self) -> None:
        for placeholder in ("<background>", "TBD", "Unknown", "N/A"):
            with self.subTest(placeholder=placeholder):
                body = work_body("complete").replace(
                    "Background text.", placeholder, 1
                )
                result = parse_work_body(body)
                self.assertIn(
                    "placeholder_required_section",
                    {item.code for item in result.errors},
                )

        legitimate = work_body("complete").replace(
            "Background text.",
            "The cause is unknown until runtime evidence is captured.",
            1,
        )
        self.assertTrue(parse_work_body(legitimate).valid)

    def test_legacy_untyped_decision_brief_is_not_forced_to_migrate(self) -> None:
        body = work_body("in-progress", ["- [ ] T1: Choose the retry policy."])
        body = body.replace(
            "Use the existing component.",
            "#### T1 — Retry policy\n\n- Why: historical context only.",
        )
        result = parse_work_body(body)

        self.assertTrue(result.valid, result.errors)
        self.assertEqual(
            {warning.code for warning in result.warnings}, {"missing_todo_kind"}
        )

    def test_todo_accepts_uppercase_checked_but_rejects_prose(self) -> None:
        checked = parse_work_body(
            work_body("complete", ["- [X] T1: Action: Done."])
        )
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
