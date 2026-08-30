#!/usr/bin/env python3
"""Inspect one Breadcrumb work issue without mutating GitHub or the repository."""

from __future__ import annotations

import sys

from internal.cli import (
    JsonArgumentParser,
    absolute_executable,
    positive_issue_number,
    run_json_action,
)
from internal.github import resolve_repository
from internal.projection import inspect_issue


def _parser() -> JsonArgumentParser:
    parser = JsonArgumentParser(description="Inspect one Breadcrumb work issue.")
    parser.add_argument("issue_number", type=positive_issue_number)
    parser.add_argument(
        "--gh-executable",
        type=absolute_executable,
        help="Absolute path to the GitHub CLI executable.",
    )
    parser.add_argument("--comments", choices=("incremental", "all"))
    return parser


def main(argv: list[str] | None = None) -> int:
    def action() -> dict[str, object]:
        arguments = _parser().parse_args(argv)
        context, client = resolve_repository(gh_executable=arguments.gh_executable)
        return inspect_issue(
            client,
            arguments.issue_number,
            default_branch=context.default_branch,
            comment_mode=arguments.comments,
        )

    return run_json_action(action)


if __name__ == "__main__":
    sys.exit(main())
