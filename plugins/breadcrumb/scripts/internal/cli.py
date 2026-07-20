"""Common CLI behavior and JSON output helpers."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from typing import NoReturn

from . import SCHEMA_VERSION
from .errors import CliUsageError, sanitized


class JsonArgumentParser(argparse.ArgumentParser):
    """Argument parser that lets entry points preserve their JSON contract."""

    def error(self, message: str) -> NoReturn:
        raise CliUsageError(message)


def write_json(payload: Mapping[str, object]) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def write_diagnostic(message: object) -> None:
    sys.stderr.write(f"{sanitized(message)}\n")


def operational_error(code: str, message: object) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "error": {
            "code": code,
            "message": sanitized(message),
        },
    }
