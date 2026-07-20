"""Resolution and contract validation for active Breadcrumb templates."""

from __future__ import annotations

import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from . import SCHEMA_VERSION
from .documents import STATE_END, STATE_START, STATUS_HEADING, TODO_HEADING
from .errors import BreadcrumbOperationalError
from .footprints import (
    count_footprints,
    normalize_markdown,
    validate_template_footprint,
)


TEMPLATE_TYPES = (
    "requirement",
    "design",
    "comment-refine",
    "comment-implementation",
    "pull-request",
)

_STATUS_FIELD_RE = re.compile(r"^- ([A-Za-z][A-Za-z ]*): (\S.*)$")
_VERIFICATION_HEADING_RE = re.compile(
    r"^#{1,6}[ \t]+Verification Report[ \t]*$", re.MULTILINE
)
_CLOSES_RE = re.compile(r"(?im)^\s*closes\s+#[^\s]+\s*$")
_ISSUE_REFERENCE_RE = re.compile(r"^#[1-9][0-9]*$")


@dataclass(frozen=True)
class ValidationError:
    template: str
    code: str
    message: str
    line: int | None = None

    def as_json(self) -> dict[str, object]:
        return {
            "template": self.template,
            "code": self.code,
            "line": self.line,
            "message": self.message,
        }


class _TemplateReadError(Exception):
    pass


def _error(
    template: str, code: str, message: str, line: int | None = None
) -> ValidationError:
    return ValidationError(template, code, message, line)


