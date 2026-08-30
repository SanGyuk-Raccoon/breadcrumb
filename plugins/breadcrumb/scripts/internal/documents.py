"""Parse the small machine-readable portion of a Breadcrumb work issue."""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import WORK_SCHEMA_VERSION, WORK_STATUSES


HEADINGS = (
    "## Background",
    "## Goal",
    "## Requirements",
    "## Design",
    "## Verification",
    "## Todo",
    "## Breadcrumb Status",
)
NARRATIVE_HEADINGS = HEADINGS[:5]
TODO_HEADING = "## Todo"
STATUS_HEADING = "## Breadcrumb Status"

_LEVEL_TWO_HEADING_RE = re.compile(r"^##(?:\s|$).*$")
_UP_TO_LEVEL_FOUR_HEADING_RE = re.compile(r"^#{1,4}(?:\s|$).*$")
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(?:.*)$")
_TASK_RE = re.compile(r"^- \[([ xX])\] (\S(?:.*\S)?)$")
_TODO_ID_RE = re.compile(r"^(T[1-9][0-9]*): +(\S(?:.*\S)?)$")
_TODO_KIND_RE = re.compile(r"^(Decision|Action): +(\S(?:.*\S)?)$")
_DECISION_BRIEF_HEADING_RE = re.compile(
    r"^#### +(T[1-9][0-9]*) +— +(\S(?:.*\S)?)$"
)
_DECISION_BRIEF_FIELD_RE = re.compile(
    r"^- (Why|Options|Recommendation|Uncertainty|Reply example):(?: +(.*))?$"
)
_FIELD_RE = re.compile(r"^- ([A-Za-z][A-Za-z ]*): (\S(?:.*\S)?)$")

_DECISION_BRIEF_FIELDS = (
    "Why",
    "Options",
    "Recommendation",
    "Uncertainty",
    "Reply example",
)
_COMPLETE_SECTION_PLACEHOLDERS = frozenset(
    {
        "<background>",
        "<goal>",
        "<requirements>",
        "<design>",
        "<verification>",
        "tbd",
        "todo",
        "unknown",
        "pending",
        "none",
        "n/a",
    }
)


def normalize_markdown(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


@dataclass(frozen=True)
class DocumentError:
    code: str
    message: str
    line: int | None = None

    def as_dict(self) -> dict[str, object]:
        result: dict[str, object] = {"code": self.code, "message": self.message}
        if self.line is not None:
            result["line"] = self.line
        return result


@dataclass(frozen=True)
class DocumentWarning:
    code: str
    message: str
    line: int

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "message": self.message, "line": self.line}


@dataclass(frozen=True)
class TodoItem:
    id: str | None
    checked: bool
    text: str
    line: int

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "checked": self.checked,
            "text": self.text,
            "line": self.line,
        }


@dataclass(frozen=True)
class WorkDocument:
    schema_version: int | None
    status: str | None
    resolved: int
    unresolved: int
    items: tuple[TodoItem, ...]
    warnings: tuple[DocumentWarning, ...]
    errors: tuple[DocumentError, ...]

    @property
    def valid(self) -> bool:
        return not self.errors

    def projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "todo": {
                "resolved": self.resolved,
                "unresolved": self.unresolved,
                "items": [item.as_dict() for item in self.items],
            },
            "warnings": [warning.as_dict() for warning in self.warnings],
            "valid": self.valid,
            "errors": [problem.as_dict() for problem in self.errors],
        }


def _problem(
    problems: list[DocumentError], code: str, message: str, line: int | None = None
) -> None:
    candidate = DocumentError(code, message, line)
    if candidate not in problems:
        problems.append(candidate)


def _visible_lines(lines: list[str]) -> list[bool]:
    """Return which lines are outside Markdown fenced code blocks."""

    visible: list[bool] = []
    fence_character: str | None = None
    fence_length = 0
    for line in lines:
        if fence_character is None:
            match = _FENCE_RE.fullmatch(line)
            if match is None:
                visible.append(True)
                continue
            marker = match.group(1)
            fence_character = marker[0]
            fence_length = len(marker)
            visible.append(False)
            continue
        visible.append(False)
        closing = line.lstrip(" ")
        if len(line) - len(closing) <= 3:
            marker = closing.rstrip()
            if (
                marker
                and set(marker) == {fence_character}
                and len(marker) >= fence_length
            ):
                fence_character = None
                fence_length = 0
    return visible


