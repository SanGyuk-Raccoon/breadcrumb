"""Parsing for Breadcrumb issue state blocks."""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import (
    SUPPORTED_DESIGN_DOCUMENT_SCHEMA_VERSIONS,
    SUPPORTED_REQUIREMENT_DOCUMENT_SCHEMA_VERSIONS,
)
from .footprints import normalize_markdown


STATE_START = "<!-- breadcrumb:state:start -->"
STATE_END = "<!-- breadcrumb:state:end -->"
TODO_HEADING = "## Todo"
STATUS_HEADING = "## Breadcrumb Status"

_TASK_RE = re.compile(r"^- \[([ x])\] \S.*$")
_STATUS_FIELD_RE = re.compile(r"^- ([A-Za-z][A-Za-z ]*): (\S.*)$")
_ISSUE_REFERENCE_RE = re.compile(r"^#([1-9][0-9]*)$")


@dataclass(frozen=True)
class DocumentProblem(Exception):
    code: str
    message: str
    line: int | None = None

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class IssueStatus:
    schema_version: int
    issue_type: str
    phase: str
    related_requirement: int | None
    refined_from: int | None
    last_step: str


def _single_line(lines: list[str], value: str, missing_code: str) -> int:
    matches = [index for index, line in enumerate(lines) if line == value]
    if not matches:
        raise DocumentProblem(missing_code, f"{value} is missing")
    if len(matches) > 1:
        raise DocumentProblem(
            "duplicate_marker" if value in {STATE_START, STATE_END} else "invalid_heading",
            f"{value} appears more than once",
            matches[1] + 1,
        )
    return matches[0]


