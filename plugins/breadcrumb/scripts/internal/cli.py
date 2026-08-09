"""Common CLI behavior and JSON output helpers."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from typing import NoReturn

from . import PROJECTION_VERSION
from .errors import CliUsageError, sanitized


class JsonArgumentParser(argparse.ArgumentParser):
    """Let entry points preserve their JSON error contract."""

    def error(self, message: str) -> NoReturn:
        raise CliUsageError(message)


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