def _heading_positions(
    lines: list[str], visible: list[bool], problems: list[DocumentError]
) -> dict[str, int]:
    positions: dict[str, int] = {}
    expected = set(HEADINGS)
    for heading in HEADINGS:
        matches = [
            index
            for index, line in enumerate(lines)
            if visible[index] and line == heading
        ]
        if not matches:
            _problem(problems, "missing_heading", f"{heading} is missing")
        elif len(matches) > 1:
            _problem(
                problems,
                "duplicate_heading",
                f"{heading} appears more than once",
                matches[1] + 1,
            )
        else:
            positions[heading] = matches[0]

    for index, line in enumerate(lines):
        if (
            visible[index]
            and _LEVEL_TWO_HEADING_RE.fullmatch(line)
            and line not in expected
        ):
            _problem(
                problems,
                "unexpected_heading",
                f"unexpected level-two heading: {line}",
                index + 1,
            )

    if len(positions) == len(HEADINGS):
        actual = [positions[heading] for heading in HEADINGS]
        if actual != sorted(actual):
            _problem(
                problems,
                "invalid_heading_order",
                "work issue headings do not follow the required order",
            )
        first = positions[HEADINGS[0]]
        before = next((index for index, line in enumerate(lines[:first]) if line.strip()), None)
        if before is not None:
            _problem(
                problems,
                "content_before_background",
                "nothing may precede the Background heading",
                before + 1,
            )
    return positions


def _parse_todo(
    lines: list[str], positions: dict[str, int], problems: list[DocumentError]
) -> tuple[int, int, tuple[TodoItem, ...], tuple[DocumentWarning, ...]]:
    if TODO_HEADING not in positions or STATUS_HEADING not in positions:
        return 0, 0, (), ()
    start = positions[TODO_HEADING]
    end = positions[STATUS_HEADING]
    if start >= end:
        return 0, 0, (), ()

    resolved = 0
    unresolved = 0
    items: list[TodoItem] = []
    warnings: list[DocumentWarning] = []
    seen_ids: set[str] = set()
    for index in range(start + 1, end):
        line = lines[index]
        if not line.strip():
            continue
        match = _TASK_RE.fullmatch(line)
        if not match:
            _problem(
                problems,
                "invalid_todo",
                "Todo may contain only Markdown task-list items",
                index + 1,
            )
            continue
        checked = match.group(1) != " "
        if not checked:
            unresolved += 1
        else:
            resolved += 1

        text = match.group(2)
        identifier: str | None = None
        identifier_match = _TODO_ID_RE.fullmatch(text)
        if identifier_match is None:
            warnings.append(
                DocumentWarning(
                    "missing_todo_id",
                    "Todo item does not start with a canonical T<number>: identifier",
                    index + 1,
                )
            )
        else:
            identifier, text = identifier_match.groups()
            if identifier in seen_ids:
                _problem(
                    problems,
                    "duplicate_todo_id",
                    f"Todo ID {identifier} appears more than once",
                    index + 1,
                )
            else:
                seen_ids.add(identifier)
            if _TODO_KIND_RE.fullmatch(text) is None:
                warnings.append(
                    DocumentWarning(
                        "missing_todo_kind",
                        "Todo item does not declare Decision: or Action: after its canonical ID",
                        index + 1,
                    )
                )
        items.append(TodoItem(identifier, checked, text, index + 1))
    return resolved, unresolved, tuple(items), tuple(warnings)


def _validate_complete_sections(
    lines: list[str], positions: dict[str, int], problems: list[DocumentError]
) -> None:
    if any(heading not in positions for heading in HEADINGS):
        return
    for heading, following in zip(
        NARRATIVE_HEADINGS, HEADINGS[1 : len(NARRATIVE_HEADINGS) + 1], strict=True
    ):
        start = positions[heading] + 1
        end = positions[following]
        content = "\n".join(lines[start:end]).strip()
        section = heading.removeprefix("## ")
        if not content:
            _problem(
                problems,
                "empty_required_section",
                f"complete requires non-empty {section} content",
                positions[heading] + 1,
            )
        elif content.casefold() in _COMPLETE_SECTION_PLACEHOLDERS:
            line = next(
                (index + 1 for index in range(start, end) if lines[index].strip()),
                positions[heading] + 1,
            )
            _problem(
                problems,
                "placeholder_required_section",
                f"complete {section} content is a reserved placeholder",
                line,
            )


def _decision_briefs(
    lines: list[str], positions: dict[str, int], visible: list[bool]
) -> dict[str, list[tuple[int, dict[str, list[tuple[str, int]]]]]]:
    briefs: dict[str, list[tuple[int, dict[str, list[tuple[str, int]]]]]] = {}
    if any(heading not in positions for heading in HEADINGS):
        return briefs

    for heading, following in zip(
        NARRATIVE_HEADINGS, HEADINGS[1 : len(NARRATIVE_HEADINGS) + 1], strict=True
    ):
        index = positions[heading] + 1
        end = positions[following]
        while index < end:
            match = (
                _DECISION_BRIEF_HEADING_RE.fullmatch(lines[index])
                if visible[index]
                else None
            )
            if match is None:
                index += 1
                continue

            identifier = match.group(1)
            heading_line = index + 1
            fields: dict[str, list[tuple[str, int]]] = {}
            index += 1
            while index < end:
                if visible[index] and _UP_TO_LEVEL_FOUR_HEADING_RE.fullmatch(
                    lines[index]
                ):
                    break
                field_match = (
                    _DECISION_BRIEF_FIELD_RE.fullmatch(lines[index])
                    if visible[index]
                    else None
                )
                if field_match is not None:
                    name, value = field_match.groups()
                    fields.setdefault(name, []).append(((value or "").strip(), index + 1))
                index += 1
            briefs.setdefault(identifier, []).append((heading_line, fields))
    return briefs


