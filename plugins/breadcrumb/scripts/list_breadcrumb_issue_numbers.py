#!/usr/bin/env python3
"""List compact Breadcrumb backlog, requirement, and design issue-number sets."""

from __future__ import annotations

import json
import sys


def _unsupported_runtime() -> int:
    message = "Breadcrumb scripts require Python 3.11 or newer"
    sys.stderr.write(f"{message}\n")
    json.dump(
        {"schema_version": 1, "error": {"code": "unsupported_python", "message": message}},
        sys.stdout,
        indent=2,
    )
    sys.stdout.write("\n")
    return 2


if sys.version_info < (3, 11) and __name__ == "__main__":
    sys.exit(_unsupported_runtime())

from internal.cli import JsonArgumentParser, operational_error, write_diagnostic, write_json
from internal.errors import BreadcrumbOperationalError
from internal.github import GitHubClient, parse_target
from internal.listing import list_issue_numbers


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < (3, 11):
        return _unsupported_runtime()
    parser = JsonArgumentParser(description="List Breadcrumb issue numbers.")
    parser.add_argument("--hostname", required=True, help="GitHub host, for example github.com")
    parser.add_argument("--repository", required=True, help="repository in owner/name form")
    parser.add_argument(
        "--type",
        choices=("all", "backlog", "requirement", "design"),
        default="all",
        dest="type_filter",
    )
    try:
        arguments = parser.parse_args(argv)
        target = parse_target(arguments.hostname, arguments.repository)
        payload = list_issue_numbers(GitHubClient(target), arguments.type_filter)
    except BreadcrumbOperationalError as exc:
        write_diagnostic(exc.message)
        write_json(operational_error(exc.code, exc.message))
        return 2
    except Exception as exc:  # Preserve the machine contract for unexpected operations.
        write_diagnostic(exc)
        write_json(operational_error("operational_error", exc))
        return 2

    write_json(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
