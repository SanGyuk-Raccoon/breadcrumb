"""Validate the fixed templates bundled with the plugin."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .documents import HEADINGS, normalize_markdown


TEMPLATE_FILES = {
    "work": "work.md",
    "comment-implementation": "comment-implementation.md",
    "comment-implementation-stale": "comment-implementation-stale.md",
    "comment-update": "comment-update.md",
    "pull-request": "pull-request.md",
}


@dataclass(frozen=True)
class TemplateProblem:
    code: str
    message: str


def _exact_nonempty_lines(value: str) -> list[str]:
    return [line for line in normalize_markdown(value).split("\n") if line.strip()]


def _require_exact_lines(
    actual: list[str], expected: list[str]
) -> list[TemplateProblem]:
    if actual == expected:
        return []
    return [
        TemplateProblem(
            "invalid_template_contract",
            "template headings, metadata, or placeholders do not match the fixed contract",
        )
    ]


def validate_template(template_type: str, value: str) -> list[TemplateProblem]:
    if template_type not in TEMPLATE_FILES:
        return [TemplateProblem("unknown_template", f"unknown template: {template_type}")]
    if not isinstance(value, str) or not value.strip():
        return [TemplateProblem("empty_template", "template is empty")]
    if "<!--" in value or "-->" in value:
        return [
            TemplateProblem(
                "forbidden_marker", "fixed templates must not contain HTML control markers"
            )
        ]

    lines = _exact_nonempty_lines(value)
    if template_type == "work":
        expected: list[str] = []
        placeholders = (
            "<background>",
            "<goal>",
            "<requirements>",
            "<design>",
            "<verification>",
            "<todo>",
        )
        for heading, placeholder in zip(HEADINGS[:-1], placeholders, strict=True):
            expected.extend((heading, placeholder))
        expected.extend(
            (
                HEADINGS[-1],
                "- Schema Version: 1",
                "- Status: <backlog-or-in-progress-or-complete>",
            )
        )
        return _require_exact_lines(lines, expected)
    if template_type == "comment-implementation":
        return _require_exact_lines(
            lines,
            [
                "## Breadcrumb Implementation",
                "- Schema Version: 1",
                "- Branch: [`<branch>`](<branch-url>)",
                "- Verified Commit: [`<commit>`](<commit-url>)",
                "- Verification: <passed-or-failed-or-pending>",
                "## Summary",
                "<summary>",
                "## Verification Report",
                "<verification-report>",
            ],
        )
    if template_type == "comment-implementation-stale":
        return _require_exact_lines(
            lines,
            [
                "## Breadcrumb Implementation Stale",
                "- Schema Version: 1",
                "- Previous Implementation: [comment](<comment-url>)",
                "- Branch: [`<branch>`](<branch-url>)",
                "- Verified Commit: [`<commit>`](<commit-url>)",
                "- Reason: <reason>",
            ],
        )
    if template_type == "comment-update":
        return _require_exact_lines(
            lines,
            [
                "## Breadcrumb Update",
                "- Schema Version: 1",
                "- Applied Through: [comment](<comment-url>)|none",
                "- Comment Prefix SHA-256: `<comment-prefix-sha256>`",
                "- Body SHA-256: `<body-sha256>`",
                "## Summary",
                "<summary>",
            ],
        )
    return _require_exact_lines(
        lines,
        [
            "## Summary",
            "<summary>",
            "## Changes",
            "<changes>",
            "Closes #<issue-number>",
        ],
    )


def validate_bundled_templates(plugin_root: Path) -> dict[str, object]:
    results: list[dict[str, object]] = []
    all_errors: list[dict[str, str]] = []
    for template_type, filename in TEMPLATE_FILES.items():
        path = plugin_root / "templates" / filename
        if path.is_symlink() or not path.is_file():
            problems = [TemplateProblem("template_unreadable", f"cannot read {path}")]
        else:
            problems = validate_template(template_type, path.read_text(encoding="utf-8"))
        errors = [
            {"code": problem.code, "message": problem.message} for problem in problems
        ]
        results.append(
            {
                "type": template_type,
                "path": str(path),
                "valid": not errors,
                "errors": errors,
            }
        )
        all_errors.extend(errors)
    return {"valid": not all_errors, "templates": results, "errors": all_errors}
