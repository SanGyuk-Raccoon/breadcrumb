from __future__ import annotations

import unittest

from support import SCRIPT_ROOT  # noqa: F401 - installs the scripts import path

from internal.footprints import parse_branch, parse_footprint, validate_template_footprint


def implementation_body(
    *, issue: int = 21, branch: str = "breadcrumb/21-login-rate-limit"
) -> str:
    return f"""<!--
breadcrumb:
  version: 1
  step: implement
  issue: {issue}
  branch: {branch}
  commit: 0123456789abcdef0123456789abcdef01234567
  verification: passed
-->

## Breadcrumb: Implementation
"""


class BranchTests(unittest.TestCase):
    def test_branch_requires_positive_issue_and_slug(self) -> None:
        self.assertEqual(parse_branch("breadcrumb/21-login-rate-limit"), 21)
        self.assertIsNone(parse_branch("breadcrumb/0-nope"))
        self.assertIsNone(parse_branch("breadcrumb/21-Upper"))
        self.assertIsNone(parse_branch("feature/21-login"))


class FootprintTests(unittest.TestCase):
    def test_valid_implementation_footprint(self) -> None:
        result = parse_footprint(
            implementation_body(), expected_step="implement", expected_issue=21
        )
        self.assertEqual(result.outcome, "valid")
        self.assertEqual(result.footprint.branch, "breadcrumb/21-login-rate-limit")

    def test_valid_legacy_refine_footprint(self) -> None:
        body = """<!--
breadcrumb:
  version: 1
  step: refine
  issue: 11
  replacement_issue: 12
-->

## Breadcrumb: Refinement
"""
        result = parse_footprint(body, expected_step="refine", expected_issue=11)
        self.assertEqual(result.outcome, "valid")
        self.assertEqual(result.footprint.replacement_issue, 12)

    def test_non_footprint_first_block_is_ignored(self) -> None:
        result = parse_footprint("## Heading\n\n" + implementation_body())
        self.assertEqual(result.outcome, "not-breadcrumb")

    def test_unknown_duplicate_and_context_fields_are_invalid(self) -> None:
        unknown = implementation_body().replace(
            "  verification: passed", "  verification: passed\n  extra: value"
        )
        duplicate = implementation_body().replace(
            "  issue: 21", "  issue: 21\n  issue: 21"
        )
        mismatch = implementation_body(issue=22, branch="breadcrumb/22-login-rate-limit")
        self.assertEqual(parse_footprint(unknown).outcome, "invalid")
        self.assertEqual(parse_footprint(duplicate).outcome, "invalid")
        self.assertEqual(
            parse_footprint(mismatch, expected_issue=21).outcome, "invalid"
        )

    def test_pr_requires_matching_final_closes_line(self) -> None:
        body = """<!--
breadcrumb:
  version: 1
  step: pr
  issue: 21
  branch: breadcrumb/21-login-rate-limit
-->

## Summary

Closes #21
"""
        result = parse_footprint(
            body,
            expected_step="pr",
            expected_issue=21,
            expected_branch="breadcrumb/21-login-rate-limit",
            require_pr_closes=True,
        )
        self.assertEqual(result.outcome, "valid")
        self.assertEqual(
            parse_footprint(body + "extra\n", require_pr_closes=True).outcome,
            "invalid",
        )

    def test_template_parser_allows_placeholders_but_enforces_shape(self) -> None:
        template = """<!--
breadcrumb:
  version: 1
  step: implement
  issue: <design-issue-number>
  branch: <implementation-branch>
  commit: <verified-head-sha>
  verification: <passed-or-failed-or-instruction-error-or-pending>
-->
"""
        self.assertEqual(validate_template_footprint(template, "implement"), [])
        problems = validate_template_footprint(
            template.replace("  step: implement", "  step: refine"), "implement"
        )
        self.assertIn("invalid_footprint_step", {problem.code for problem in problems})
        wrong_placeholder = validate_template_footprint(
            template.replace("<implementation-branch>", "any-branch"), "implement"
        )
        self.assertIn("missing_field", {problem.code for problem in wrong_placeholder})


if __name__ == "__main__":
    unittest.main()
