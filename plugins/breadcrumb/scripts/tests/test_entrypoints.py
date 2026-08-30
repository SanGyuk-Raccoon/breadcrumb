from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from support import SCRIPT_ROOT  # noqa: F401

import inspect_work_issue
import list_work_issues
import project_adrs
from internal.cli import operational_error
from internal.github import parse_target


def invoke(module: object, arguments: list[str]) -> tuple[int, dict[str, object], str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = module.main(arguments)  # type: ignore[attr-defined]
    return exit_code, json.loads(stdout.getvalue()), stderr.getvalue()


class ProjectionEntrypointTests(unittest.TestCase):
    def test_inspect_requires_one_issue_number(self) -> None:
        exit_code, payload, diagnostic = invoke(inspect_work_issue, [])
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["error"]["code"], "invalid_arguments")
        self.assertTrue(diagnostic)

    def test_entrypoints_reject_other_operation_shapes(self) -> None:
        variants = (
            (list_work_issues, ["inspect", "18"]),
            (inspect_work_issue, ["18", "--status", "complete"]),
            (project_adrs, ["list"]),
        )
        for module, arguments in variants:
            with self.subTest(module=module.__name__):
                exit_code, payload, _ = invoke(module, arguments)
                self.assertEqual(exit_code, 2)
                self.assertEqual(payload["error"]["code"], "invalid_arguments")

    def test_inspect_rejects_non_positive_or_padded_numbers(self) -> None:
        for value in ("0", "-1", "01"):
            with self.subTest(value=value):
                exit_code, payload, _ = invoke(inspect_work_issue, [value])
                self.assertEqual(exit_code, 2)
                self.assertEqual(payload["error"]["code"], "invalid_arguments")

    def test_list_emits_only_the_issue_collection_projection(self) -> None:
        with mock.patch.object(
            list_work_issues, "resolve_repository", return_value=(None, object())
        ), mock.patch.object(
            list_work_issues,
            "list_issues",
            return_value={"projection_version": 1, "issues": []},
        ) as listed:
            exit_code, payload, _ = invoke(
                list_work_issues, ["--status", "complete"]
            )
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["issues"], [])
        listed.assert_called_once_with(
            mock.ANY, status_filter="complete", include_closed=False
        )

    def test_inspect_emits_only_one_issue_projection(self) -> None:
        with mock.patch.object(
            inspect_work_issue, "resolve_repository", return_value=(None, object())
        ), mock.patch.object(
            inspect_work_issue,
            "inspect_issue",
            return_value={"projection_version": 1, "issue": {"number": 18}},
        ) as inspected:
            exit_code, payload, _ = invoke(
                inspect_work_issue, ["18", "--comments", "incremental"]
            )
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["issue"]["number"], 18)
        inspected.assert_called_once_with(mock.ANY, 18, comment_mode="incremental")

    def test_inspect_accepts_both_comment_modes(self) -> None:
        for mode in ("incremental", "all"):
            with self.subTest(mode=mode), mock.patch.object(
                inspect_work_issue, "resolve_repository", return_value=(None, object())
            ), mock.patch.object(
                inspect_work_issue,
                "inspect_issue",
                return_value={"projection_version": 1, "issue": {"number": 18}},
            ) as inspected:
                exit_code, _, _ = invoke(
                    inspect_work_issue, ["18", "--comments", mode]
                )
            self.assertEqual(exit_code, 0)
            inspected.assert_called_once_with(mock.ANY, 18, comment_mode=mode)

    def test_adr_projection_is_local_and_accepts_a_base_ref(self) -> None:
        root = Path("/tmp/repository")
        target = parse_target("github.example.test", "acme/widgets")
        expected = {
            "projection_version": 1,
            "repository": "acme/widgets",
            "valid": True,
        }
        with mock.patch.object(
            project_adrs,
            "discover_repository",
            return_value=(root, "origin", target),
        ) as discovered, mock.patch.object(
            project_adrs, "project_adr_corpus", return_value=expected
        ) as projected:
            exit_code, payload, _ = invoke(
                project_adrs, ["--compact", "--base", "origin/main"]
            )
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload, expected)
        discovered.assert_called_once_with()
        projected.assert_called_once_with(
            root,
            repository="acme/widgets",
            hostname="github.example.test",
            base_ref="origin/main",
            finder_input=None,
            compact=True,
        )

    def test_adr_finder_input_rejects_malformed_json(self) -> None:
        root = Path("/tmp/repository")
        target = parse_target("github.example.test", "acme/widgets")
        with mock.patch.object(
            project_adrs,
            "discover_repository",
            return_value=(root, "origin", target),
        ):
            exit_code, payload, _ = invoke(
                project_adrs,
                ["--base", "main", "--finder-input-json", "not-json"],
            )
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["error"]["code"], "invalid_arguments")

    def test_github_entrypoints_pass_the_canonical_cli_executable(self) -> None:
        executable = str(Path(sys.executable).resolve())
        with mock.patch.object(
            list_work_issues, "resolve_repository", return_value=(None, object())
        ) as resolved, mock.patch.object(
            list_work_issues,
            "list_issues",
            return_value={"projection_version": 1, "issues": []},
        ):
            exit_code, _, _ = invoke(
                list_work_issues, ["--gh-executable", executable]
            )
        self.assertEqual(exit_code, 0)
        resolved.assert_called_once_with(gh_executable=executable)

    def test_github_cli_executable_rejects_unsafe_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            non_executable = root / "gh"
            non_executable.write_text("not executable", encoding="utf-8")
            non_executable.chmod(0o600)
            candidates = (
                "relative/gh",
                str(root / "missing-gh"),
                str(root),
                str(non_executable),
            )
            for candidate in candidates:
                with self.subTest(candidate=candidate):
                    exit_code, payload, _ = invoke(
                        list_work_issues, ["--gh-executable", candidate]
                    )
                    self.assertEqual(exit_code, 2)
                    self.assertEqual(payload["error"]["code"], "invalid_arguments")

    def test_github_cli_executable_resolves_symlink_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            link = Path(directory) / "gh"
            link.symlink_to(Path(sys.executable).resolve())
            with mock.patch.object(
                list_work_issues, "resolve_repository", return_value=(None, object())
            ) as resolved, mock.patch.object(
                list_work_issues,
                "list_issues",
                return_value={"projection_version": 1, "issues": []},
            ):
                exit_code, _, _ = invoke(
                    list_work_issues, ["--gh-executable", str(link)]
                )
        self.assertEqual(exit_code, 0)
        resolved.assert_called_once_with(
            gh_executable=str(Path(sys.executable).resolve())
        )

    def test_python_guard_runs_before_normal_work(self) -> None:
        with mock.patch.object(sys, "version_info", (3, 10, 0)):
            exit_code, payload, _ = invoke(list_work_issues, [])
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
