"""Compose Breadcrumb issue, implementation, and pull request projections."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence

from . import (
    BREADCRUMB_LABEL,
    PROJECTION_VERSION,
    TRUSTED_ASSOCIATIONS,
)
from .comments import (
    CommentArtifact,
    UpdateArtifact,
    UpdateResult,
    parse_breadcrumb_comment,
    parse_update_comment,
)
from .documents import WorkDocument, parse_work_body
from .errors import BreadcrumbOperationalError
from .github import GitHubClient


@dataclass(frozen=True)
class ProjectionError:
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


CommentMode = Literal["incremental", "all"]


@dataclass(frozen=True)
class _Comment:
    identifier: int
    url: str
    created_at: str
    updated_at: str
    author: str | None
    author_association: str
    body: str

    @property
    def key(self) -> tuple[str, int]:
        return self.created_at, self.identifier

    def as_item(self) -> dict[str, object]:
        return {
            "id": self.identifier,
            "url": self.url,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "author": self.author,
            "author_association": self.author_association,
            "body": self.body,
        }


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


def _normalize_comment(
    raw: Mapping[str, Any],
    *,
    issue_number: int,
    repository_url: str,
) -> _Comment:
    identifier = _positive_number(raw.get("id"), "an issue comment")
    url = raw.get("html_url")
    created_at = raw.get("created_at")
    updated_at = raw.get("updated_at")
    association = raw.get("author_association")
    body = raw.get("body")
    if not all(
        isinstance(value, str) and value
        for value in (url, created_at, updated_at, association)
    ):
        raise BreadcrumbOperationalError(
            "invalid_github_response", "an issue comment contains malformed metadata"
        )
    if not isinstance(body, str):
        raise BreadcrumbOperationalError(
            "invalid_github_response", "an issue comment body is malformed"
        )
    expected_url = (
        f"{repository_url.rstrip('/')}/issues/{issue_number}#issuecomment-{identifier}"
    )
    if url != expected_url:
        raise BreadcrumbOperationalError(
            "invalid_github_response", "an issue comment URL does not match its identity"
        )
    user = raw.get("user")
    author = user.get("login") if isinstance(user, dict) else None
    if author is not None and not isinstance(author, str):
        raise BreadcrumbOperationalError(
            "invalid_github_response", "an issue comment author is malformed"
        )
    return _Comment(identifier, url, created_at, updated_at, author, association, body)


def _comment_snapshot(
    raw_comments: Sequence[Mapping[str, Any]],
    *,
    issue_number: int,
    repository_url: str,
) -> list[_Comment]:
    return sorted(
        (
            _normalize_comment(
                comment,
                issue_number=issue_number,
                repository_url=repository_url,
            )
            for comment in raw_comments
        ),
        key=lambda comment: comment.key,
    )


def _latest_implementation(
    comments: Sequence[_Comment],
    issue_number: int,
    repository_url: str,
) -> tuple[CommentArtifact | None, ProjectionError | None]:
    valid: list[tuple[tuple[str, int], CommentArtifact]] = []
    invalid_candidate = False
    untrusted_candidate = False
    for comment in comments:
        result = parse_breadcrumb_comment(
            comment.body,
            expected_issue=issue_number,
            repository_url=repository_url,
        )
        if result.outcome == "not-breadcrumb":
            continue
        if result.outcome == "invalid" or result.artifact is None:
            invalid_candidate = True
            continue
        if comment.author_association not in TRUSTED_ASSOCIATIONS:
            untrusted_candidate = True
            continue
        valid.append((comment.key, result.artifact))
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


def _body_sha256(body: object) -> str:
    value = body if isinstance(body, str) else ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _update_item(comment: _Comment, artifact: UpdateArtifact) -> dict[str, object]:
    return {
        "comment_id": comment.identifier,
        "comment_url": comment.url,
        "created_at": comment.created_at,
        "updated_at": comment.updated_at,
        "applied_through_id": artifact.applied_through_id,
        "applied_through_url": artifact.applied_through_url,
        "body_sha256": artifact.body_sha256,
    }


def _warning(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _comment_projection(
    raw_issue: Mapping[str, Any],
    comments: Sequence[_Comment],
    *,
    issue_number: int,
    repository_url: str,
    mode: CommentMode,
) -> dict[str, object]:
    body_sha256 = _body_sha256(raw_issue.get("body"))
    ordinary: list[_Comment] = []
    valid_updates: list[tuple[_Comment, UpdateArtifact]] = []
    trusted_update_candidates: list[tuple[_Comment, UpdateResult]] = []
    warnings: list[dict[str, str]] = []

    for comment in comments:
        implementation = parse_breadcrumb_comment(
            comment.body,
            expected_issue=issue_number,
            repository_url=repository_url,
        )
        update = parse_update_comment(
            comment.body,
            expected_issue=issue_number,
            repository_url=repository_url,
        )
        if update.outcome != "not-breadcrumb":
            if comment.author_association in TRUSTED_ASSOCIATIONS:
                trusted_update_candidates.append((comment, update))
                if update.outcome == "valid" and update.artifact is not None:
                    valid_updates.append((comment, update.artifact))
            else:
                candidate = _warning(
                    "untrusted_update_comment",
                    f"Breadcrumb Update comment {comment.url} lacks trusted author provenance",
                )
                if candidate not in warnings:
                    warnings.append(candidate)
        if (
            implementation.outcome == "not-breadcrumb"
            and update.outcome == "not-breadcrumb"
        ):
            ordinary.append(comment)

    checkpoint: dict[str, object] | None = None
    boundary: tuple[str, int] | None = None
    fallback = False
    if trusted_update_candidates:
        marker, result = max(trusted_update_candidates, key=lambda item: item[0].key)
        artifact = result.artifact
        if result.outcome != "valid" or not isinstance(artifact, UpdateArtifact):
            fallback = True
            warnings.append(
                _warning(
                    "invalid_update_checkpoint",
                    f"latest trusted Breadcrumb Update comment {marker.url} is malformed",
                )
            )
        elif artifact.body_sha256 != body_sha256:
            fallback = True
            warnings.append(
                _warning(
                    "stale_update_checkpoint",
                    f"latest trusted Breadcrumb Update comment {marker.url} does not match the current issue body",
                )
            )
        else:
            source: _Comment | None = None
            if artifact.applied_through_id is not None:
                source = next(
                    (
                        comment
                        for comment in ordinary
                        if comment.identifier == artifact.applied_through_id
                        and comment.url == artifact.applied_through_url
                    ),
                    None,
                )
                if source is None or source.key >= marker.key:
                    fallback = True
                    warnings.append(
                        _warning(
                            "invalid_update_checkpoint",
                            f"Breadcrumb Update comment {marker.url} has an unavailable or out-of-order Applied Through comment",
                        )
                    )
                else:
                    boundary = source.key
                    edited = next(
                        (
                            comment
                            for comment in ordinary
                            if comment.key <= boundary
                            and comment.updated_at >= marker.created_at
                        ),
                        None,
                    )
                    if edited is not None:
                        fallback = True
                        boundary = None
                        warnings.append(
                            _warning(
                                "edited_comment_before_checkpoint",
                                f"ordinary comment {edited.url} was edited at or after the selected Breadcrumb Update checkpoint",
                            )
                        )
            if not fallback:
                checkpoint = {
                    "comment_id": marker.identifier,
                    "comment_url": marker.url,
                    "applied_through_id": artifact.applied_through_id,
                    "applied_through_url": artifact.applied_through_url,
                }

    effective_mode: CommentMode = "all" if mode == "all" or fallback else "incremental"
    selected = ordinary
    if effective_mode == "incremental" and boundary is not None:
        selected = [comment for comment in ordinary if comment.key > boundary]

    return {
        "requested_mode": mode,
        "effective_mode": effective_mode,
        "body_sha256": body_sha256,
        "checkpoint": checkpoint,
        "items": [comment.as_item() for comment in selected],
        "updates": [
            _update_item(comment, artifact)
            for comment, artifact in sorted(valid_updates, key=lambda item: item[0].key)
        ],
        "warnings": warnings,
    }


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
    client: GitHubClient,
    raw: Mapping[str, Any],
    *,
    comments: Sequence[_Comment] | None = None,
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
    snapshot = (
        list(comments)
        if comments is not None
        else _comment_snapshot(
            client.issue_comments(issue_number),
            issue_number=issue_number,
            repository_url=client.target.web_url,
        )
    )
    artifact, artifact_error = _latest_implementation(
        snapshot, issue_number, client.target.web_url
    )
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


def inspect_issue(
    client: GitHubClient,
    issue_number: int,
    *,
    comment_mode: CommentMode | None = None,
) -> dict[str, object]:
    raw = client.issue(issue_number)
    snapshot: list[_Comment] | None = None
    if "pull_request" not in raw:
        snapshot = _comment_snapshot(
            client.issue_comments(issue_number),
            issue_number=issue_number,
            repository_url=client.target.web_url,
        )
    result: dict[str, object] = {
        "projection_version": PROJECTION_VERSION,
        "hostname": client.target.hostname,
        "repository": client.target.identity,
        "issue": project_issue(client, raw, comments=snapshot),
    }
    if comment_mode is not None and snapshot is not None:
        result["comments"] = _comment_projection(
            raw,
            snapshot,
            issue_number=issue_number,
            repository_url=client.target.web_url,
            mode=comment_mode,
        )
    return result


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
