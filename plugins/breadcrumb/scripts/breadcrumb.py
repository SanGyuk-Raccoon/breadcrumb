#!/usr/bin/env python3
"""Read-only Breadcrumb work issue projection CLI."""

from __future__ import annotations

import json
import sys


def _unsupported_runtime() -> int:
    message = "Breadcrumb scripts require Python 3.11 or newer"
    sys.stderr.write(f"{message}\n")
    json.dump(
        {
            "projection_version": 1,
            "error": {"code": "unsupported_python", "message": message},
        },
        sys.stdout,
        indent=2,
    )
    sys.stdout.write("\n")
    return 2


if sys.version_info < (3, 11) and __name__ == "__main__":
    sys.exit(_unsupported_runtime())

import argparse
import os
from pathlib import Path

from internal import WORK_STATUSES
from internal.cli import JsonArgumentParser, operational_error, write_diagnostic, write_json
from internal.errors import BreadcrumbOperationalError, CliUsageError
from internal.github import resolve_repository
from internal.projection import inspect_issue, list_issues


def _positive_issue_number(value: str) -> int:
    try:
        number = int(value, 10)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "issue number must be a positive decimal integer"
        ) from exc
    if number <= 0 or str(number) != value:
        raise argparse.ArgumentTypeError(
            "issue number must be a positive decimal integer"
        )
    return number


def _absolute_executable(value: str) -> str:
    path = Path(value)
    message = "GitHub CLI executable must be an absolute path to an executable file"
    if not path.is_absolute():
        raise argparse.ArgumentTypeError(message)
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise argparse.ArgumentTypeError(message) from exc
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise argparse.ArgumentTypeError(message)
    return str(resolved)


def _parser() -> JsonArgumentParser:
    parser = JsonArgumentParser(description="Inspect Breadcrumb work issues.")
    parser.add_argument(
        "--gh-executable",
        type=_absolute_executable,
        help="Absolute path to the GitHub CLI executable.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    list_parser = commands.add_parser("list", help="List Breadcrumb work issues.")
    list_parser.add_argument("--status", choices=WORK_STATUSES)
    list_parser.add_argument("--include-closed", action="store_true")

    inspect_parser = commands.add_parser("inspect", help="Inspect one work issue.")
    inspect_parser.add_argument("issue_number", type=_positive_issue_number)
    inspect_parser.add_argument("--comments", choices=("incremental", "all"))
    return parser


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < (3, 11):
        return _unsupported_runtime()
    try:
        arguments = _parser().parse_args(argv)
        _, client = resolve_repository(gh_executable=arguments.gh_executable)
        if arguments.command == "list":
            payload = list_issues(
                client,
                status_filter=arguments.status,
                include_closed=arguments.include_closed,
            )
        else:
            payload = inspect_issue(
                client,
                arguments.issue_number,
                comment_mode=arguments.comments,
            )
    except (BreadcrumbOperationalError, CliUsageError) as exc:
        write_diagnostic(exc.message)
        write_json(operational_error(exc.code, exc.message))
        return 2
    except Exception as exc:  # Preserve JSON output for unexpected operational failures.
        write_diagnostic(exc)
        write_json(operational_error("operational_error", exc))
        return 2

    write_json(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
