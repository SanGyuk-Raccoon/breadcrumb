"""Compact Breadcrumb progress projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from . import SCHEMA_VERSION
from .documents import DocumentProblem, IssueStatus, parse_issue_status
from .errors import BreadcrumbOperationalError
from .footprints import Footprint, parse_footprint
from .github import GitHubClient
from .listing import DESIGN_LABEL, REQUIREMENT_LABEL, label_names


@dataclass(frozen=True)
class ProjectionProblem(Exception):
    code: str
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class LoadedIssue:
    number: int
    title: str
    state: str
    created_at: str
    issue_type: str
    status: IssueStatus
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class ImplementationArtifact:
    comment_present: bool
    branch: str | None
    pull_number: int | None
    pull_state: str | None


def _positive_number(value: object, description: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise BreadcrumbOperationalError(
            "invalid_github_response", f"GitHub returned {description} without a valid number"
        )
    return value


def _issue_type(raw: Mapping[str, Any]) -> str:
    names = label_names(raw)
    has_requirement = REQUIREMENT_LABEL in names
    has_design = DESIGN_LABEL in names
    if has_requirement and has_design:
        raise ProjectionProblem(
            "conflicting_type_labels",
            "issue has both breadcrumb:requirement and breadcrumb:design labels",
        )
    if not has_requirement and not has_design:
        raise ProjectionProblem(
            "missing_type_label", "issue has no Breadcrumb type label"
        )
    return "requirement" if has_requirement else "design"


def _load_issue(raw: Mapping[str, Any], expected_number: int | None = None) -> LoadedIssue:
    number = _positive_number(raw.get("number"), "an issue")
    if expected_number is not None and number != expected_number:
        raise BreadcrumbOperationalError(
            "invalid_github_response",
            f"GitHub returned issue #{number} when issue #{expected_number} was requested",
        )
    if "pull_request" in raw:
        raise ProjectionProblem("not_an_issue", "requested number identifies a pull request")
    title = raw.get("title")
    if not isinstance(title, str):
        raise BreadcrumbOperationalError(
            "invalid_github_response", f"issue #{number} is missing a title"
        )
    state_value = raw.get("state")
    if not isinstance(state_value, str) or state_value.lower() not in {"open", "closed"}:
        raise BreadcrumbOperationalError(
            "invalid_github_response", f"issue #{number} has an invalid GitHub state"
        )
    created_at_value = raw.get("created_at")
    created_at = created_at_value if isinstance(created_at_value, str) else ""
    issue_type = _issue_type(raw)
    try:
        status = parse_issue_status(raw.get("body"), issue_type)
    except DocumentProblem as exc:
        raise ProjectionProblem(exc.code, exc.message) from exc
    return LoadedIssue(
        number=number,
        title=title,
        state=state_value.lower(),
        created_at=created_at,
        issue_type=issue_type,
        status=status,
        raw=raw,
    )


def _comment_key(comment: Mapping[str, Any]) -> tuple[str, int]:
    created = comment.get("created_at")
    identifier = comment.get("id")
    return (
        created if isinstance(created, str) else "",
        identifier if isinstance(identifier, int) and not isinstance(identifier, bool) else 0,
    )


def _latest_implementation_footprint(
    comments: list[Mapping[str, Any]], design_number: int
) -> Footprint | None:
    valid: list[tuple[tuple[str, int], Footprint]] = []
    invalid_candidates = False
    untrusted_candidates = False
    for comment in comments:
        body = comment.get("body")
        result = parse_footprint(
            body if isinstance(body, str) else "",
            expected_step="implement",
            expected_issue=design_number,
        )
        if result.outcome == "valid" and result.footprint is not None:
            if comment.get("author_association") in {"OWNER", "MEMBER", "COLLABORATOR"}:
                valid.append((_comment_key(comment), result.footprint))
            else:
                untrusted_candidates = True
        elif result.outcome == "invalid":
            invalid_candidates = True
    if valid:
        return max(valid, key=lambda item: item[0])[1]
    if invalid_candidates or untrusted_candidates:
        provenance = (
            " and no syntactically valid candidate has trusted author provenance"
            if untrusted_candidates
            else ""
        )
        raise ProjectionProblem(
            "invalid_footprint",
            "implementation comments contain Breadcrumb footprints but none is valid"
            + provenance,
        )
    return None


def _final_closes(body: str, issue_number: int) -> bool:
    final = next(
        (line for line in reversed(body.replace("\r\n", "\n").replace("\r", "\n").split("\n")) if line.strip()),
        "",
    )
    return final == f"Closes #{issue_number}"


def _related_pull(
    pulls: list[Mapping[str, Any]], design_number: int, branch: str
) -> tuple[int, str] | None:
    candidates: list[tuple[bool, str, int, str]] = []
    for pull in pulls:
        head = pull.get("head")
        if not isinstance(head, dict) or head.get("ref") != branch:
            continue
        body_value = pull.get("body")
        body = body_value if isinstance(body_value, str) else ""
        parsed = parse_footprint(
            body,
            expected_step="pr",
            expected_issue=design_number,
            expected_branch=branch,
            require_pr_closes=True,
        )
        if parsed.outcome != "valid" and not (
            parsed.outcome == "not-breadcrumb" and _final_closes(body, design_number)
        ):
            continue

        number = _positive_number(pull.get("number"), "a pull request")
        state_value = pull.get("state")
        if not isinstance(state_value, str) or state_value.lower() not in {"open", "closed"}:
            raise BreadcrumbOperationalError(
                "invalid_github_response", f"pull request #{number} has an invalid state"
            )
        created_value = pull.get("created_at")
        created_at = created_value if isinstance(created_value, str) else ""
        state = state_value.lower()
        candidates.append((state == "open", created_at, number, state))
    if not candidates:
        return None
    selected = max(candidates, key=lambda item: (item[0], item[1], item[2]))
    return selected[2], selected[3]


def _implementation_artifact(
    client: GitHubClient, design_number: int
) -> ImplementationArtifact:
    footprint = _latest_implementation_footprint(
        client.issue_comments(design_number), design_number
    )
    if footprint is None:
        return ImplementationArtifact(False, None, None, None)
    branch = footprint.branch
    if branch is None:  # The strict parser guarantees this for implement footprints.
        raise ProjectionProblem("invalid_footprint", "implementation branch is missing")
    pull = _related_pull(client.pulls_for_branch(branch), design_number, branch)
    if pull is None:
        return ImplementationArtifact(True, branch, None, None)
    return ImplementationArtifact(True, branch, pull[0], pull[1])


def _select_related_designs(
    requirements: list[LoadedIssue], design_candidates: list[LoadedIssue]
) -> tuple[dict[int, LoadedIssue], dict[int, ProjectionProblem]]:
    by_requirement: dict[int, list[LoadedIssue]] = {}
    for design in design_candidates:
        related = design.status.related_requirement
        if related is not None:
            by_requirement.setdefault(related, []).append(design)

    selected: dict[int, LoadedIssue] = {}
    errors: dict[int, ProjectionProblem] = {}
    for requirement in requirements:
        candidates = by_requirement.get(requirement.number, [])
        open_candidates = [candidate for candidate in candidates if candidate.state == "open"]
        if len(open_candidates) > 1:
            numbers = ", ".join(f"#{item.number}" for item in sorted(open_candidates, key=lambda item: item.number))
            errors[requirement.number] = ProjectionProblem(
                "conflicting_related_designs",
                f"multiple open design issues reference requirement #{requirement.number}: {numbers}",
            )
        elif len(open_candidates) == 1:
            selected[requirement.number] = open_candidates[0]
        elif candidates:
            selected[requirement.number] = max(
                candidates, key=lambda item: (item.created_at, item.number)
            )
    return selected, errors


def _missing_artifact() -> ImplementationArtifact:
    return ImplementationArtifact(False, None, None, None)


def _projection(
    issue: LoadedIssue,
    related_number: int | None,
    artifact: ImplementationArtifact,
) -> dict[str, object]:
    relation_name = "related_design" if issue.issue_type == "requirement" else "related_requirement"
    return {
        "number": issue.number,
        "title": issue.title,
        "state": issue.state,
        "type": issue.issue_type,
        "phase": issue.status.phase,
        relation_name: {
            "present": related_number is not None,
            "number": related_number,
        },
        "implementation": {
            "comment_present": artifact.comment_present,
            "branch": artifact.branch,
        },
        "pull_request": {
            "present": artifact.pull_number is not None,
            "number": artifact.pull_number,
            "state": artifact.pull_state,
        },
    }


def get_issue_progress(
    client: GitHubClient, issue_numbers: list[int]
) -> dict[str, object]:
    requested: dict[int, LoadedIssue] = {}
    error_by_number: dict[int, ProjectionProblem] = {}
    raw_by_number: dict[int, Mapping[str, Any]] = {}

    for number in issue_numbers:
        raw = client.issue(number)
        raw_by_number[number] = raw
        try:
            requested[number] = _load_issue(raw, number)
        except ProjectionProblem as exc:
            error_by_number[number] = exc

    requirements = [
        requested[number]
        for number in issue_numbers
        if number in requested and requested[number].issue_type == "requirement"
    ]

    design_candidates: list[LoadedIssue] = []
    if requirements:
        seen_candidates: set[int] = set()
        for raw_candidate in client.issues_with_label(DESIGN_LABEL):
            if "pull_request" in raw_candidate:
                continue
            candidate_number = _positive_number(raw_candidate.get("number"), "an issue")
            if candidate_number in seen_candidates:
                continue
            seen_candidates.add(candidate_number)
            candidate_raw = raw_by_number.get(candidate_number, raw_candidate)
            try:
                candidate = requested.get(candidate_number) or _load_issue(candidate_raw)
            except ProjectionProblem:
                continue
            if candidate.issue_type == "design":
                design_candidates.append(candidate)

    related_designs, relationship_errors = _select_related_designs(
        requirements, design_candidates
    )
    error_by_number.update(relationship_errors)

    artifact_cache: dict[int, ImplementationArtifact | ProjectionProblem] = {}

    def artifact_for(design_number: int) -> ImplementationArtifact:
        cached = artifact_cache.get(design_number)
        if isinstance(cached, ProjectionProblem):
            raise cached
        if isinstance(cached, ImplementationArtifact):
            return cached
        try:
            artifact = _implementation_artifact(client, design_number)
        except ProjectionProblem as exc:
            artifact_cache[design_number] = exc
            raise
        artifact_cache[design_number] = artifact
        return artifact

    requirement_results: list[dict[str, object]] = []
    design_results: list[dict[str, object]] = []
    for number in issue_numbers:
        issue = requested.get(number)
        if issue is None or number in error_by_number:
            continue
        if issue.issue_type == "requirement":
            related_design = related_designs.get(number)
            artifact = _missing_artifact()
            if related_design is not None:
                try:
                    artifact = artifact_for(related_design.number)
                except ProjectionProblem as exc:
                    error_by_number[number] = ProjectionProblem(
                        exc.code,
                        f"related design #{related_design.number}: {exc.message}",
                    )
                    continue
            requirement_results.append(
                _projection(
                    issue,
                    related_design.number if related_design is not None else None,
                    artifact,
                )
            )
        else:
            try:
                artifact = artifact_for(number)
            except ProjectionProblem as exc:
                error_by_number[number] = exc
                continue
            design_results.append(
                _projection(issue, issue.status.related_requirement, artifact)
            )

    errors = [
        {
            "number": number,
            "code": error_by_number[number].code,
            "message": error_by_number[number].message,
        }
        for number in issue_numbers
        if number in error_by_number
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "hostname": client.target.hostname,
        "repository": client.target.identity,
        "requirements": requirement_results,
        "designs": design_results,
        "errors": errors,
    }
