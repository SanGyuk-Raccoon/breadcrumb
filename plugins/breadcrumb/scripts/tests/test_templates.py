from __future__ import annotations

import unittest

from support import SCRIPT_ROOT

from internal.comments import parse_breadcrumb_comment, parse_update_comment
from internal.documents import parse_work_body
from internal.template_validation import (
    TEMPLATE_FILES,
    validate_bundled_templates,
    validate_template,
)


PLUGIN_ROOT = SCRIPT_ROOT.parent


class TemplateTests(unittest.TestCase):
    def test_all_five_bundled_templates_are_valid(self) -> None:
        result = validate_bundled_templates(PLUGIN_ROOT)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(len(result["templates"]), 5)
        self.assertEqual(set(TEMPLATE_FILES), {
            "work",
            "comment-implementation",
            "comment-implementation-stale",
            "comment-update",
            "pull-request",
        })

    def test_fixed_templates_reject_markers_and_shape_changes(self) -> None:
        work = (PLUGIN_ROOT / "templates" / "work.md").read_text(encoding="utf-8")
        self.assertTrue(validate_template("work", "<!-- marker -->\n" + work))
        self.assertTrue(validate_template("work", work.replace("## Goal", "## Objective")))
        pull = (PLUGIN_ROOT / "templates" / "pull-request.md").read_text(encoding="utf-8")
        self.assertTrue(validate_template("pull-request", pull.replace("Closes", "Fixes")))
        update = (PLUGIN_ROOT / "templates" / "comment-update.md").read_text(
            encoding="utf-8"
        )
        self.assertTrue(
            validate_template(
                "comment-update",
                update.replace(
                    "- Comment Prefix SHA-256: `<comment-prefix-sha256>`\n", ""
                ),
            )
        )

    def test_rendered_work_template_matches_document_parser(self) -> None:
        rendered = (PLUGIN_ROOT / "templates" / "work.md").read_text(encoding="utf-8")
        replacements = {
            "<background>": "Context.",
            "<goal>": "Outcome.",
            "<requirements>": "- Required behavior.",
            "<design>": "Use the existing component.",
            "<verification>": "Run unit tests.",
            "<todo>": "- [x] Planning completed.",
            "<backlog-or-in-progress-or-complete>": "complete",
        }
        for source, target in replacements.items():
            rendered = rendered.replace(source, target)
        result = parse_work_body(rendered)
        self.assertTrue(result.valid, result.errors)

    def test_rendered_implementation_template_matches_comment_parser(self) -> None:
        rendered = (PLUGIN_ROOT / "templates" / "comment-implementation.md").read_text(
            encoding="utf-8"
        )
        replacements = {
            "<branch>": "breadcrumb/18-example",
            "<branch-url>": "https://github.com/acme/widgets/tree/breadcrumb/18-example",
            "<commit>": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "<commit-url>": "https://github.com/acme/widgets/commit/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "<passed-or-failed-or-pending>": "passed",
            "<summary>": "Implemented the change.",
            "<verification-report>": "Unit tests passed.",
        }
        for source, target in replacements.items():
            rendered = rendered.replace(source, target)
        result = parse_breadcrumb_comment(
            rendered,
            expected_issue=18,
            repository_url="https://github.com/acme/widgets",
        )
        self.assertEqual(result.outcome, "valid")

    def test_rendered_update_template_matches_comment_parser(self) -> None:
        rendered = (PLUGIN_ROOT / "templates" / "comment-update.md").read_text(
            encoding="utf-8"
        )
        rendered = rendered.replace(
            "[comment](<comment-url>)|none",
            "[comment](https://github.com/acme/widgets/issues/18#issuecomment-100)",
        )
        rendered = rendered.replace("<comment-prefix-sha256>", "b" * 64)
        rendered = rendered.replace("<body-sha256>", "a" * 64)
        rendered = rendered.replace("<summary>", "Applied the reviewed decisions.")
        result = parse_update_comment(
            rendered,
            expected_issue=18,
            repository_url="https://github.com/acme/widgets",
        )
        self.assertEqual(result.outcome, "valid")


if __name__ == "__main__":
    unittest.main()
