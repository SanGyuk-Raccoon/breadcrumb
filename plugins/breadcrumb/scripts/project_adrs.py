#!/usr/bin/env python3
"""Project the repository-local Breadcrumb ADR corpus without side effects."""

from __future__ import annotations

import sys

from internal.adrs import parse_finder_input_json, project_adr_corpus
from internal.cli import JsonArgumentParser, run_json_action
from internal.github import discover_repository


def _parser() -> JsonArgumentParser:
    parser = JsonArgumentParser(
        description="Project the repository-local Breadcrumb ADR corpus."
    )
    parser.add_argument(
        "--base",
        help="Optional Git ref used for structural ADR lifecycle diff validation.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Return only the ADR index, corpus metadata, and structural diff.",
    )
    parser.add_argument(
        "--finder-input-json",
        help="Exact compact planning input used to rank every ADR without filtering.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    def action() -> dict[str, object]:
        arguments = _parser().parse_args(argv)
        root, _, target = discover_repository()
        finder_input = (
            parse_finder_input_json(arguments.finder_input_json)
            if arguments.finder_input_json is not None
            else None
        )
        return project_adr_corpus(
            root,
            repository=target.identity,
            hostname=target.hostname,
            base_ref=arguments.base,
            finder_input=finder_input,
            compact=arguments.compact,
        )

    return run_json_action(action)


if __name__ == "__main__":
    sys.exit(main())
