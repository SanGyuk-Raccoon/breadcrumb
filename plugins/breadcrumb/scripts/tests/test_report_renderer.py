from __future__ import annotations

import importlib.util
import unittest

from support import SCRIPT_ROOT

from internal.documents import HEADINGS, parse_work_body


REPORT_SCRIPT = (
    SCRIPT_ROOT.parent / "skills" / "breadcrumb-report" / "scripts" / "render_report.py"
)
SPEC = importlib.util.spec_from_file_location("breadcrumb_report_renderer", REPORT_SCRIPT)
assert SPEC is not None and SPEC.loader is not None
REPORT_RENDERER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPORT_RENDERER)


class ReportRendererTests(unittest.TestCase):
    def test_bug_is_one_valid_backlog_work_issue(self) -> None:
        result = REPORT_RENDERER.render_report(
            {
                "report_type": "Bug",
                "title": "List omits report issues",
                "summary": "A submitted report is absent from list output.",
                "actual_behavior": "The report uses an unsupported body shape.",
                "expected_behavior": "The report appears as backlog work.",
                "reproduction_context": "Submit a product report, then run list.",
                "constraints": "Keep the ordinary parser strict.",
                "acceptance_conditions": "Use only the breadcrumb label.",
            }
        )

        parsed = parse_work_body(result["body"])
        self.assertTrue(parsed.valid, parsed.errors)
        self.assertEqual(result["labels"], ["breadcrumb"])
        self.assertEqual((parsed.status, parsed.resolved, parsed.unresolved), ("backlog", 0, 1))
        self.assertEqual(
            [line for line in result["body"].splitlines() if line.startswith("## ")],
            list(HEADINGS),
        )
        todo = result["body"].split("## Todo\n", 1)[1].split(
            "## Breadcrumb Status", 1
        )[0]
        self.assertEqual(
            [line for line in todo.splitlines() if line],
            ["- [ ] 보고 내용을 구현 가능한 요구사항, 설계와 검증 계획으로 정제한다."],
        )
        self.assertIn("### Report Type\n\nBug", result["body"])
        self.assertIn("### Expected Behavior", result["body"])

    def test_feature_request_preserves_value_and_leaves_unconfirmed_sections_blank(self) -> None:
        result = REPORT_RENDERER.render_report(
            {
                "report_type": "Feature Request",
                "title": "Create reports as backlog work",
                "problem_or_opportunity": "Product reports need durable lifecycle state.",
                "desired_behavior": "Create a schema 1 backlog work issue.",
                "context": "Reports may be submitted outside a Git repository.",
                "expected_value": "The existing list and load workflow can consume reports.",
                "constraints": "Target only the Breadcrumb upstream.",
            }
        )

        parsed = parse_work_body(result["body"])
        self.assertTrue(parsed.valid, parsed.errors)
        self.assertIn("### Report Type\n\nFeature Request", result["body"])
        self.assertIn("### Expected Value", result["body"])
        self.assertIn("## Design\n\n\n\n## Verification", result["body"])
        self.assertEqual(result["todo"], {"resolved": 0, "unresolved": 1})

    def test_reserved_report_values_are_rejected(self) -> None:
        base = {
            "report_type": "Bug",
            "title": "Safe title",
            "summary": "Observed problem.",
            "actual_behavior": "Current result.",
            "expected_behavior": "Expected result.",
            "reproduction_context": "Confirmed context.",
        }
        variants = (
            ("summary", "Observed.\n\n## Goal\n\nInjected."),
            ("actual_behavior", "Current result.\n- Status: complete"),
            ("expected_behavior", "<!-- breadcrumb:state -->"),
            ("reproduction_context", "Contains <background> placeholder."),
        )
        for key, value in variants:
            with self.subTest(key=key):
                payload = dict(base)
                payload[key] = value
                with self.assertRaises(ValueError):
                    REPORT_RENDERER.render_report(payload)

    def test_type_fields_and_title_are_strict(self) -> None:
        with self.assertRaisesRegex(ValueError, "report_type"):
            REPORT_RENDERER.render_report({"report_type": "Feature", "title": "Title"})
        with self.assertRaisesRegex(ValueError, "one line"):
            REPORT_RENDERER.render_report(
                {
                    "report_type": "Bug",
                    "title": "First\nSecond",
                    "summary": "Summary",
                    "actual_behavior": "Actual",
                    "expected_behavior": "Expected",
                    "reproduction_context": "Context",
                }
            )
        with self.assertRaisesRegex(ValueError, "unknown input fields"):
            REPORT_RENDERER.render_report(
                {
                    "report_type": "Bug",
                    "title": "Title",
                    "summary": "Summary",
                    "actual_behavior": "Actual",
                    "expected_behavior": "Expected",
                    "reproduction_context": "Context",
                    "labels": ["bug"],
                }
            )


if __name__ == "__main__":
    unittest.main()
