#!/usr/bin/env python3
"""List Breadcrumb work issues without mutating GitHub or the repository."""

from __future__ import annotations

import sys

from internal import WORK_STATUSES
from internal.cli import JsonArgumentParser, absolute_executable, run_json_action
from internal.github import resolve_repository
from internal.projection import list_issues


def _parser() -> JsonArgumentParser:
    parser = JsonArgumentParser(description="List Breadcrumb work issues.")
    parser.add_argument(
        "--gh-executable",
        type=absolute_executable,
        help="Absolute path to the GitHub CLI executable.",
    )
    parser.add_argument("--status", choices=WORK_STATUSES)
    parser.add_argument("--include-closed", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    def action() -> dict[str, object]:
        arguments = _parser().parse_args(argv)
        _, client = resolve_repository(gh_executable=arguments.gh_executable)
        return list_issues(
            client,
            status_filter=arguments.status,
            include_closed=arguments.include_closed,
        )

    return run_json_action(action)


if __name__ == "__main__":
    sys.exit(main())
