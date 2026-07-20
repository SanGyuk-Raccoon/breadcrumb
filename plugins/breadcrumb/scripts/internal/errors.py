"""Error types and credential-safe diagnostic helpers."""

from __future__ import annotations

import os
import re


class BreadcrumbOperationalError(Exception):
    """An invocation or external-operation failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class CliUsageError(BreadcrumbOperationalError):
    """Raised instead of allowing argparse to terminate without JSON output."""

    def __init__(self, message: str) -> None:
        super().__init__("invalid_arguments", message)


_TOKEN_PATTERNS = (
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]+\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]+\b"),
)


def sanitized(message: object) -> str:
    """Remove known credential forms from an error message."""

    result = str(message)
    for variable in ("GH_TOKEN", "GH_ENTERPRISE_TOKEN"):
        token = os.environ.get(variable)
        if token:
            result = result.replace(token, "[REDACTED]")
    for pattern in _TOKEN_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result