def _validate_state_template(template: str, text: str) -> list[ValidationError]:
    lines = normalize_markdown(text).split("\n")
    errors: list[ValidationError] = []

    starts = [index for index, line in enumerate(lines) if line == STATE_START]
    ends = [index for index, line in enumerate(lines) if line == STATE_END]
    if not starts:
        errors.append(_error(template, "missing_marker", "breadcrumb:state:start marker is missing"))
    elif len(starts) > 1:
        errors.append(
            _error(
                template,
                "duplicate_marker",
                "breadcrumb:state:start marker appears more than once",
                starts[1] + 1,
            )
        )
    if not ends:
        errors.append(_error(template, "missing_marker", "breadcrumb:state:end marker is missing"))
    elif len(ends) > 1:
        errors.append(
            _error(
                template,
                "duplicate_marker",
                "breadcrumb:state:end marker appears more than once",
                ends[1] + 1,
            )
        )
    start = starts[0] if len(starts) == 1 else None
    end = ends[0] if len(ends) == 1 else None
    ordered = start is not None and end is not None and start < end
    if start is not None and end is not None and start >= end:
        errors.append(
            _error(
                template,
                "invalid_marker_order",
                "breadcrumb:state:start must precede breadcrumb:state:end",
                start + 1,
            )
        )
    if end is not None and any(line.strip() for line in lines[end + 1 :]):
        errors.append(
            _error(
                template,
                "invalid_marker_order",
                "nothing may follow breadcrumb:state:end",
                end + 2,
            )
        )

    if ordered:
        scope_start, scope_end = start + 1, end
    elif start is not None:
        scope_start, scope_end = start + 1, len(lines)
    elif end is not None:
        scope_start, scope_end = 0, end
    else:
        scope_start, scope_end = 0, len(lines)

    block_indices = range(scope_start, scope_end)
    todo = [index for index in block_indices if lines[index] == TODO_HEADING]
    status = [index for index in block_indices if lines[index] == STATUS_HEADING]
    if len(todo) != 1:
        message = "Todo heading is missing" if not todo else "Todo heading appears more than once"
        errors.append(
            _error(template, "missing_heading", message, None if not todo else todo[1] + 1)
        )
    if len(status) != 1:
        message = (
            "Breadcrumb Status heading is missing"
            if not status
            else "Breadcrumb Status heading appears more than once"
        )
        errors.append(
            _error(
                template,
                "missing_heading",
                message,
                None if not status else status[1] + 1,
            )
        )
    if len(todo) != 1 or len(status) != 1:
        return errors
    if todo[0] >= status[0]:
        errors.append(
            _error(
                template,
                "invalid_marker_order",
                "Todo must precede Breadcrumb Status",
                todo[0] + 1,
            )
        )
        return errors

    fields: dict[str, list[tuple[str, int]]] = {}
    field_order: list[str] = []
    for index in range(status[0] + 1, scope_end):
        if not lines[index].strip():
            continue
        match = _STATUS_FIELD_RE.fullmatch(lines[index])
        if not match:
            errors.append(
                _error(
                    template,
                    "missing_field",
                    "Breadcrumb Status contains an invalid field line",
                    index + 1,
                )
            )
            continue
        name, value = match.groups()
        fields.setdefault(name, []).append((value, index + 1))
        field_order.append(name)

    required = [
        "Schema Version",
        "Type",
        "Phase",
        "Refined From",
        "Last Breadcrumb Step",
    ]
    if template == "design":
        required.insert(3, "Related Requirement")
    for name in required:
        values = fields.get(name, [])
        if not values:
            errors.append(
                _error(
                    template,
                    "missing_field",
                    f"Breadcrumb Status field {name} is missing",
                )
            )
        elif len(values) > 1:
            errors.append(
                _error(
                    template,
                    "missing_field",
                    f"Breadcrumb Status field {name} appears more than once",
                    values[1][1],
                )
            )

    unknown = [name for name in field_order if name not in required]
    for name in dict.fromkeys(unknown):
        errors.append(
            _error(
                template,
                "missing_field",
                f"unknown Breadcrumb Status field {name}",
                fields[name][0][1],
            )
        )
    if (
        not unknown
        and all(len(fields.get(name, [])) == 1 for name in required)
        and field_order != required
    ):
        mismatch = next(
            index
            for index, (actual, expected) in enumerate(zip(field_order, required))
            if actual != expected
        )
        errors.append(
            _error(
                template,
                "missing_field",
                "Breadcrumb Status fields do not follow the required order",
                fields[field_order[mismatch]][0][1],
            )
        )

    type_values = fields.get("Type", [])
    if len(type_values) == 1 and type_values[0][0] != template:
        errors.append(
            _error(
                template,
                "invalid_type",
                f"Breadcrumb Status Type must be {template}",
                type_values[0][1],
            )
        )
    version_values = fields.get("Schema Version", [])
    if len(version_values) == 1 and version_values[0][0] != "1":
        errors.append(
            _error(
                template,
                "missing_field",
                "Breadcrumb Status Schema Version must be 1",
                version_values[0][1],
            )
        )

    phase_values = fields.get("Phase", [])
    if len(phase_values) == 1 and phase_values[0][0] not in {
        "draft",
        "ready",
        "<draft-or-ready>",
    }:
        errors.append(
            _error(
                template,
                "missing_field",
                "Breadcrumb Status Phase value is invalid",
                phase_values[0][1],
            )
        )
    refined_values = fields.get("Refined From", [])
    if len(refined_values) == 1 and not (
        refined_values[0][0] in {"none", "<issue-reference-or-none>"}
        or _ISSUE_REFERENCE_RE.fullmatch(refined_values[0][0])
    ):
        errors.append(
            _error(
                template,
                "missing_field",
                "Breadcrumb Status Refined From value is invalid",
                refined_values[0][1],
            )
        )
    last_values = fields.get("Last Breadcrumb Step", [])
    allowed_last = (
        {"open", "refine", "<open-or-refine>"}
        if template == "requirement"
        else {"design"}
    )
    if len(last_values) == 1 and last_values[0][0] not in allowed_last:
        errors.append(
            _error(
                template,
                "missing_field",
                "Breadcrumb Status Last Breadcrumb Step value is invalid",
                last_values[0][1],
            )
        )
    if template == "design":
        related_values = fields.get("Related Requirement", [])
        if len(related_values) == 1 and not (
            related_values[0][0] == "#<requirement-issue-number>"
            or _ISSUE_REFERENCE_RE.fullmatch(related_values[0][0])
        ):
            errors.append(
                _error(
                    template,
                    "missing_field",
                    "Breadcrumb Status Related Requirement value is invalid",
                    related_values[0][1],
                )
            )
    return errors


