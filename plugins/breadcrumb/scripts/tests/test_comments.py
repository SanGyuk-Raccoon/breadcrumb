from __future__ import annotations

import unittest

from support import copied_fixture

from internal.comments import parse_branch, parse_breadcrumb_comment, parse_update_comment


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

    def test_parse_update_comment_with_comment_or_none_boundary(self) -> None:
        linked = "\n".join(
            [
                "## Breadcrumb Update",
                "",
                "- Schema Version: 1",
                "- Applied Through: [comment](https://ghe.example.test/acme/widgets/issues/3#issuecomment-102)",
                f"- Comment Prefix SHA-256: `{'b' * 64}`",
                f"- Body SHA-256: `{'a' * 64}`",
                "",
                "## Summary",
                "",
                "Applied two decisions.",
            ]
        )
        result = parse_update_comment(
            linked, expected_issue=3, repository_url=self.repository_url
        )
        self.assertEqual(result.outcome, "valid")
        self.assertEqual(result.artifact.applied_through_id, 102)
        self.assertEqual(result.artifact.comment_prefix_sha256, "b" * 64)

        none = linked.replace(
            "[comment](https://ghe.example.test/acme/widgets/issues/3#issuecomment-102)",
            "none",
        )
        result = parse_update_comment(
            none, expected_issue=3, repository_url=self.repository_url
        )
        self.assertEqual(result.outcome, "valid")
        self.assertIsNone(result.artifact.applied_through_id)

    def test_update_comment_rejects_wrong_identity_schema_and_hash(self) -> None:
        source = "\n".join(
            [
                "## Breadcrumb Update",
                "- Schema Version: 1",
                "- Applied Through: [comment](https://ghe.example.test/acme/widgets/issues/3#issuecomment-102)",
                f"- Comment Prefix SHA-256: `{'b' * 64}`",
                f"- Body SHA-256: `{'a' * 64}`",
            ]
        )
        cases = (
            source.replace("Schema Version: 1", "Schema Version: 2"),
            source.replace("/issues/3#", "/issues/4#"),
            source.replace("/acme/widgets/", "/acme/other/"),
            source.replace("b" * 64, "ABC"),
            source.replace("a" * 64, "abc"),
        )
        for body in cases:
            with self.subTest():
                result = parse_update_comment(
                    body, expected_issue=3, repository_url=self.repository_url
                )
                self.assertEqual(result.outcome, "invalid")

    def test_update_comment_accepts_repository_url_case_variance(self) -> None:
        body = "\n".join(
            [
                "## Breadcrumb Update",
                "- Schema Version: 1",
                "- Applied Through: [comment](https://ghe.example.test/ACME/Widgets/issues/3#issuecomment-102)",
                f"- Comment Prefix SHA-256: `{'b' * 64}`",
                f"- Body SHA-256: `{'a' * 64}`",
            ]
        )
        result = parse_update_comment(
            body, expected_issue=3, repository_url=self.repository_url
        )
        self.assertEqual(result.outcome, "valid")

    def test_update_comment_rejects_non_string_incomplete_and_malformed_boundary(self) -> None:
        cases: tuple[object, ...] = (
            None,
            "## Breadcrumb Update\n\n- Schema Version: 1",
            "\n".join(
                [
                    "## Breadcrumb Update",
                    "- Schema Version: 1",
                    "- Applied Through: issuecomment-102",
                    f"- Comment Prefix SHA-256: `{'b' * 64}`",
                    f"- Body SHA-256: `{'a' * 64}`",
                ]
            ),
        )
        expected = ("not-breadcrumb", "invalid", "invalid")
        for body, outcome in zip(cases, expected, strict=True):
            with self.subTest(body=body):
                result = parse_update_comment(body, expected_issue=3)
                self.assertEqual(result.outcome, outcome)

    def test_ordinary_comment_is_not_an_update(self) -> None:
        result = parse_update_comment("T1: A", expected_issue=3)
        self.assertEqual(result.outcome, "not-breadcrumb")


if __name__ == "__main__":
    unittest.main()
