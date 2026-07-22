"""Minimal Breadcrumb issue-number collection."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from . import SCRIPT_OUTPUT_SCHEMA_VERSION
from .errors import BreadcrumbOperationalError
from .github import GitHubClient


REQUIREMENT_LABEL = "breadcrumb:requirement"
DESIGN_LABEL = "breadcrumb:design"


def label_names(issue: Mapping[str, Any]) -> set[str]:
    labels = issue.get("labels")
    if not isinstance(labels, list):
        raise BreadcrumbOperationalError(
            "invalid_github_response", "an issue contains malformed label metadata"
        )
    names: set[str] = set()
    for label in labels:
        if isinstance(label, str):
            names.add(label)
        elif isinstance(label, dict) and isinstance(label.get("name"), str):
            names.add(label["name"])
        else:
            raise BreadcrumbOperationalError(
                "invalid_github_response", "an issue contains malformed label metadata"
            )
    return names


def _number(issue: Mapping[str, Any]) -> int:
    number = issue.get("number")
    if not isinstance(number, int) or isinstance(number, bool) or number <= 0:
        raise BreadcrumbOperationalError(
            "invalid_github_response", "an issue is missing a valid number"
        )
    return number


def list_issue_numbers(client: GitHubClient, type_filter: str) -> dict[str, object]:
    if type_filter not in {"all", "requirement", "design"}:
        raise BreadcrumbOperationalError(
            "invalid_type_filter", "type filter must be all, requirement, or design"
        )

    labels = []
    if type_filter in {"all", "requirement"}:
        labels.append(REQUIREMENT_LABEL)
    if type_filter in {"all", "design"}:
        labels.append(DESIGN_LABEL)

    issues_by_number: dict[int, Mapping[str, Any]] = {}
    for label in labels:
        for issue in client.issues_with_label(label):
            if "pull_request" in issue:
                continue
            issues_by_number[_number(issue)] = issue

    requirements: list[int] = []
    designs: list[int] = []
    invalid: list[dict[str, object]] = []
    for number in sorted(issues_by_number):
        names = label_names(issues_by_number[number])
        has_requirement = REQUIREMENT_LABEL in names
        has_design = DESIGN_LABEL in names
        if has_requirement and has_design:
            invalid.append(
                {
                    "number": number,
                    "code": "conflicting_type_labels",
                    "message": (
                        "issue has both breadcrumb:requirement and breadcrumb:design labels"
                    ),
                }
            )
        elif has_requirement and type_filter in {"all", "requirement"}:
            requirements.append(number)
        elif has_design and type_filter in {"all", "design"}:
            designs.append(number)

    return {
        "schema_version": SCRIPT_OUTPUT_SCHEMA_VERSION,
        "hostname": client.target.hostname,
        "repository": client.target.identity,
        "filter": type_filter,
        "requirements": requirements,
        "designs": designs,
        "invalid": invalid,
    }
