from __future__ import annotations

import unittest

from support import copied_fixture

from internal.documents import DocumentProblem, parse_issue_status


class IssueBodyTests(unittest.TestCase):
    def test_requirement_and_design_status(self) -> None:
        requirement = copied_fixture("requirement_issue.json")
        design = copied_fixture("design_issue.json")
        requirement_status = parse_issue_status(requirement["body"], "requirement")
        design_status = parse_issue_status(design["body"], "design")
        self.assertEqual(requirement_status.schema_version, 2)
        self.assertEqual(requirement_status.phase, "ready")
        self.assertIsNone(requirement_status.related_requirement)
        self.assertIsNone(requirement_status.refined_from)
        self.assertEqual(design_status.schema_version, 1)
        self.assertEqual(design_status.related_requirement, 12)

    def test_backlog_status_has_no_phase_or_todo(self) -> None:
        backlog = copied_fixture("backlog_issue.json")
        status = parse_issue_status(backlog["body"], "backlog")
        self.assertEqual(status.schema_version, 1)
        self.assertEqual(status.issue_type, "backlog")
        self.assertIsNone(status.phase)
        self.assertIsNone(status.related_requirement)
        self.assertIsNone(status.refined_from)
        self.assertEqual(status.last_step, "backlog")

    def test_backlog_rejects_todo_phase_and_trailing_content(self) -> None:
        body = copied_fixture("backlog_issue.json")["body"]
        variants = (
            (body.replace("## Breadcrumb Status", "## Todo\n\n## Breadcrumb Status"), "invalid_heading"),
            (body.replace("- Type: backlog", "- Type: backlog\n- Phase: ready"), "unknown_field"),
            (body.replace("- Type: backlog", "- Type: requirement"), "invalid_type"),
            (
                body.replace(
                    "<!-- breadcrumb:state:start -->",
                    "<!-- breadcrumb:state:start -->\n<!-- breadcrumb:state:start -->",
                ),
                "duplicate_marker",
            ),
            (body + "\ntrailing", "invalid_marker_order"),
        )
        for value, code in variants:
            with self.subTest(code=code), self.assertRaises(DocumentProblem) as raised:
                parse_issue_status(value, "backlog")
            self.assertEqual(raised.exception.code, code)

    def test_legacy_requirement_status_remains_supported(self) -> None:
        issue = copied_fixture("requirement_issue_v1.json")
        status = parse_issue_status(issue["body"], "requirement")
        self.assertEqual(status.schema_version, 1)
        self.assertEqual(status.refined_from, 5)
        self.assertEqual(status.last_step, "refine")

    def test_requirement_fields_are_version_specific(self) -> None:
        current = copied_fixture("requirement_issue.json")["body"]
        legacy = copied_fixture("requirement_issue_v1.json")["body"]
        v2_with_refined_from = current.replace(
            "- Last Breadcrumb Step: open",
            "- Refined From: none\n- Last Breadcrumb Step: open",
        )
        v1_without_refined_from = legacy.replace("- Refined From: #5\n", "")

        with self.assertRaises(DocumentProblem) as v2_error:
            parse_issue_status(v2_with_refined_from, "requirement")
        with self.assertRaises(DocumentProblem) as v1_error:
            parse_issue_status(v1_without_refined_from, "requirement")
        self.assertEqual(v2_error.exception.code, "unknown_field")
        self.assertEqual(v1_error.exception.code, "missing_field")

    def test_design_schema_version_two_is_not_supported(self) -> None:
        design = copied_fixture("design_issue.json")
        design["body"] = design["body"].replace(
            "- Schema Version: 1", "- Schema Version: 2"
        )
        with self.assertRaises(DocumentProblem) as raised:
            parse_issue_status(design["body"], "design")
        self.assertEqual(raised.exception.code, "invalid_schema_version")

    def test_phase_must_match_todo(self) -> None:
        issue = copied_fixture("requirement_issue.json")
        issue["body"] = issue["body"].replace("- [x]", "- [ ]")
        with self.assertRaises(DocumentProblem) as raised:
            parse_issue_status(issue["body"], "requirement")
        self.assertEqual(raised.exception.code, "invalid_phase")

    def test_state_block_must_be_final(self) -> None:
        issue = copied_fixture("requirement_issue.json")
        with self.assertRaises(DocumentProblem) as raised:
            parse_issue_status(issue["body"] + "\ntrailing", "requirement")
        self.assertEqual(raised.exception.code, "invalid_marker_order")

    def test_invalid_todo_syntax_is_rejected(self) -> None:
        issue = copied_fixture("requirement_issue.json")
        issue["body"] = issue["body"].replace(
            "- [x] Confirm the threshold", "An unresolved note"
        )
        with self.assertRaises(DocumentProblem) as raised:
            parse_issue_status(issue["body"], "requirement")
        self.assertEqual(raised.exception.code, "invalid_todo")

    def test_reserved_lines_and_lowercase_checkbox_are_exact(self) -> None:
        issue = copied_fixture("requirement_issue.json")
        cases = (
            (issue["body"].replace("<!-- breadcrumb:state:start -->", " <!-- breadcrumb:state:start -->"), "missing_marker"),
            (issue["body"].replace("## Todo", "## Todo "), "missing_heading"),
            (issue["body"].replace("- [x]", "- [X]"), "invalid_todo"),
        )
        for body, code in cases:
            with self.subTest(code=code), self.assertRaises(DocumentProblem) as raised:
                parse_issue_status(body, "requirement")
            self.assertEqual(raised.exception.code, code)

    def test_status_rejects_unknown_and_out_of_order_fields(self) -> None:
        issue = copied_fixture("requirement_issue.json")
        unknown = issue["body"].replace(
            "- Last Breadcrumb Step: open",
            "- Extra: value\n- Last Breadcrumb Step: open",
        )
        out_of_order = issue["body"].replace(
            "- Schema Version: 2\n- Type: requirement",
            "- Type: requirement\n- Schema Version: 2",
        )
        with self.assertRaises(DocumentProblem) as unknown_error:
            parse_issue_status(unknown, "requirement")
        with self.assertRaises(DocumentProblem) as order_error:
            parse_issue_status(out_of_order, "requirement")
        self.assertEqual(unknown_error.exception.code, "unknown_field")
        self.assertEqual(order_error.exception.code, "invalid_field_order")


if __name__ == "__main__":
    unittest.main()
