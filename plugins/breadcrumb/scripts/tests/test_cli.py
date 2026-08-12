from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import unittest
from unittest import mock

from support import SCRIPT_ROOT  # noqa: F401

import breadcrumb
from internal.cli import operational_error


def invoke(arguments: list[str]) -> tuple[int, dict[str, object], str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = breadcrumb.main(arguments)
    return exit_code, json.loads(stdout.getvalue()), stderr.getvalue()


class CliTests(unittest.TestCase):
    def test_requires_a_subcommand(self) -> None:
        exit_code, payload, diagnostic = invoke([])
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["projection_version"], 1)
        self.assertEqual(payload["error"]["code"], "invalid_arguments")
        self.assertTrue(diagnostic)

    def test_inspect_rejects_non_positive_or_padded_numbers(self) -> None:
        for value in ("0", "-1", "01"):
            with self.subTest(value=value):
                exit_code, payload, _ = invoke(["inspect", value])
                self.assertEqual(exit_code, 2)
                self.assertEqual(payload["error"]["code"], "invalid_arguments")

    def test_list_and_inspect_emit_projection_json(self) -> None:
        with mock.patch.object(breadcrumb, "resolve_repository", return_value=(None, object())), mock.patch.object(
            breadcrumb,
            "list_issues",
            return_value={"projection_version": 1, "issues": []},
        ) as listed:
            exit_code, payload, _ = invoke(["list", "--status", "complete"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["issues"], [])
        listed.assert_called_once_with(
            mock.ANY, status_filter="complete", include_closed=False
        )

        with mock.patch.object(breadcrumb, "resolve_repository", return_value=(None, object())), mock.patch.object(
            breadcrumb,
            "inspect_issue",
            return_value={"projection_version": 1, "issue": {"number": 18}},
        ) as inspected:
            exit_code, payload, _ = invoke(["inspect", "18"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["issue"]["number"], 18)
        inspected.assert_called_once_with(mock.ANY, 18, comment_mode=None)

    def test_inspect_accepts_explicit_comment_modes(self) -> None:
        for mode in ("incremental", "all"):
            with self.subTest(mode=mode), mock.patch.object(
                breadcrumb, "resolve_repository", return_value=(None, object())
            ), mock.patch.object(
                breadcrumb,
                "inspect_issue",
                return_value={"projection_version": 1, "issue": {"number": 18}},
            ) as inspected:
                exit_code, payload, _ = invoke(["inspect", "18", "--comments", mode])
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["issue"]["number"], 18)
            inspected.assert_called_once_with(mock.ANY, 18, comment_mode=mode)

    def test_inspect_rejects_unknown_comment_mode(self) -> None:
        exit_code, payload, _ = invoke(["inspect", "18", "--comments", "recent"])
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["error"]["code"], "invalid_arguments")

    def test_python_guard_runs_before_normal_work(self) -> None:
        with mock.patch.object(sys, "version_info", (3, 10, 0)):
            exit_code, payload, _ = invoke(["list"])
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["error"]["code"], "unsupported_python")

    def test_operational_errors_redact_tokens(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"GH_TOKEN": "github_pat_secret", "GH_ENTERPRISE_TOKEN": "enterprise-secret"},
        ):
            payload = operational_error(
                "github_api_error",
                "github_pat_secret enterprise-secret gho_othersecret",
            )
        encoded = json.dumps(payload)
        self.assertNotIn("github_pat_secret", encoded)
        self.assertNotIn("enterprise-secret", encoded)
        self.assertNotIn("gho_othersecret", encoded)
        self.assertIn("[REDACTED]", encoded)


if __name__ == "__main__":
    unittest.main()
