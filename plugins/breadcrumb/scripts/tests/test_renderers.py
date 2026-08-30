from __future__ import annotations

import unittest

from support import SCRIPT_ROOT  # noqa: F401

from internal.adrs import parse_adr_bytes
from internal.comments import parse_breadcrumb_comment, parse_update_comment
from internal.documents import parse_work_body
from internal.rendering import (
    render_adr,
    render_implementation_comment,
    render_pull_request,
    render_stale_comment,
    render_update_comment,
    render_work_issue,
)


REPOSITORY_URL = "https://github.com/acme/widgets"
COMMIT = "a" * 40


class ArtifactRendererTests(unittest.TestCase):
    def test_work_issue_renderer_produces_one_valid_complete_issue(self) -> None:
        result = render_work_issue(
            {
                "title": "Split workflow skills",
                "background": "The current skill mixes unrelated operations.",
                "goal": "Expose operation-scoped skills.",
                "requirements": "- Preserve artifact schemas.",
                "design": "Use shared internal modules.",
                "verification": "Run the full unit test suite.",
                "todo": ["- [x] T1: Confirm the design."],
                "status": "complete",
            }
        )
        parsed = parse_work_body(result["body"])
        self.assertTrue(parsed.valid, parsed.errors)
        self.assertEqual(parsed.items[0].id, "T1")
        self.assertEqual(parsed.warnings, ())
        self.assertEqual(result["labels"], ["breadcrumb"])
        self.assertEqual(result["todo"], {"resolved": 1, "unresolved": 0})

    def test_work_issue_renderer_rejects_invalid_status_and_heading_injection(self) -> None:
        base = {
            "title": "Title",
            "background": "Background",
            "goal": "Goal",
            "requirements": "Requirements",
            "design": "Design",
            "verification": "Verification",
            "todo": [],
            "status": "complete",
        }
        with self.assertRaisesRegex(ValueError, "status"):
            render_work_issue({**base, "status": "done"})
        with self.assertRaisesRegex(ValueError, "valid work issue"):
            render_work_issue({**base, "goal": "## Breadcrumb Status"})

    def test_adr_renderer_produces_one_valid_document(self) -> None:
        result = render_adr(
            {
                "issue_number": 29,
                "slug": "operation-scoped-skills",
                "title": "Use operation-scoped skills",
                "status": "accepted",
                "supersedes": [],
                "superseded_by": [],
                "summary": "Split the public workflow by operation.",
                "context": "The umbrella skill mixes unrelated authority.",
                "affected_areas": {
                    "components": ["plugin skills"],
                    "paths": ["plugins/breadcrumb/skills/**"],
                    "resources": ["GitHub work issues"],
                    "behaviors": ["skill selection"],
                },
                "decision": "Expose seven independent skills.",
                "consequences": "Each skill loads less unrelated context.",
                "review_triggers": "The host stops namespacing plugin skills.",
            }
        )
        parsed = parse_adr_bytes(result["path"], result["body"].encode("utf-8"))
        self.assertTrue(parsed.valid, parsed.errors)
        self.assertEqual(result["path"], ".breadcrumb/adr/29-operation-scoped-skills.md")

    def test_adr_renderer_keeps_the_two_relationship_fields_distinct(self) -> None:
        result = render_adr(
            {
                "issue_number": 29,
                "slug": "replacement",
                "title": "Replace an earlier decision",
                "status": "accepted",
                "supersedes": ["20-old-b.md", "19-old-a.md"],
                "superseded_by": [],
                "summary": "Replace two related decisions.",
                "context": "The earlier decisions no longer fit.",
                "affected_areas": {
                    "components": [],
                    "paths": [],
                    "resources": [],
                    "behaviors": [],
                },
                "decision": "Use the replacement.",
                "consequences": "Predecessors require reverse links in the same PR.",
                "review_triggers": "The replacement no longer applies.",
            }
        )
        self.assertIn(
            "- Supersedes: 19-old-a.md, 20-old-b.md\n- Superseded By: none",
            result["body"],
        )

    def test_implementation_renderer_matches_the_comment_parser(self) -> None:
        result = render_implementation_comment(
            {
                "issue_number": 29,
                "repository_url": REPOSITORY_URL,
                "branch": "breadcrumb/29-operation-scoped-skills",
                "commit": COMMIT,
                "verification": "passed",
                "summary": "Implemented the planned split.",
                "verification_report": "All unit tests passed.",
            }
        )
        parsed = parse_breadcrumb_comment(
            result["body"], expected_issue=29, repository_url=REPOSITORY_URL
        )
        self.assertEqual(parsed.outcome, "valid")

    def test_stale_renderer_matches_the_comment_parser(self) -> None:
        result = render_stale_comment(
            {
                "issue_number": 29,
                "repository_url": REPOSITORY_URL,
                "previous_comment_url": f"{REPOSITORY_URL}/issues/29#issuecomment-42",
                "branch": "breadcrumb/29-operation-scoped-skills",
                "commit": COMMIT,
                "reason": "The requirements changed.",
            }
        )
        parsed = parse_breadcrumb_comment(
            result["body"], expected_issue=29, repository_url=REPOSITORY_URL
        )
        self.assertEqual(parsed.outcome, "valid")
        self.assertEqual(parsed.artifact.kind, "stale")

    def test_update_renderer_supports_none_and_exact_comment_boundaries(self) -> None:
        for applied in (
            None,
            f"{REPOSITORY_URL}/issues/29#issuecomment-42",
        ):
            with self.subTest(applied=applied):
                result = render_update_comment(
                    {
                        "issue_number": 29,
                        "repository_url": REPOSITORY_URL,
                        "applied_through_url": applied,
                        "comment_prefix_sha256": "b" * 64,
                        "body_sha256": "c" * 64,
                        "summary": "Recorded the reviewed decisions.",
                    }
                )
                parsed = parse_update_comment(
                    result["body"],
                    expected_issue=29,
                    repository_url=REPOSITORY_URL,
                )
                self.assertEqual(parsed.outcome, "valid")

    def test_pull_request_renderer_preserves_the_closing_contract(self) -> None:
        result = render_pull_request(
            {
                "issue_number": 29,
                "title": "Split Breadcrumb workflow skills",
                "summary": "Expose operation-scoped skills and scripts.",
                "changes": [
                    "Add seven focused skills",
                    "ADR: .breadcrumb/adr/29-operation-scoped-skills.md",
                ],
            }
        )
        self.assertEqual(
            [line for line in result["body"].splitlines() if line.startswith("## ")],
            ["## Summary", "## Changes"],
        )
        self.assertTrue(result["body"].rstrip().endswith("Closes #29"))

    def test_pull_request_renderer_rejects_an_injected_closing_relationship(self) -> None:
        with self.assertRaisesRegex(ValueError, "closing reference"):
            render_pull_request(
                {
                    "issue_number": 29,
                    "title": "Title",
                    "summary": "Also fixes #30.",
                    "changes": ["Change"],
                }
            )

    def test_renderers_reject_unknown_fields_and_cross_issue_links(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown input fields"):
            render_pull_request(
                {
                    "issue_number": 29,
                    "title": "Title",
                    "summary": "Summary",
                    "changes": ["Change"],
                    "draft": True,
                }
            )
        with self.assertRaisesRegex(ValueError, "same work issue"):
            render_stale_comment(
                {
                    "issue_number": 29,
                    "repository_url": REPOSITORY_URL,
                    "previous_comment_url": f"{REPOSITORY_URL}/issues/30#issuecomment-42",
                    "branch": "breadcrumb/29-operation-scoped-skills",
                    "commit": COMMIT,
                    "reason": "Changed.",
                }
            )


if __name__ == "__main__":
    unittest.main()
