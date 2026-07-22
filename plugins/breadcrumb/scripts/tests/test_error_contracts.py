from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import unittest
from unittest import mock

from support import SCRIPT_ROOT  # noqa: F401

import get_breadcrumb_issue_progress as progress_cli
import list_breadcrumb_issue_numbers as list_cli
import validate_breadcrumb_templates as template_cli
from internal.cli import operational_error


def invoke(main: object, arguments: list[str]) -> tuple[int, dict[str, object], str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = main(arguments)
    return exit_code, json.loads(stdout.getvalue()), stderr.getvalue()


class ErrorContractTests(unittest.TestCase):
    def test_list_requires_explicit_hostname_and_repository(self) -> None:
        exit_code, payload, diagnostic = invoke(list_cli.main, [])
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["error"]["code"], "invalid_arguments")
        self.assertTrue(diagnostic)

    def test_progress_rejects_non_positive_issue_number_as_json(self) -> None:
        exit_code, payload, _ = invoke(
            progress_cli.main,
            ["--hostname", "github.com", "--repository", "acme/widgets", "0"],
        )
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["error"]["code"], "invalid_arguments")

    def test_template_rejects_unsupported_type_as_json(self) -> None:
        exit_code, payload, _ = invoke(template_cli.main, ["unknown"])
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["error"]["code"], "invalid_arguments")

    def test_template_rejects_removed_comment_refine_type(self) -> None:
        exit_code, payload, _ = invoke(template_cli.main, ["comment-refine"])
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["error"]["code"], "invalid_arguments")

    def test_operational_error_redacts_environment_token(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "GH_TOKEN": "github_pat_secretvalue",
                "GH_ENTERPRISE_TOKEN": "enterprise-secret-value",
            },
        ):
            payload = operational_error(
                "github_api_error",
                "request failed for github_pat_secretvalue enterprise-secret-value gho_othersecret",
            )
        self.assertNotIn("github_pat_secretvalue", json.dumps(payload))
        self.assertNotIn("enterprise-secret-value", json.dumps(payload))
        self.assertNotIn("gho_othersecret", json.dumps(payload))
        self.assertIn("[REDACTED]", payload["error"]["message"])

    def test_all_public_entries_guard_python_before_argument_parsing(self) -> None:
        for module in (list_cli, progress_cli, template_cli):
            with self.subTest(module=module.__name__), mock.patch.object(
                sys, "version_info", (3, 10, 0)
            ):
                exit_code, payload, _ = invoke(module.main, [])
            self.assertEqual(exit_code, 2)
            self.assertEqual(payload["error"]["code"], "unsupported_python")


if __name__ == "__main__":
    unittest.main()
