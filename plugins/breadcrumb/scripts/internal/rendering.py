"""Pure renderers for Breadcrumb's fixed Markdown artifacts."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from . import ADR_STATUSES, BREADCRUMB_LABEL, WORK_STATUSES
from .adrs import parse_adr_bytes
from .comments import parse_breadcrumb_comment, parse_branch, parse_update_comment
from .documents import normalize_markdown, parse_work_body
from .template_validation import validate_template


PLUGIN_ROOT = Path(__file__).resolve().parents[2]
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_OBJECT_ID_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_TASK_RE = re.compile(r"^- \[([ xX])\] \S(?:.*\S)?$")
_COMMENT_URL_RE = re.compile(r"^https://[^\s/]+/[^\s/]+/[^\s/]+/issues/([1-9][0-9]*)#issuecomment-([1-9][0-9]*)$")
_CLOSING_REFERENCE_RE = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+"
    r"(?:[^\s/#]+/[^\s/#]+)?#[1-9][0-9]*\b",
    re.IGNORECASE,
)

_PLACEHOLDERS = frozenset(
    {
        "<background>",
        "<goal>",
        "<requirements>",
        "<design>",
        "<verification>",
        "<todo>",
        "<backlog-or-in-progress-or-complete>",
        "<title>",
        "<accepted-or-superseded-or-deprecated>",
        "<number>",
        "<none-or-sorted-adr-basenames>",
        "<summary>",
        "<context>",
        "<components-or-none>",
        "<paths-or-none>",
        "<resources-or-none>",
        "<behaviors-or-none>",
        "<decision>",
        "<consequences>",
        "<review-triggers>",
        "<branch>",
        "<branch-url>",
        "<commit>",
        "<commit-url>",
        "<passed-or-failed-or-pending>",
        "<verification-report>",
        "<comment-url>",
        "<reason>",
        "<comment-prefix-sha256>",
        "<body-sha256>",
        "<changes>",
        "<issue-number>",
    }
)


def _require_shape(
    payload: dict[str, Any], *, required: set[str], optional: set[str] | None = None
) -> None:
    allowed = required | (optional or set())
    unknown = sorted(set(payload) - allowed)
    missing = sorted(required - set(payload))
    if unknown:
        raise ValueError(f"unknown input fields: {', '.join(unknown)}")
    if missing:
        raise ValueError(f"missing input fields: {', '.join(missing)}")


def _text(
    payload: dict[str, Any], key: str, *, required: bool = True, one_line: bool = False
) -> str:
    raw = payload.get(key, "")
    if not isinstance(raw, str):
        raise ValueError(f"{key} must be a string")
    value = normalize_markdown(raw).strip()
    if required and not value:
        raise ValueError(f"{key} is required")
    if "\x00" in value:
        raise ValueError(f"{key} contains a null byte")
    if one_line and "\n" in value:
        raise ValueError(f"{key} must be one line")
    if any(token in value for token in _PLACEHOLDERS):
        raise ValueError(f"{key} contains a reserved template placeholder")
    return value


def _positive_integer(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{key} must be a positive integer")
    return value


def _narrative(payload: dict[str, Any], key: str) -> str:
    value = _text(payload, key)
    if any(line.startswith("## ") for line in value.splitlines()):
        raise ValueError(f"{key} contains a reserved level-two heading")
    return value


def _string_list(
    payload: dict[str, Any], key: str, *, required: bool = False, one_line: bool = True
) -> list[str]:
    raw = payload.get(key)
    if not isinstance(raw, list):
        raise ValueError(f"{key} must be an array")
    values: list[str] = []
    for index, item in enumerate(raw):
        if not isinstance(item, str):
            raise ValueError(f"{key}[{index}] must be a string")
        value = normalize_markdown(item).strip()
        if not value:
            raise ValueError(f"{key}[{index}] must not be empty")
        if one_line and "\n" in value:
            raise ValueError(f"{key}[{index}] must be one line")
        if "\x00" in value or any(token in value for token in _PLACEHOLDERS):
            raise ValueError(f"{key}[{index}] contains reserved content")
        values.append(value)
    if required and not values:
        raise ValueError(f"{key} must not be empty")
    if len(values) != len(set(values)):
        raise ValueError(f"{key} must not contain duplicates")
    return values


def _repository_url(payload: dict[str, Any]) -> str:
    value = _text(payload, "repository_url", one_line=True).rstrip("/")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.query
        or parsed.fragment
        or len([part for part in parsed.path.split("/") if part]) != 2
    ):
        raise ValueError("repository_url must be an https repository URL")
    return value


def _load_template(template_type: str) -> str:
    path = PLUGIN_ROOT / "templates" / f"{template_type}.md"
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"bundled template is unreadable: {path}")
    value = path.read_text(encoding="utf-8")
    if validate_template(template_type, value):
        raise ValueError(f"bundled {template_type} template violates the fixed contract")
    return value


def _render_template(template_type: str, replacements: dict[str, str]) -> str:
    body = _load_template(template_type)
    for placeholder, value in replacements.items():
        if body.count(placeholder) != 1:
            raise ValueError(f"bundled template has invalid placeholder {placeholder}")
        body = body.replace(placeholder, value, 1)
    if any(token in body for token in replacements):
        raise ValueError("rendered artifact contains an unresolved template placeholder")
    return body


def render_work_issue(payload: dict[str, Any]) -> dict[str, object]:
    required = {
        "title",
        "background",
        "goal",
        "requirements",
        "design",
        "verification",
        "todo",
        "status",
    }
    _require_shape(payload, required=required)
    title = _text(payload, "title", one_line=True)
    status = _text(payload, "status", one_line=True)
    if status not in WORK_STATUSES:
        raise ValueError("status must be backlog, in-progress, or complete")
    todo = _string_list(payload, "todo")
    for index, item in enumerate(todo):
        if _TASK_RE.fullmatch(item) is None:
            raise ValueError(f"todo[{index}] must be a Markdown task-list item")
    body = _render_template(
        "work",
        {
            "<background>": _text(payload, "background", required=False),
            "<goal>": _text(payload, "goal", required=False),
            "<requirements>": _text(payload, "requirements", required=False),
            "<design>": _text(payload, "design", required=False),
            "<verification>": _text(payload, "verification", required=False),
            "<todo>": "\n".join(todo),
            "<backlog-or-in-progress-or-complete>": status,
        },
    )
    parsed = parse_work_body(body)
    if not parsed.valid:
        codes = ", ".join(problem.code for problem in parsed.errors)
        raise ValueError(f"rendered body is not a valid work issue: {codes}")
    return {
        "title": title,
        "body": body,
        "labels": [BREADCRUMB_LABEL],
        "status": parsed.status,
        "todo": {"resolved": parsed.resolved, "unresolved": parsed.unresolved},
    }


def render_adr(payload: dict[str, Any]) -> dict[str, object]:
    required = {
        "issue_number",
        "slug",
        "title",
        "status",
        "supersedes",
        "superseded_by",
        "summary",
        "context",
        "affected_areas",
        "decision",
        "consequences",
        "review_triggers",
    }
    _require_shape(payload, required=required)
    issue_number = _positive_integer(payload, "issue_number")
    slug = _text(payload, "slug", one_line=True)
    if _SLUG_RE.fullmatch(slug) is None:
        raise ValueError("slug must be lowercase ASCII kebab-case")
    status = _text(payload, "status", one_line=True)
    if status not in ADR_STATUSES:
        raise ValueError("status must be accepted, superseded, or deprecated")
    supersedes = sorted(_string_list(payload, "supersedes"))
    superseded_by = sorted(_string_list(payload, "superseded_by"))
    affected = payload.get("affected_areas")
    if not isinstance(affected, dict):
        raise ValueError("affected_areas must be an object")
    _require_shape(
        affected,
        required={"components", "paths", "resources", "behaviors"},
    )

    def affected_value(key: str) -> str:
        values = _string_list(affected, key)
        return ", ".join(values) if values else "none"

    path = f".breadcrumb/adr/{issue_number}-{slug}.md"
    first = ", ".join(supersedes) or "none"
    second = ", ".join(superseded_by) or "none"
    body = _load_template("adr")
    relationship_placeholder = "<none-or-sorted-adr-basenames>"
    if body.count(relationship_placeholder) != 2:
        raise ValueError("bundled ADR template has invalid relationship placeholders")
    body = body.replace(relationship_placeholder, first, 1)
    body = body.replace(relationship_placeholder, second, 1)
    replacements = {
        "<title>": _text(payload, "title", one_line=True),
        "<accepted-or-superseded-or-deprecated>": status,
        "<number>": str(issue_number),
        "<summary>": _text(payload, "summary"),
        "<context>": _text(payload, "context"),
        "<components-or-none>": affected_value("components"),
        "<paths-or-none>": affected_value("paths"),
        "<resources-or-none>": affected_value("resources"),
        "<behaviors-or-none>": affected_value("behaviors"),
        "<decision>": _text(payload, "decision"),
        "<consequences>": _text(payload, "consequences"),
        "<review-triggers>": _text(payload, "review_triggers"),
    }
    for placeholder, value in replacements.items():
        if body.count(placeholder) != 1:
            raise ValueError(f"bundled ADR template has invalid placeholder {placeholder}")
        body = body.replace(placeholder, value, 1)
    if any(token in body for token in replacements):
        raise ValueError("rendered ADR contains an unresolved template placeholder")
    parsed = parse_adr_bytes(path, body.encode("utf-8"))
    if not parsed.valid:
        codes = ", ".join(problem.code for problem in parsed.errors)
        raise ValueError(f"rendered body is not a valid ADR: {codes}")
    return {"path": path, "body": body, "status": status, "work_issue": issue_number}


def _branch_and_commit(payload: dict[str, Any]) -> tuple[int, str, str, str]:
    issue_number = _positive_integer(payload, "issue_number")
    repository_url = _repository_url(payload)
    branch = _text(payload, "branch", one_line=True)
    if parse_branch(branch) != issue_number:
        raise ValueError("branch must be a Breadcrumb branch for issue_number")
    commit = _text(payload, "commit", one_line=True)
    if _OBJECT_ID_RE.fullmatch(commit) is None:
        raise ValueError("commit must be a full lowercase Git object ID")
    return issue_number, repository_url, branch, commit


def render_implementation_comment(payload: dict[str, Any]) -> dict[str, object]:
    required = {
        "issue_number",
        "repository_url",
        "branch",
        "commit",
        "verification",
        "summary",
        "verification_report",
    }
    _require_shape(payload, required=required)
    issue_number, repository_url, branch, commit = _branch_and_commit(payload)
    verification = _text(payload, "verification", one_line=True)
    if verification not in {"passed", "failed", "pending"}:
        raise ValueError("verification must be passed, failed, or pending")
    body = _render_template(
        "comment-implementation",
        {
            "<branch>": branch,
            "<branch-url>": f"{repository_url}/tree/{branch}",
            "<commit>": commit,
            "<commit-url>": f"{repository_url}/commit/{commit}",
            "<passed-or-failed-or-pending>": verification,
            "<summary>": _narrative(payload, "summary"),
            "<verification-report>": _narrative(payload, "verification_report"),
        },
    )
    parsed = parse_breadcrumb_comment(
        body, expected_issue=issue_number, repository_url=repository_url
    )
    if parsed.outcome != "valid":
        raise ValueError(f"rendered implementation comment is invalid: {parsed.message}")
    return {"body": body, "verification": verification}


def render_stale_comment(payload: dict[str, Any]) -> dict[str, object]:
    required = {
        "issue_number",
        "repository_url",
        "previous_comment_url",
        "branch",
        "commit",
        "reason",
    }
    _require_shape(payload, required=required)
    issue_number, repository_url, branch, commit = _branch_and_commit(payload)
    previous = _text(payload, "previous_comment_url", one_line=True)
    match = _COMMENT_URL_RE.fullmatch(previous)
    if match is None or int(match.group(1)) != issue_number:
        raise ValueError("previous_comment_url must identify the same work issue")
    expected_prefix = f"{repository_url}/issues/{issue_number}#issuecomment-"
    if not previous.casefold().startswith(expected_prefix.casefold()):
        raise ValueError("previous_comment_url must identify the same repository")
    body = _render_template(
        "comment-implementation-stale",
        {
            "<comment-url>": previous,
            "<branch>": branch,
            "<branch-url>": f"{repository_url}/tree/{branch}",
            "<commit>": commit,
            "<commit-url>": f"{repository_url}/commit/{commit}",
            "<reason>": _text(payload, "reason", one_line=True),
        },
    )
    parsed = parse_breadcrumb_comment(
        body, expected_issue=issue_number, repository_url=repository_url
    )
    if parsed.outcome != "valid":
        raise ValueError(f"rendered stale comment is invalid: {parsed.message}")
    return {"body": body}


def render_update_comment(payload: dict[str, Any]) -> dict[str, object]:
    required = {
        "issue_number",
        "repository_url",
        "applied_through_url",
        "comment_prefix_sha256",
        "body_sha256",
        "summary",
    }
    _require_shape(payload, required=required)
    issue_number = _positive_integer(payload, "issue_number")
    repository_url = _repository_url(payload)
    applied = payload.get("applied_through_url")
    if applied is None:
        applied_value = "none"
    elif isinstance(applied, str):
        applied_value = _text(payload, "applied_through_url", one_line=True)
        match = _COMMENT_URL_RE.fullmatch(applied_value)
        if match is None or int(match.group(1)) != issue_number:
            raise ValueError("applied_through_url must identify the same work issue")
        expected_prefix = f"{repository_url}/issues/{issue_number}#issuecomment-"
        if not applied_value.casefold().startswith(expected_prefix.casefold()):
            raise ValueError("applied_through_url must identify the same repository")
        applied_value = f"[comment]({applied_value})"
    else:
        raise ValueError("applied_through_url must be a string or null")
    prefix = _text(payload, "comment_prefix_sha256", one_line=True)
    body_sha = _text(payload, "body_sha256", one_line=True)
    if _SHA256_RE.fullmatch(prefix) is None:
        raise ValueError("comment_prefix_sha256 must be a lowercase SHA-256")
    if _SHA256_RE.fullmatch(body_sha) is None:
        raise ValueError("body_sha256 must be a lowercase SHA-256")
    body = _render_template(
        "comment-update",
        {
            "[comment](<comment-url>)|none": applied_value,
            "<comment-prefix-sha256>": prefix,
            "<body-sha256>": body_sha,
            "<summary>": _narrative(payload, "summary"),
        },
    )
    parsed = parse_update_comment(
        body, expected_issue=issue_number, repository_url=repository_url
    )
    if parsed.outcome != "valid":
        raise ValueError(f"rendered update comment is invalid: {parsed.message}")
    return {"body": body}


def render_pull_request(payload: dict[str, Any]) -> dict[str, object]:
    required = {"issue_number", "title", "summary", "changes"}
    _require_shape(payload, required=required)
    issue_number = _positive_integer(payload, "issue_number")
    title = _text(payload, "title", one_line=True)
    changes = _string_list(payload, "changes", required=True)
    summary = _narrative(payload, "summary")
    if _CLOSING_REFERENCE_RE.search(summary) or any(
        _CLOSING_REFERENCE_RE.search(change) for change in changes
    ):
        raise ValueError("summary and changes must not add another closing reference")
    body = _render_template(
        "pull-request",
        {
            "<summary>": summary,
            "<changes>": "\n".join(f"- {item}" for item in changes),
            "<issue-number>": str(issue_number),
        },
    )
    visible_headings = [line for line in body.splitlines() if line.startswith("## ")]
    if visible_headings != ["## Summary", "## Changes"]:
        raise ValueError("rendered pull request contains invalid headings")
    if not body.rstrip().endswith(f"Closes #{issue_number}"):
        raise ValueError("rendered pull request lacks the closing relationship")
    return {"title": title, "body": body, "issue_number": issue_number}
