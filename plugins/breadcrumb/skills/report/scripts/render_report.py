#!/usr/bin/env python3
"""Render one validated schema-1 backlog issue from sanitized report fields."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[3]
PLUGIN_SCRIPT_ROOT = PLUGIN_ROOT / "scripts"
sys.path.insert(0, str(PLUGIN_SCRIPT_ROOT))

from internal.cli import run_renderer  # noqa: E402
from internal.documents import normalize_markdown  # noqa: E402
from internal.rendering import render_work_issue  # noqa: E402


TODO = "- [ ] 보고 내용을 구현 가능한 요구사항, 설계와 검증 계획으로 정제한다."
CONTROL_FIELD_RE = re.compile(
    r"^ {0,3}- (?:Schema Version|Status|Branch|Verified Commit|Verification|"
    r"Previous Implementation|Reason):(?:\s|$)"
)
LEVEL_TWO_RE = re.compile(r"^ {0,3}##(?:\s|$)")
COMMON_FIELDS = {
    "report_type",
    "title",
    "constraints",
    "acceptance_conditions",
    "design",
    "verification",
}
BUG_FIELDS = COMMON_FIELDS | {
    "summary",
    "actual_behavior",
    "expected_behavior",
    "reproduction_context",
}
FEATURE_FIELDS = COMMON_FIELDS | {
    "problem_or_opportunity",
    "desired_behavior",
    "context",
    "expected_value",
}


def _value(payload: dict[str, Any], key: str, *, required: bool = False) -> str:
    raw = payload.get(key, "")
    if not isinstance(raw, str):
        raise ValueError(f"{key} must be a string")
    value = normalize_markdown(raw).strip()
    if required and not value:
        raise ValueError(f"{key} is required")
    if "\x00" in value:
        raise ValueError(f"{key} contains a null byte")
    for line in value.split("\n"):
        if LEVEL_TWO_RE.match(line):
            raise ValueError(f"{key} contains a reserved level-two heading")
        if CONTROL_FIELD_RE.match(line):
            raise ValueError(f"{key} contains Breadcrumb control metadata")
        if "<!--" in line and "breadcrumb" in line.casefold():
            raise ValueError(f"{key} contains Breadcrumb control metadata")
    return value


def _section(name: str, value: str) -> str:
    return f"### {name}\n\n{value}"


def _sections(items: list[tuple[str, str]]) -> str:
    return "\n\n".join(_section(name, value) for name, value in items if value)


def render_report(payload: dict[str, Any]) -> dict[str, object]:
    report_type = _value(payload, "report_type", required=True)
    if report_type == "Bug":
        allowed = BUG_FIELDS
    elif report_type == "Feature Request":
        allowed = FEATURE_FIELDS
    else:
        raise ValueError("report_type must be Bug or Feature Request")
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(f"unknown input fields: {', '.join(unknown)}")

    title = _value(payload, "title", required=True)
    if "\n" in title:
        raise ValueError("title must be one line")
    design = _value(payload, "design")
    verification = _value(payload, "verification")
    constraints = _value(payload, "constraints")
    acceptance = _value(payload, "acceptance_conditions")

    if report_type == "Bug":
        background = _sections(
            [
                ("Report Type", report_type),
                ("Summary", _value(payload, "summary", required=True)),
                ("Actual Behavior", _value(payload, "actual_behavior", required=True)),
                (
                    "Reproduction Context",
                    _value(payload, "reproduction_context", required=True),
                ),
            ]
        )
        goal = _section(
            "Expected Behavior", _value(payload, "expected_behavior", required=True)
        )
        requirements = _sections(
            [("Constraints", constraints), ("Acceptance Conditions", acceptance)]
        )
    else:
        background = _sections(
            [
                ("Report Type", report_type),
                (
                    "Problem or Opportunity",
                    _value(payload, "problem_or_opportunity", required=True),
                ),
                ("Context", _value(payload, "context", required=True)),
            ]
        )
        goal = _section(
            "Desired Behavior", _value(payload, "desired_behavior", required=True)
        )
        requirements = _sections(
            [
                ("Expected Value", _value(payload, "expected_value", required=True)),
                ("Constraints", constraints),
                ("Acceptance Conditions", acceptance),
            ]
        )

    rendered = render_work_issue(
        {
            "title": title,
            "background": background,
            "goal": goal,
            "requirements": requirements,
            "design": design,
            "verification": verification,
            "todo": [TODO],
            "status": "backlog",
        }
    )
    return {**rendered, "report_type": report_type}


if __name__ == "__main__":
    raise SystemExit(run_renderer(render_report))
