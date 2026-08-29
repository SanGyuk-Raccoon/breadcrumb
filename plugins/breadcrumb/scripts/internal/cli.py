"""Common CLI behavior and JSON input/output helpers."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable
from typing import NoReturn

from . import PROJECTION_VERSION
from .errors import BreadcrumbOperationalError, CliUsageError, sanitized


class JsonArgumentParser(argparse.ArgumentParser):
    """Let entry points preserve their JSON error contract."""

    def error(self, message: str) -> NoReturn:
        raise CliUsageError(message)


def positive_issue_number(value: str) -> int:
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


def absolute_executable(value: str) -> str:
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


def write_json(payload: Mapping[str, object]) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def write_diagnostic(message: object) -> None:
    sys.stderr.write(f"{sanitized(message)}\n")


def operational_error(code: str, message: object) -> dict[str, object]:
    return {
        "projection_version": PROJECTION_VERSION,
        "error": {
            "code": code,
            "message": sanitized(message),
        },
    }


def unsupported_runtime() -> int:
    message = "Breadcrumb scripts require Python 3.11 or newer"
    write_diagnostic(message)
    write_json(operational_error("unsupported_python", message))
    return 2


def run_json_action(action: Callable[[], Mapping[str, object]]) -> int:
    """Run one projection action while preserving the JSON error contract."""

    if sys.version_info < (3, 11):
        return unsupported_runtime()
    try:
        payload = action()
    except (BreadcrumbOperationalError, CliUsageError) as exc:
        write_diagnostic(exc.message)
        write_json(operational_error(exc.code, exc.message))
        return 2
    except Exception as exc:  # Preserve JSON output for unexpected failures.
        write_diagnostic(exc)
        write_json(operational_error("operational_error", exc))
        return 2
    write_json(payload)
    return 0


def read_stdin_object() -> dict[str, Any]:
    payload = json.load(sys.stdin)
    if not isinstance(payload, dict):
        raise ValueError("input must be a JSON object")
    return payload


def run_renderer(renderer: Callable[[dict[str, Any]], Mapping[str, object]]) -> int:
    """Run one pure renderer from JSON stdin to JSON stdout."""

    if sys.version_info < (3, 11):
        return unsupported_runtime()
    try:
        payload = renderer(read_stdin_object())
    except (json.JSONDecodeError, OSError, UnicodeError, ValueError) as exc:
        write_diagnostic(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    write_json(payload)
    return 0
