from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import SCRIPT_ROOT

from internal.template_validation import (
    TEMPLATE_TYPES,
    validate_active_templates,
    validate_template,
)


PLUGIN_ROOT = SCRIPT_ROOT.parent


class TemplateValidationTests(unittest.TestCase):
    def test_bundled_templates_are_valid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = validate_active_templates(
                TEMPLATE_TYPES,
                repository_root=Path(directory),
                plugin_root=PLUGIN_ROOT,
            )
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["templates"]), 5)
        self.assertTrue(all(item["source"] == "plugin" for item in result["templates"]))

    def test_repository_override_is_selected_independently(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            override = root / ".breadcrumb" / "templates"
            override.mkdir(parents=True)
            override.joinpath("requirement.md").write_text(
                (PLUGIN_ROOT / "templates" / "requirement.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            result = validate_active_templates(
                TEMPLATE_TYPES, repository_root=root, plugin_root=PLUGIN_ROOT
            )
        sources = {item["type"]: item["source"] for item in result["templates"]}
        self.assertEqual(sources["requirement"], "repository")
        self.assertEqual(sources["design"], "plugin")

    def test_invalid_override_does_not_fall_back(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            override = root / ".breadcrumb" / "templates"
            override.mkdir(parents=True)
            override.joinpath("design.md").write_text("## Technical Design\n", encoding="utf-8")
            result = validate_active_templates(
                ("design",), repository_root=root, plugin_root=PLUGIN_ROOT
            )
        self.assertFalse(result["valid"])
        self.assertEqual(result["templates"][0]["source"], "repository")
        self.assertIn("missing_marker", {error["code"] for error in result["errors"]})

    def test_repository_override_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            override = root / ".breadcrumb" / "templates"
            override.mkdir(parents=True)
            override.joinpath("requirement.md").symlink_to(
                PLUGIN_ROOT / "templates" / "requirement.md"
            )
            result = validate_active_templates(
                ("requirement",), repository_root=root, plugin_root=PLUGIN_ROOT
            )
        self.assertFalse(result["valid"])
        self.assertEqual(result["errors"][0]["code"], "template_unreadable")

    def test_missing_and_unreadable_templates_have_stable_errors(self) -> None:
        with tempfile.TemporaryDirectory() as repository, tempfile.TemporaryDirectory() as plugin:
            missing = validate_active_templates(
                ("requirement",),
                repository_root=Path(repository),
                plugin_root=Path(plugin),
            )
            path = Path(plugin) / "templates" / "requirement.md"
            path.mkdir(parents=True)
            unreadable = validate_active_templates(
                ("requirement",),
                repository_root=Path(repository),
                plugin_root=Path(plugin),
            )
        self.assertEqual(missing["errors"][0]["code"], "template_not_found")
        self.assertEqual(unreadable["errors"][0]["code"], "template_unreadable")

    def test_contract_errors_are_structured(self) -> None:
        requirement = (PLUGIN_ROOT / "templates" / "requirement.md").read_text(
            encoding="utf-8"
        )
        errors = validate_template(
            "requirement",
            requirement.replace("- Type: requirement", "- Type: design").replace(
                "<!-- breadcrumb:state:end -->", ""
            ),
        )
        self.assertEqual(
            {error.code for error in errors}, {"missing_marker", "invalid_type"}
        )

        pull_errors = validate_template(
            "pull-request", "## Summary\n\nCloses #123\n"
        )
        self.assertEqual(pull_errors[0].code, "forbidden_pr_metadata")

    def test_ordinary_template_content_is_not_executed_or_interpreted(self) -> None:
        pull = "## Summary\n\n`$(touch should-not-exist)` is ordinary Markdown.\n"
        self.assertEqual(validate_template("pull-request", pull), [])

    def test_state_template_rejects_inexact_and_reordered_machine_lines(self) -> None:
        requirement = (PLUGIN_ROOT / "templates" / "requirement.md").read_text(
            encoding="utf-8"
        )
        variants = (
            requirement.replace("## Todo", " ## Todo"),
            requirement.replace(
                "- Schema Version: 1\n- Type: requirement",
                "- Type: requirement\n- Schema Version: 1",
            ),
            requirement.replace(
                "- Last Breadcrumb Step: <open-or-refine>",
                "- Extra: value\n- Last Breadcrumb Step: <open-or-refine>",
            ),
        )
        for variant in variants:
            with self.subTest():
                self.assertTrue(validate_template("requirement", variant))


if __name__ == "__main__":
    unittest.main()
