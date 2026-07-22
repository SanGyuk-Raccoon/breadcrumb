#!/usr/bin/env python3
"""Resolve and validate Breadcrumb's active template environment."""

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

from pathlib import Path

from internal.cli import JsonArgumentParser, operational_error, write_diagnostic, write_json
from internal.errors import BreadcrumbOperationalError, CliUsageError
from internal.template_validation import TEMPLATE_TYPES, validate_active_templates


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < (3, 11):
        return _unsupported_runtime()
    parser = JsonArgumentParser(
        description="Validate one active Breadcrumb template or the full template set."
    )
    parser.add_argument(
        "template_type",
        metavar="TEMPLATE_TYPE",
        help="requirement, design, comment-implementation, pull-request, or all",
    )
    try:
        arguments = parser.parse_args(argv)
        if arguments.template_type == "all":
            selected = TEMPLATE_TYPES
        elif arguments.template_type in TEMPLATE_TYPES:
            selected = (arguments.template_type,)
        else:
            raise CliUsageError(f"unsupported template type: {arguments.template_type}")

        plugin_root = Path(__file__).resolve().parent.parent
        payload = validate_active_templates(
            selected,
            repository_root=Path.cwd(),
            plugin_root=plugin_root,
        )
    except BreadcrumbOperationalError as exc:
        write_diagnostic(exc.message)
        write_json(operational_error(exc.code, exc.message))
        return 2
    except OSError as exc:
        write_diagnostic(exc)
        write_json(operational_error("filesystem_error", exc))
        return 2
    except Exception as exc:  # Preserve the machine contract for unexpected operations.
        write_diagnostic(exc)
        write_json(operational_error("operational_error", exc))
        return 2

    write_json(payload)
    return 0 if payload["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
