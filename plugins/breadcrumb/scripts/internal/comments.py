"""Parse Breadcrumb control comments from visible Markdown."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .documents import normalize_markdown


IMPLEMENTATION_HEADING = "## Breadcrumb Implementation"
STALE_HEADING = "## Breadcrumb Implementation Stale"
UPDATE_HEADING = "## Breadcrumb Update"

BRANCH_RE = re.compile(r"^breadcrumb/([1-9][0-9]*)-[a-z0-9][a-z0-9-]*$")
_OBJECT_ID_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_BRANCH_LINE_RE = re.compile(
    r"^- Branch: \[`([^`]+)`\]\((https://[^\s()]+)\)$"
)
_COMMIT_LINE_RE = re.compile(
    r"^- Verified Commit: \[`([^`]+)`\]\((https://[^\s()]+)\)$"
)
_PREVIOUS_LINE_RE = re.compile(
    r"^- Previous Implementation: \[comment\]\((https://[^\s()]+)\)$"
)
_VERIFICATION_LINE_RE = re.compile(
    r"^- Verification: (passed|failed|pending)$"
)
_REASON_LINE_RE = re.compile(r"^- Reason: (\S(?:.*\S)?)$")
_APPLIED_THROUGH_LINE_RE = re.compile(
    r"^- Applied Through: \[comment\]\((https://[^\s()]+/issues/([1-9][0-9]*)"
    r"#issuecomment-([1-9][0-9]*))\)$"
)
_BODY_SHA256_LINE_RE = re.compile(r"^- Body SHA-256: `([0-9a-f]{64})`$")


def parse_branch(value: str) -> int | None:
    match = BRANCH_RE.fullmatch(value)
    return int(match.group(1)) if match else None


@dataclass(frozen=True)
class CommentArtifact:
    kind: Literal["implementation", "stale"]
    branch: str
    branch_url: str
    commit: str
    commit_url: str
    verification: str | None = None
    previous_comment_url: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class CommentResult:
    outcome: Literal["not-breadcrumb", "valid", "invalid"]
    artifact: CommentArtifact | None = None
    message: str | None = None


@dataclass(frozen=True)
class UpdateArtifact:
    applied_through_id: int | None
    applied_through_url: str | None
    body_sha256: str


@dataclass(frozen=True)
class UpdateResult:
    outcome: Literal["not-breadcrumb", "valid", "invalid"]
    artifact: UpdateArtifact | None = None
    message: str | None = None


def _invalid(message: str) -> CommentResult:
    return CommentResult("invalid", message=message)


def _invalid_update(message: str) -> UpdateResult:
    return UpdateResult("invalid", message=message)


def _metadata_lines(body: str) -> list[str]:
    return [line for line in normalize_markdown(body).split("\n") if line.strip()]


def _validate_common(
    branch_match: re.Match[str] | None,
    commit_match: re.Match[str] | None,
    expected_issue: int,
    repository_url: str | None,
) -> tuple[str, str, str, str] | CommentResult:
    if branch_match is None:
        return _invalid("Branch metadata is malformed")
    if commit_match is None:
        return _invalid("Verified Commit metadata is malformed")

    branch, branch_url = branch_match.groups()
    commit, commit_url = commit_match.groups()
    if parse_branch(branch) != expected_issue:
        return _invalid("implementation branch does not match the work issue")
    if not _OBJECT_ID_RE.fullmatch(commit):
        return _invalid("Verified Commit must be a full lowercase Git object ID")
    if repository_url is not None:
        base = repository_url.rstrip("/")
        if branch_url != f"{base}/tree/{branch}":
            return _invalid("Branch link does not match its branch")
        if commit_url != f"{base}/commit/{commit}":
            return _invalid("Verified Commit link does not match its commit")
    return branch, branch_url, commit, commit_url


def parse_breadcrumb_comment(
    body: object,
    *,
    expected_issue: int,
    repository_url: str | None = None,
) -> CommentResult:
    """Parse only the fixed heading and metadata bullets; ignore human prose."""

    if not isinstance(body, str):
        return CommentResult("not-breadcrumb")
    lines = _metadata_lines(body)
    if not lines or lines[0] not in {IMPLEMENTATION_HEADING, STALE_HEADING}:
        return CommentResult("not-breadcrumb")

    if lines[0] == IMPLEMENTATION_HEADING:
        if len(lines) < 5:
            return _invalid("implementation comment metadata is incomplete")
        if lines[1] != "- Schema Version: 1":
            return _invalid("implementation comment Schema Version must be 1")
        common = _validate_common(
            _BRANCH_LINE_RE.fullmatch(lines[2]),
            _COMMIT_LINE_RE.fullmatch(lines[3]),
            expected_issue,
            repository_url,
        )
        if isinstance(common, CommentResult):
            return common
        verification_match = _VERIFICATION_LINE_RE.fullmatch(lines[4])
        if verification_match is None:
            return _invalid("Verification metadata is malformed")
        branch, branch_url, commit, commit_url = common
        return CommentResult(
            "valid",
            artifact=CommentArtifact(
                "implementation",
                branch,
                branch_url,
                commit,
                commit_url,
                verification=verification_match.group(1),
            ),
        )

    if len(lines) < 6:
        return _invalid("stale comment metadata is incomplete")
    if lines[1] != "- Schema Version: 1":
        return _invalid("stale comment Schema Version must be 1")
    previous_match = _PREVIOUS_LINE_RE.fullmatch(lines[2])
    if previous_match is None:
        return _invalid("Previous Implementation metadata is malformed")
    common = _validate_common(
        _BRANCH_LINE_RE.fullmatch(lines[3]),
        _COMMIT_LINE_RE.fullmatch(lines[4]),
        expected_issue,
        repository_url,
    )
    if isinstance(common, CommentResult):
        return common
    reason_match = _REASON_LINE_RE.fullmatch(lines[5])
    if reason_match is None:
        return _invalid("stale Reason metadata is malformed")
    branch, branch_url, commit, commit_url = common
    return CommentResult(
        "valid",
        artifact=CommentArtifact(
            "stale",
            branch,
            branch_url,
            commit,
            commit_url,
            previous_comment_url=previous_match.group(1),
            reason=reason_match.group(1),
        ),
    )


def parse_update_comment(
    body: object,
    *,
    expected_issue: int,
    repository_url: str | None = None,
) -> UpdateResult:
    """Parse only the fixed update heading and metadata bullets."""

    if not isinstance(body, str):
        return UpdateResult("not-breadcrumb")
    lines = _metadata_lines(body)
    if not lines or lines[0] != UPDATE_HEADING:
        return UpdateResult("not-breadcrumb")
    if len(lines) < 4:
        return _invalid_update("update comment metadata is incomplete")
    if lines[1] != "- Schema Version: 1":
        return _invalid_update("update comment Schema Version must be 1")

    applied_through_id: int | None = None
    applied_through_url: str | None = None
    if lines[2] != "- Applied Through: none":
        applied_match = _APPLIED_THROUGH_LINE_RE.fullmatch(lines[2])
        if applied_match is None:
            return _invalid_update("Applied Through metadata is malformed")
        applied_through_url, issue_value, comment_value = applied_match.groups()
        if int(issue_value) != expected_issue:
            return _invalid_update("Applied Through does not match the work issue")
        applied_through_id = int(comment_value)
        if repository_url is not None:
            expected_url = (
                f"{repository_url.rstrip('/')}/issues/{expected_issue}"
                f"#issuecomment-{applied_through_id}"
            )
            if applied_through_url != expected_url:
                return _invalid_update("Applied Through does not match the repository")

    body_match = _BODY_SHA256_LINE_RE.fullmatch(lines[3])
    if body_match is None:
        return _invalid_update("Body SHA-256 metadata is malformed")
    return UpdateResult(
        "valid",
        artifact=UpdateArtifact(
            applied_through_id=applied_through_id,
            applied_through_url=applied_through_url,
            body_sha256=body_match.group(1),
        ),
    )