def parse_issue_status(body: object, expected_type: str) -> IssueStatus:
    """Parse and validate the reserved final state block in an issue body."""

    if not isinstance(body, str):
        raise DocumentProblem("missing_marker", "issue body is missing")
    lines = normalize_markdown(body).split("\n")
    start = _single_line(lines, STATE_START, "missing_marker")
    end = _single_line(lines, STATE_END, "missing_marker")
    if start >= end:
        raise DocumentProblem(
            "invalid_marker_order", "state start marker must precede state end marker"
        )
    if any(line.strip() for line in lines[end + 1 :]):
        raise DocumentProblem(
            "invalid_marker_order",
            "nothing may follow the state end marker",
            end + 2,
        )

    block = lines[start + 1 : end]
    todo_relative = _single_line(block, TODO_HEADING, "missing_heading")
    status_relative = _single_line(block, STATUS_HEADING, "missing_heading")
    if todo_relative >= status_relative:
        raise DocumentProblem(
            "invalid_heading_order", "Todo must precede Breadcrumb Status"
        )

    has_unchecked = False
    for relative, line in enumerate(block[todo_relative + 1 : status_relative]):
        if not line.strip():
            continue
        match = _TASK_RE.fullmatch(line)
        absolute_line = start + todo_relative + relative + 3
        if not match:
            raise DocumentProblem(
                "invalid_todo",
                "Todo may contain only valid Markdown task-list items",
                absolute_line,
            )
        if match.group(1) == " ":
            has_unchecked = True

    fields: dict[str, tuple[str, int]] = {}
    field_order: list[str] = []
    for relative, line in enumerate(block[status_relative + 1 :]):
        if not line.strip():
            continue
        absolute_line = start + status_relative + relative + 3
        match = _STATUS_FIELD_RE.fullmatch(line)
        if not match:
            raise DocumentProblem(
                "invalid_status", "Breadcrumb Status contains an invalid line", absolute_line
            )
        name, value = match.groups()
        if name in fields:
            raise DocumentProblem(
                "duplicate_field",
                f"Breadcrumb Status field {name} appears more than once",
                absolute_line,
            )
        fields[name] = (value, absolute_line)
        field_order.append(name)

    base_required = ["Schema Version", "Type", "Phase"]
    for name in base_required:
        if name not in fields:
            raise DocumentProblem(
                "missing_field", f"Breadcrumb Status field {name} is missing"
            )

    issue_type = fields["Type"][0]
    if issue_type not in {"requirement", "design"} or issue_type != expected_type:
        raise DocumentProblem(
            "invalid_type",
            f"Breadcrumb Type must be {expected_type}",
            fields["Type"][1],
        )

    supported_versions = (
        SUPPORTED_REQUIREMENT_DOCUMENT_SCHEMA_VERSIONS
        if expected_type == "requirement"
        else SUPPORTED_DESIGN_DOCUMENT_SCHEMA_VERSIONS
    )
    schema_value = fields["Schema Version"][0]
    allowed_schema_values = {str(version) for version in supported_versions}
    if schema_value not in allowed_schema_values:
        allowed = " or ".join(sorted(allowed_schema_values))
        raise DocumentProblem(
            "invalid_schema_version",
            f"Breadcrumb Schema Version must be {allowed} for {expected_type}",
            fields["Schema Version"][1],
        )
    schema_version = int(schema_value)

    required = list(base_required)
    if expected_type == "design":
        required.extend(("Related Requirement", "Refined From"))
    elif schema_version == 1:
        required.append("Refined From")
    required.append("Last Breadcrumb Step")
    for name in required:
        if name not in fields:
            raise DocumentProblem(
                "missing_field", f"Breadcrumb Status field {name} is missing"
            )
    unknown = [name for name in field_order if name not in required]
    if unknown:
        name = unknown[0]
        raise DocumentProblem(
            "unknown_field",
            f"unknown Breadcrumb Status field: {name}",
            fields[name][1],
        )
    if field_order != required:
        first_mismatch = next(
            index
            for index, (actual, expected) in enumerate(zip(field_order, required))
            if actual != expected
        )
        name = field_order[first_mismatch]
        raise DocumentProblem(
            "invalid_field_order",
            "Breadcrumb Status fields do not follow the required order",
            fields[name][1],
        )

    phase = fields["Phase"][0]
    if phase not in {"draft", "ready"}:
        raise DocumentProblem(
            "invalid_phase",
            "Breadcrumb Phase must be draft or ready",
            fields["Phase"][1],
        )
    expected_phase = "draft" if has_unchecked else "ready"
    if phase != expected_phase:
        raise DocumentProblem(
            "invalid_phase",
            f"Breadcrumb Phase must be {expected_phase} for the current Todo state",
            fields["Phase"][1],
        )

    refined_from = None
    if "Refined From" in fields:
        refined_value = fields["Refined From"][0]
        if refined_value != "none":
            refined_match = _ISSUE_REFERENCE_RE.fullmatch(refined_value)
            if not refined_match:
                raise DocumentProblem(
                    "invalid_refined_from",
                    "Refined From must be none or a positive issue reference",
                    fields["Refined From"][1],
                )
            refined_from = int(refined_match.group(1))

    last_step = fields["Last Breadcrumb Step"][0]
    allowed_last_steps = {"open", "refine"} if expected_type == "requirement" else {"design"}
    if last_step not in allowed_last_steps:
        raise DocumentProblem(
            "invalid_last_step",
            f"Last Breadcrumb Step is invalid for {expected_type}",
            fields["Last Breadcrumb Step"][1],
        )

    related_requirement = None
    if expected_type == "design":
        related_match = _ISSUE_REFERENCE_RE.fullmatch(fields["Related Requirement"][0])
        if not related_match:
            raise DocumentProblem(
                "invalid_related_requirement",
                "Related Requirement must be a positive issue reference",
                fields["Related Requirement"][1],
            )
        related_requirement = int(related_match.group(1))

    return IssueStatus(
        schema_version=schema_version,
        issue_type=issue_type,
        phase=phase,
        related_requirement=related_requirement,
        refined_from=refined_from,
        last_step=last_step,
    )
