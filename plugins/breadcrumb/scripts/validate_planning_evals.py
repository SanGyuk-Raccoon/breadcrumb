#!/usr/bin/env python3
"""Validate issue-planning scenario catalogs and public result summaries."""

from __future__ import annotations

import sys
from pathlib import Path

from internal.cli import JsonArgumentParser, unsupported_runtime, write_diagnostic, write_json
from internal.errors import CliUsageError
from internal.evals import (
    EvaluationInputError,
    input_error_projection,
    read_json_file,
    validate_evaluation,
)


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = PLUGIN_ROOT / "evals" / "scenarios.json"


def _parser() -> JsonArgumentParser:
    parser = JsonArgumentParser(
        description="Validate issue-planning scenarios and public result summaries."
    )
    parser.add_argument(
        "--catalog",
        default=str(DEFAULT_CATALOG),
        help="Scenario catalog JSON path. Defaults to the bundled catalog.",
    )
    parser.add_argument(
        "--result",
        action="append",
        default=[],
        help="Captured public result JSON path. May be repeated.",
    )
    return parser


def _failure(code: str, path: str, message: str) -> int:
    error = EvaluationInputError(code, path, message)
    write_diagnostic(message)
    write_json(input_error_projection(error))
    return 2


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < (3, 11):
        return unsupported_runtime()
    try:
        arguments = _parser().parse_args(argv)
    except CliUsageError as exc:
        return _failure(exc.code, "<arguments>", exc.message)

    catalog_path = Path(arguments.catalog)
    try:
        catalog_payload = read_json_file(catalog_path)
        result_payloads = [
            (value, read_json_file(Path(value))) for value in arguments.result
        ]
    except EvaluationInputError as exc:
        return _failure(exc.code, exc.path, exc.message)

    projection = validate_evaluation(
        catalog_payload,
        result_payloads,
        catalog_source=str(catalog_path),
    )
    write_json(projection)
    if not projection["valid"]:
        return 2
    if not projection["passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