def validate_template(template: str, text: str) -> list[ValidationError]:
    if template in {"requirement", "design"}:
        return _validate_state_template(template, text)

    if template in {"comment-refine", "comment-implementation"}:
        expected_step = "refine" if template == "comment-refine" else "implement"
        errors = [
            _error(template, problem.code, problem.message, problem.line)
            for problem in validate_template_footprint(text, expected_step)
        ]
        if template == "comment-implementation":
            headings = list(_VERIFICATION_HEADING_RE.finditer(normalize_markdown(text)))
            if len(headings) != 1:
                message = (
                    "Verification Report heading is missing"
                    if not headings
                    else "Verification Report heading appears more than once"
                )
                line = None
                if len(headings) > 1:
                    line = normalize_markdown(text)[: headings[1].start()].count("\n") + 1
                errors.append(_error(template, "missing_heading", message, line))
        return errors

    if template == "pull-request":
        errors: list[ValidationError] = []
        if not text.strip():
            errors.append(_error(template, "empty_template", "pull request template is empty"))
        if count_footprints(text):
            errors.append(
                _error(
                    template,
                    "forbidden_pr_metadata",
                    "pull request template must not contain a Breadcrumb footprint",
                )
            )
        closes = _CLOSES_RE.search(normalize_markdown(text))
        if closes:
            line = normalize_markdown(text)[: closes.start()].count("\n") + 1
            errors.append(
                _error(
                    template,
                    "forbidden_pr_metadata",
                    "pull request template must not contain a Closes reference",
                    line,
                )
            )
        return errors

    raise BreadcrumbOperationalError("invalid_template_type", f"unsupported template type: {template}")


def _lexists(path: Path) -> bool:
    try:
        return os.path.lexists(path)
    except OSError as exc:
        raise BreadcrumbOperationalError(
            "filesystem_error", f"could not inspect template path: {exc}"
        ) from exc


def _read_regular_template(path: Path, expected_directory: Path, root: Path) -> str:
    current = expected_directory
    while current != root:
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise _TemplateReadError(exc.strerror or str(exc)) from exc
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise _TemplateReadError("template directory path is not a regular directory")
        if root not in current.parents:
            raise _TemplateReadError("template directory escapes its expected root")
        current = current.parent

    try:
        metadata = path.lstat()
    except OSError as exc:
        raise _TemplateReadError(exc.strerror or str(exc)) from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise _TemplateReadError("template path is not a regular non-symlink file")

    try:
        resolved_directory = expected_directory.resolve(strict=True)
        resolved_path = path.resolve(strict=True)
    except OSError as exc:
        raise _TemplateReadError(exc.strerror or str(exc)) from exc
    if not resolved_path.is_relative_to(resolved_directory):
        raise _TemplateReadError("template path escapes its expected template directory")

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        descriptor = os.open(path, flags)
        opened_metadata = os.fstat(descriptor)
        if not stat.S_ISREG(opened_metadata.st_mode):
            raise _TemplateReadError("template path is not a regular file")
        with os.fdopen(descriptor, "r", encoding="utf-8") as source:
            descriptor = -1
            return source.read()
    except (OSError, UnicodeError) as exc:
        reason = exc.strerror if isinstance(exc, OSError) and exc.strerror else str(exc)
        raise _TemplateReadError(reason) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def validate_active_templates(
    selected: Iterable[str], *, repository_root: Path, plugin_root: Path
) -> dict[str, object]:
    templates: list[dict[str, object]] = []
    all_errors: list[ValidationError] = []

    for template in selected:
        filename = f"{template}.md"
        repository_path = repository_root / ".breadcrumb" / "templates" / filename
        plugin_path = plugin_root / "templates" / filename

        source: str | None
        path: Path | None
        display_path: str | None
        if _lexists(repository_path):
            source = "repository"
            path = repository_path
            display_path = f".breadcrumb/templates/{filename}"
        elif _lexists(plugin_path):
            source = "plugin"
            path = plugin_path
            display_path = f"templates/{filename}"
        else:
            source = None
            path = None
            display_path = None

        errors: list[ValidationError]
        if path is None:
            errors = [
                _error(
                    template,
                    "template_not_found",
                    f"{filename} was not found in the repository or plugin templates",
                )
            ]
        else:
            try:
                expected_directory = path.parent
                source_root = repository_root if source == "repository" else plugin_root
                text = _read_regular_template(path, expected_directory, source_root)
            except _TemplateReadError as exc:
                errors = [
                    _error(
                        template,
                        "template_unreadable",
                        f"could not read {display_path}: {exc}",
                    )
                ]
            else:
                errors = validate_template(template, text)

        valid = not errors
        templates.append(
            {
                "type": template,
                "source": source,
                "path": display_path,
                "valid": valid,
            }
        )
        all_errors.extend(errors)

    return {
        "schema_version": SCHEMA_VERSION,
        "valid": not all_errors,
        "templates": templates,
        "errors": [error.as_json() for error in all_errors],
    }
