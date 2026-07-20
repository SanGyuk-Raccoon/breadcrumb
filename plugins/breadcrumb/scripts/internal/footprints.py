"""Parser for Breadcrumb's restricted line-based comment footprints."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


BRANCH_RE = re.compile(r"^breadcrumb/([1-9][0-9]*)-[a-z0-9][a-z0-9-]*$")
_FIELD_RE = re.compile(r"^  ([a-z][a-z0-9_]*): (.+)$")
_OBJECT_ID_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_POSITIVE_INTEGER_RE = re.compile(r"^[1-9][0-9]*$")
_VERIFICATION_VALUES = {"passed", "failed", "instruction-error", "pending"}
_FIELDS_BY_STEP = {
    "refine": {"version", "step", "issue", "replacement_issue"},
    "implement": {"version", "step", "issue", "branch", "commit", "verification"},
    "pr": {"version", "step", "issue", "branch"},
}
_TEMPLATE_VALUES_BY_STEP = {
    "refine": {
        "issue": "<source-issue-number>",
        "replacement_issue": "<replacement-issue-number>",
    },
    "implement": {
        "issue": "<design-issue-number>",
        "branch": "<implementation-branch>",
        "commit": "<verified-head-sha>",
        "verification": "<passed-or-failed-or-instruction-error-or-pending>",
    },
}


@dataclass(frozen=True)
class Footprint:
    version: int
    step: str
    issue: int
    branch: str | None = None
    commit: str | None = None
    verification: str | None = None
    replacement_issue: int | None = None


@dataclass(frozen=True)
class FootprintResult:
    outcome: Literal["not-breadcrumb", "valid", "invalid"]
    footprint: Footprint | None = None
    message: str | None = None
    line: int | None = None


@dataclass(frozen=True)
class TemplateFootprintProblem:
    code: str
    message: str
    line: int | None = None


@dataclass(frozen=True)
class _Candidate:
    start: int
    end: int | None


def normalize_markdown(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def parse_branch(value: str) -> int | None:
    match = BRANCH_RE.fullmatch(value)
    if not match:
        return None
    number = int(match.group(1))
    return number if number > 0 else None


def _candidates(lines: list[str]) -> list[_Candidate]:
    candidates: list[_Candidate] = []
    for index in range(len(lines) - 1):
        if lines[index] != "<!--" or lines[index + 1] != "breadcrumb:":
            continue
        end = None
        for closing in range(index + 2, len(lines)):
            if lines[closing] == "-->":
                end = closing
                break
        candidates.append(_Candidate(index, end))
    return candidates


def count_footprints(value: str) -> int:
    return len(_candidates(normalize_markdown(value).split("\n")))


def _invalid(message: str, line: int | None = None) -> FootprintResult:
    return FootprintResult("invalid", message=message, line=line)


def parse_footprint(
    value: str,
    *,
    expected_step: str | None = None,
    expected_issue: int | None = None,
    expected_branch: str | None = None,
    require_pr_closes: bool = False,
) -> FootprintResult:
    """Parse a rendered footprint and optionally validate its GitHub context."""

    text = normalize_markdown(value)
    lines = text.split("\n")
    first = next((index for index, line in enumerate(lines) if line.strip()), None)
    if first is None:
        return FootprintResult("not-breadcrumb")
    if (
        lines[first] != "<!--"
        or first + 1 >= len(lines)
        or lines[first + 1] != "breadcrumb:"
    ):
        return FootprintResult("not-breadcrumb")

    candidates = _candidates(lines)
    if len(candidates) > 1:
        return _invalid("the body contains more than one Breadcrumb footprint")
    if not candidates or candidates[0].start != first:
        return _invalid("the Breadcrumb footprint is malformed", first + 1)
    candidate = candidates[0]
    if candidate.end is None:
        return _invalid("the Breadcrumb footprint is missing its closing marker", first + 1)

    fields: dict[str, str] = {}
    for index in range(candidate.start + 2, candidate.end):
        match = _FIELD_RE.fullmatch(lines[index])
        if not match:
            return _invalid(
                "footprint fields must use exactly two spaces, a key, and a non-empty value",
                index + 1,
            )
        key, field_value = match.groups()
        if key in fields:
            return _invalid(f"duplicate footprint field: {key}", index + 1)
        fields[key] = field_value

    step = fields.get("step")
    if step not in _FIELDS_BY_STEP:
        return _invalid("footprint step must be refine, implement, or pr")
    expected_fields = _FIELDS_BY_STEP[step]
    missing = sorted(expected_fields - fields.keys())
    unknown = sorted(fields.keys() - expected_fields)
    if missing:
        return _invalid(f"missing footprint field: {missing[0]}")
    if unknown:
        return _invalid(f"unknown footprint field: {unknown[0]}")
    if fields["version"] != "1":
        return _invalid("footprint version must be 1")
    if expected_step is not None and step != expected_step:
        return _invalid(f"footprint step must be {expected_step}")
    if not _POSITIVE_INTEGER_RE.fullmatch(fields["issue"]):
        return _invalid("footprint issue must be a positive decimal integer")

    issue = int(fields["issue"])
    if expected_issue is not None and issue != expected_issue:
        return _invalid(
            f"footprint issue #{issue} does not match context issue #{expected_issue}"
        )

    replacement_issue: int | None = None
    branch: str | None = None
    commit: str | None = None
    verification: str | None = None

    if step == "refine":
        replacement = fields["replacement_issue"]
        if not _POSITIVE_INTEGER_RE.fullmatch(replacement):
            return _invalid("replacement_issue must be a positive decimal integer")
        replacement_issue = int(replacement)
    else:
        branch = fields["branch"]
        branch_issue = parse_branch(branch)
        if branch_issue is None:
            return _invalid("footprint branch is not a Breadcrumb implementation branch")
        if branch_issue != issue:
            return _invalid("the issue encoded in branch does not match footprint issue")
        if expected_branch is not None and branch != expected_branch:
            return _invalid("footprint branch does not match the GitHub context")

    if step == "implement":
        commit = fields["commit"]
        if not _OBJECT_ID_RE.fullmatch(commit):
            return _invalid("footprint commit must be a full lowercase Git object ID")
        verification = fields["verification"]
        if verification not in _VERIFICATION_VALUES:
            return _invalid("footprint verification value is invalid")

    if step == "pr" and require_pr_closes:
        final = next((line for line in reversed(lines) if line.strip()), "")
        if final != f"Closes #{issue}":
            return _invalid(f"the final line must be Closes #{issue}")

    return FootprintResult(
        "valid",
        footprint=Footprint(
            version=1,
            step=step,
            issue=issue,
            branch=branch,
            commit=commit,
            verification=verification,
            replacement_issue=replacement_issue,
        ),
    )


def validate_template_footprint(
    value: str, expected_step: str
) -> list[TemplateFootprintProblem]:
    """Validate footprint structure while allowing documented template placeholders."""

    lines = normalize_markdown(value).split("\n")
    candidates = _candidates(lines)
    if not candidates:
        return [
            TemplateFootprintProblem(
                "missing_footprint", "Breadcrumb footprint is missing", None
            )
        ]
    if len(candidates) > 1:
        return [
            TemplateFootprintProblem(
                "duplicate_footprint",
                "template contains more than one Breadcrumb footprint",
                candidates[1].start + 1,
            )
        ]

    candidate = candidates[0]
    first = next((index for index, line in enumerate(lines) if line.strip()), None)
    if first != candidate.start:
        return [
            TemplateFootprintProblem(
                "missing_footprint",
                "Breadcrumb footprint must be the first non-empty block",
                candidate.start + 1,
            )
        ]
    if candidate.end is None:
        return [
            TemplateFootprintProblem(
                "missing_footprint",
                "Breadcrumb footprint closing marker is missing",
                candidate.start + 1,
            )
        ]

    problems: list[TemplateFootprintProblem] = []
    fields: dict[str, tuple[str, int]] = {}
    for index in range(candidate.start + 2, candidate.end):
        match = _FIELD_RE.fullmatch(lines[index])
        if not match:
            problems.append(
                TemplateFootprintProblem(
                    "missing_field",
                    "footprint field syntax is invalid",
                    index + 1,
                )
            )
            continue
        key, field_value = match.groups()
        if key in fields:
            problems.append(
                TemplateFootprintProblem(
                    "missing_field",
                    f"footprint field {key} appears more than once",
                    index + 1,
                )
            )
        else:
            fields[key] = (field_value, index + 1)

    expected_fields = _FIELDS_BY_STEP[expected_step]
    for field in sorted(expected_fields - fields.keys()):
        problems.append(
            TemplateFootprintProblem(
                "missing_field", f"footprint field {field} is missing", None
            )
        )
    for field in sorted(fields.keys() - expected_fields):
        problems.append(
            TemplateFootprintProblem(
                "missing_field",
                f"unknown footprint field {field}",
                fields[field][1],
            )
        )

    if "version" in fields and fields["version"][0] != "1":
        problems.append(
            TemplateFootprintProblem(
                "missing_field", "footprint version must be 1", fields["version"][1]
            )
        )
    if "step" in fields and fields["step"][0] != expected_step:
        problems.append(
            TemplateFootprintProblem(
                "invalid_footprint_step",
                f"footprint step must be {expected_step}",
                fields["step"][1],
            )
        )
    for field, expected_value in _TEMPLATE_VALUES_BY_STEP.get(expected_step, {}).items():
        if field in fields and fields[field][0] != expected_value:
            problems.append(
                TemplateFootprintProblem(
                    "missing_field",
                    f"footprint field {field} must use {expected_value}",
                    fields[field][1],
                )
            )
    return problems
