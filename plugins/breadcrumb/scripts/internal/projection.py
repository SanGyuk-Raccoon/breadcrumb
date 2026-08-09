"""Compose Breadcrumb issue, implementation, and pull request projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from . import (
    BREADCRUMB_LABEL,
    PROJECTION_VERSION,
    TRUSTED_ASSOCIATIONS,
)
from .comments import CommentArtifact, parse_breadcrumb_comment
from .documents import WorkDocument, parse_work_body
from .errors import BreadcrumbOperationalError
from .github import GitHubClient


@dataclass(frozen=True)
class ProjectionError:
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


def _positive_number(value: object, description: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise BreadcrumbOperationalError(
            "invalid_github_response", f"GitHub returned {description} without a valid number"
        )
    return value


def _label_names(issue: Mapping[str, Any]) -> set[str]:
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


def _comment_key(comment: Mapping[str, Any]) -> tuple[str, int]:
    created = comment.get("created_at")
    identifier = comment.get("id")
    return (
        created if isinstance(created, str) else "",
        identifier if isinstance(identifier, int) and not isinstance(identifier, bool) else 0,
    )


def _latest_implementation(
    client: GitHubClient,
    issue_number: int,
) -> tuple[CommentArtifact | None, ProjectionError | None]:
    valid: list[tuple[tuple[str, int], CommentArtifact]] = []
    invalid_candidate = False
    untrusted_candidate = False
    for comment in client.issue_comments(issue_number):
        result = parse_breadcrumb_comment(
            comment.get("body"),
            expected_issue=issue_number,
            repository_url=client.target.web_url,
        )
        if result.outcome == "not-breadcrumb":
            continue
        if result.outcome == "invalid" or result.artifact is None:
            invalid_candidate = True
            continue
        if comment.get("author_association") not in TRUSTED_ASSOCIATIONS:
            untrusted_candidate = True
            continue
        valid.append((_comment_key(comment), result.artifact))
    if valid:
        return max(valid, key=lambda item: item[0])[1], None
    if invalid_candidate or untrusted_candidate:
        detail = ""
        if untrusted_candidate:
            detail = " or lacks trusted author provenance"
        return None, ProjectionError(
            "invalid_implementation_comment",
            "Breadcrumb implementation comments are malformed" + detail,
        )
    return None, None


def _normalize_pull(
    raw: Mapping[str, Any],
) -> tuple[dict[str, object] | None, ProjectionError | None, str]:
    try:
        number = _positive_number(raw.get("number"), "a pull request")
    except BreadcrumbOperationalError:
        return None, ProjectionError(
            "invalid_pull_request", "linked pull request number is malformed"
        ), ""
    state_value = raw.get("state")
    if not isinstance(state_value, str) or state_value.upper() not in {
        "OPEN",
        "CLOSED",
        "MERGED",
    }:
        return None, ProjectionError(
            "invalid_pull_request", f"linked pull request #{number} has an invalid state"
        ), ""
    draft = raw.get("isDraft")
    if not isinstance(draft, bool):
        return None, ProjectionError(
            "invalid_pull_request", f"linked pull request #{number} has invalid draft metadata"
        ), ""
    state = state_value.lower()
    timestamp = raw.get("mergedAt") or raw.get("closedAt") or raw.get("createdAt")
    key = timestamp if isinstance(timestamp, str) else ""
    return {"number": number, "state": state, "draft": draft}, None, key


def _linked_pull_request(
    client: GitHubClient, issue_number: int
) -> tuple[dict[str, object] | None, ProjectionError | None]:
    normalized: list[tuple[dict[str, object], str]] = []
    for raw in client.closing_pull_requests(issue_number):
        pull, error, timestamp = _normalize_pull(raw)
        if error is not None:
            return None, error
        assert pull is not None
        normalized.append((pull, timestamp))
    open_pulls = [item for item in normalized if item[0]["state"] == "open"]
    if len(open_pulls) > 1:
        numbers = ", ".join(
            f"#{item[0]['number']}" for item in sorted(open_pulls, key=lambda item: int(item[0]["number"]))
        )
        return None, ProjectionError(
            "conflicting_open_pull_requests",
            f"multiple open pull requests close issue #{issue_number}: {numbers}",
        )
    if open_pulls:
        return open_pulls[0][0], None
    if not normalized:
        return None, None

    merged = [item for item in normalized if item[0]["state"] == "merged"]
    candidates = merged or normalized
    selected = max(candidates, key=lambda item: (item[1], int(item[0]["number"])))
    return selected[0], None


def _base_projection(raw: Mapping[str, Any]) -> tuple[dict[str, object], WorkDocument]:
    number = _positive_number(raw.get("number"), "an issue")
    title = raw.get("title")
    url = raw.get("html_url")
    state_value = raw.get("state")
    if not isinstance(title, str) or not isinstance(url, str):
        raise BreadcrumbOperationalError(
            "invalid_github_response", f"issue #{number} is missing title or URL metadata"
        )
    if not isinstance(state_value, str) or state_value.lower() not in {"open", "closed"}:
        raise BreadcrumbOperationalError(
            "invalid_github_response", f"issue #{number} has an invalid GitHub state"
        )
    document = parse_work_body(raw.get("body"))
    projection = {
        "number": number,
        "title": title,
        "url": url,
        "github_state": state_value.lower(),
        "schema_version": document.schema_version,
        "status": document.status,
        "todo": {
            "resolved": document.resolved,
            "unresolved": document.unresolved,
        },
        "implementation": None,
        "pull_request": None,
        "valid": document.valid,
        "errors": [problem.as_dict() for problem in document.errors],
    }
    return projection, document


def project_issue(
    client: GitHubClient, raw: Mapping[str, Any]
) -> dict[str, object]:
    projection, document = _base_projection(raw)
    errors = list(projection["errors"])
    if "pull_request" in raw:
        errors.append(
            ProjectionError("not_an_issue", "requested number identifies a pull request").as_dict()
        )
        projection["valid"] = False
        projection["errors"] = errors
        return projection
    if BREADCRUMB_LABEL not in _label_names(raw):
        errors.append(
            ProjectionError(
                "missing_breadcrumb_label", "issue does not have the breadcrumb label"
            ).as_dict()
        )

    issue_number = int(projection["number"])
    artifact, artifact_error = _latest_implementation(client, issue_number)
    if artifact_error is not None:
        errors.append(artifact_error.as_dict())
    if artifact is not None:
        state = "stale" if artifact.kind == "stale" else "current"
        if document.status == "in-progress":
            state = "stale"
        projection["implementation"] = {"state": state, "branch": artifact.branch}

    pull, pull_error = _linked_pull_request(client, issue_number)
    if pull_error is not None:
        errors.append(pull_error.as_dict())
    projection["pull_request"] = pull

    implementation = projection["implementation"]
    if (
        isinstance(implementation, dict)
        and implementation.get("state") == "stale"
        and isinstance(pull, dict)
        and pull.get("state") == "open"
        and pull.get("draft") is False
    ):
        errors.append(
            ProjectionError(
                "stale_implementation_pr_not_draft",
                "an open pull request for a stale implementation must be draft",
            ).as_dict()
        )

    projection["valid"] = not errors
    projection["errors"] = errors
    return projection


def inspect_issue(client: GitHubClient, issue_number: int) -> dict[str, object]:
    return {
        "projection_version": PROJECTION_VERSION,
        "hostname": client.target.hostname,
        "repository": client.target.identity,
        "issue": project_issue(client, client.issue(issue_number)),
    }


def list_issues(
    client: GitHubClient,
    *,
    status_filter: str | None = None,
    include_closed: bool = False,
) -> dict[str, object]:
    state = "all" if include_closed else "open"
    results: list[dict[str, object]] = []
    for raw in client.issues_with_label(BREADCRUMB_LABEL, state=state):
        if "pull_request" in raw:
            continue
        projection = project_issue(client, raw)
        if status_filter is None or not projection["valid"] or projection["status"] == status_filter:
            results.append(projection)
    results.sort(key=lambda item: int(item["number"]))
    return {
        "projection_version": PROJECTION_VERSION,
        "hostname": client.target.hostname,
        "repository": client.target.identity,
        "issues": results,
    }