def _validate_decision_briefs(
    lines: list[str],
    positions: dict[str, int],
    visible: list[bool],
    items: tuple[TodoItem, ...],
    problems: list[DocumentError],
) -> None:
    briefs = _decision_briefs(lines, positions, visible)
    for item in items:
        if item.checked or item.id is None:
            continue
        kind = _TODO_KIND_RE.fullmatch(item.text)
        if kind is None or kind.group(1) != "Decision":
            continue

        matches = briefs.get(item.id, [])
        if not matches:
            _problem(
                problems,
                "missing_decision_brief",
                f"unresolved Decision Todo {item.id} requires a same-ID Decision Brief",
                item.line,
            )
            continue
        if len(matches) > 1:
            _problem(
                problems,
                "duplicate_decision_brief",
                f"Decision Brief ID {item.id} appears more than once",
                matches[1][0],
            )
            continue

        heading_line, fields = matches[0]
        malformed = [
            name
            for name in _DECISION_BRIEF_FIELDS
            if len(fields.get(name, [])) != 1 or not fields[name][0][0]
        ]
        if malformed:
            _problem(
                problems,
                "invalid_decision_brief",
                f"Decision Brief {item.id} requires one non-empty {', '.join(malformed)} field",
                heading_line,
            )


def _parse_status(
    lines: list[str], positions: dict[str, int], problems: list[DocumentError]
) -> tuple[int | None, str | None]:
    if STATUS_HEADING not in positions:
        return None, None

    fields: dict[str, tuple[str, int]] = {}
    field_order: list[str] = []
    for index in range(positions[STATUS_HEADING] + 1, len(lines)):
        line = lines[index]
        if not line.strip():
            continue
        match = _FIELD_RE.fullmatch(line)
        if not match:
            _problem(
                problems,
                "invalid_status_line",
                "Breadcrumb Status contains an invalid line",
                index + 1,
            )
            continue
        name, value = match.groups()
        if name in fields:
            _problem(
                problems,
                "duplicate_field",
                f"Breadcrumb Status field {name} appears more than once",
                index + 1,
            )
            continue
        fields[name] = (value, index + 1)
        field_order.append(name)

    required = ["Schema Version", "Status"]
    for name in required:
        if name not in fields:
            _problem(
                problems,
                "missing_field",
                f"Breadcrumb Status field {name} is missing",
            )
    for name in field_order:
        if name not in required:
            _problem(
                problems,
                "unknown_field",
                f"unknown Breadcrumb Status field: {name}",
                fields[name][1],
            )
    if all(name in fields for name in required) and field_order != required:
        _problem(
            problems,
            "invalid_field_order",
            "Breadcrumb Status fields do not follow the required order",
        )

    schema_version: int | None = None
    if "Schema Version" in fields:
        value, line = fields["Schema Version"]
        if not value.isdecimal() or value.startswith("0"):
            _problem(
                problems,
                "invalid_schema_version",
                "Breadcrumb Schema Version must be a positive decimal integer",
                line,
            )
        else:
            schema_version = int(value)
            if schema_version != WORK_SCHEMA_VERSION:
                _problem(
                    problems,
                    "unsupported_schema_version",
                    f"Breadcrumb Schema Version {schema_version} is not supported",
                    line,
                )

    status: str | None = None
    if "Status" in fields:
        value, line = fields["Status"]
        if value not in WORK_STATUSES:
            _problem(
                problems,
                "invalid_status",
                "Breadcrumb Status must be backlog, in-progress, or complete",
                line,
            )
        else:
            status = value
    return schema_version, status


def parse_work_body(body: object) -> WorkDocument:
    """Return a projection even when an individual body is malformed."""

    problems: list[DocumentError] = []
    if not isinstance(body, str) or not body.strip():
        _problem(problems, "missing_body", "issue body is missing")
        return WorkDocument(None, None, 0, 0, (), (), tuple(problems))

    lines = normalize_markdown(body).split("\n")
    visible = _visible_lines(lines)
    positions = _heading_positions(lines, visible, problems)
    resolved, unresolved, items, warnings = _parse_todo(lines, positions, problems)
    schema_version, status = _parse_status(lines, positions, problems)

    _validate_decision_briefs(lines, positions, visible, items, problems)

    if status == "in-progress" and unresolved == 0:
        _problem(
            problems,
            "status_todo_mismatch",
            "in-progress requires at least one unresolved Todo",
        )
    elif status == "complete" and unresolved != 0:
        _problem(
            problems,
            "status_todo_mismatch",
            "complete requires zero unresolved Todo items",
        )
    if status == "complete":
        _validate_complete_sections(lines, positions, problems)

    return WorkDocument(
        schema_version,
        status,
        resolved,
        unresolved,
        items,
        warnings,
        tuple(problems),
    )
