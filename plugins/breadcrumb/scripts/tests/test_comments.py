from __future__ import annotations

import unittest

from support import copied_fixture

from internal.comments import parse_branch, parse_breadcrumb_comment


class CommentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.comments = copied_fixture("comments.json")
        self.repository_url = "https://ghe.example.test/acme/widgets"

    def test_branch_contract(self) -> None:
        self.assertEqual(parse_branch("breadcrumb/3-implement-retry-policy"), 3)
        self.assertIsNone(parse_branch("breadcrumb/0-nope"))
        self.assertIsNone(parse_branch("breadcrumb/3-Upper"))
        self.assertIsNone(parse_branch("feature/3-retry"))

    def test_parse_visible_implementation_metadata(self) -> None:
        result = parse_breadcrumb_comment(
            self.comments[0]["body"], expected_issue=3, repository_url=self.repository_url
        )
        self.assertEqual(result.outcome, "valid")
        self.assertEqual(result.artifact.kind, "implementation")
        self.assertEqual(result.artifact.verification, "passed")

    def test_parse_visible_stale_metadata(self) -> None:
        result = parse_breadcrumb_comment(
            self.comments[1]["body"], expected_issue=3, repository_url=self.repository_url
        )
        self.assertEqual(result.outcome, "valid")
        self.assertEqual(result.artifact.kind, "stale")
        self.assertIn("requirements changed", result.artifact.reason.lower())

    def test_ordinary_comment_is_ignored(self) -> None:
        result = parse_breadcrumb_comment("## Review\n\nLooks good.", expected_issue=3)
        self.assertEqual(result.outcome, "not-breadcrumb")

    def test_wrong_issue_link_commit_and_verification_are_invalid(self) -> None:
        source = self.comments[0]["body"]
        cases = (
            source.replace("breadcrumb/3-", "breadcrumb/4-"),
            source.replace("/tree/breadcrumb/3-", "/tree/feature/3-"),
            source.replace("0123456789abcdef0123456789abcdef01234567", "abc", 1),
            source.replace("- Verification: passed", "- Verification: skipped"),
        )
        for body in cases:
            with self.subTest():
                result = parse_breadcrumb_comment(
                    body, expected_issue=3, repository_url=self.repository_url
                )
                self.assertEqual(result.outcome, "invalid")


if __name__ == "__main__":
    unittest.main()
