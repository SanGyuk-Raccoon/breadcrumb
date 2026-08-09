"""Read-only Git and GitHub discovery backed by argument-array subprocess calls."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlparse

from .errors import BreadcrumbOperationalError, sanitized


_HOST_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?$")
_REPOSITORY_PART_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_SCP_REMOTE_RE = re.compile(r"^(?:[^@/:]+@)?([^/:]+):(.+)$")
_PER_PAGE = 100

Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class RepositoryTarget:
    hostname: str
    owner: str
    name: str

    @property
    def identity(self) -> str:
        return f"{self.owner}/{self.name}"

    @property
    def api_root(self) -> str:
        return f"repos/{self.owner}/{self.name}"

    @property
    def web_url(self) -> str:
        return f"https://{self.hostname}/{self.identity}"


@dataclass(frozen=True)
class RepositoryContext:
    root: Path
    remote: str
    target: RepositoryTarget
    default_branch: str


def parse_target(hostname: str, repository: str) -> RepositoryTarget:
    host = hostname.strip()
    if not _HOST_RE.fullmatch(host):
        raise BreadcrumbOperationalError(
            "invalid_hostname", "hostname must be a plain host name such as github.com"
        )
    parts = repository.strip().split("/")
    if (
        len(parts) != 2
        or not all(parts)
        or not all(_REPOSITORY_PART_RE.fullmatch(part) for part in parts)
    ):
        raise BreadcrumbOperationalError(
            "invalid_repository", "repository must use the owner/name form"
        )
    return RepositoryTarget(host, parts[0], parts[1])


def parse_remote_url(remote_url: str) -> RepositoryTarget:
    value = remote_url.strip()
    host: str | None = None
    path: str | None = None
    if "://" in value:
        parsed = urlparse(value)
        host = parsed.hostname
        path = parsed.path.lstrip("/")
    else:
        match = _SCP_REMOTE_RE.fullmatch(value)
        if match:
            host, path = match.groups()
    if not host or not path:
        raise BreadcrumbOperationalError(
            "unsupported_remote", "Git remote must identify a GitHub owner/repository"
        )
    if path.endswith(".git"):
        path = path[:-4]
    return parse_target(host, path)


def _run_git(
    command: list[str], runner: Runner, *, code: str = "git_error"
) -> str:
    try:
        result = runner(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except FileNotFoundError as exc:
        raise BreadcrumbOperationalError("git_not_found", "git was not found") from exc
    except OSError as exc:
        raise BreadcrumbOperationalError(code, sanitized(exc)) from exc
    if result.returncode != 0:
        detail = sanitized(result.stderr.strip()) or f"git exited with {result.returncode}"
        raise BreadcrumbOperationalError(code, detail)
    return result.stdout.strip()


def discover_repository(runner: Runner | None = None) -> tuple[Path, str, RepositoryTarget]:
    """Resolve repository identity from Git instead of persistent Breadcrumb config."""

    execute = runner or subprocess.run
    root_value = _run_git(["git", "rev-parse", "--show-toplevel"], execute)
    if not root_value:
        raise BreadcrumbOperationalError("not_a_repository", "Git root is empty")
    root = Path(root_value).resolve()
    remote_output = _run_git(["git", "-C", str(root), "remote"], execute)
    remotes = [line.strip() for line in remote_output.splitlines() if line.strip()]
    if "origin" in remotes:
        remote = "origin"
    elif len(remotes) == 1:
        remote = remotes[0]
    elif not remotes:
        raise BreadcrumbOperationalError("missing_remote", "repository has no Git remote")
    else:
        raise BreadcrumbOperationalError(
            "ambiguous_remote", "repository has multiple remotes and no origin"
        )
    remote_url = _run_git(
        ["git", "-C", str(root), "remote", "get-url", remote], execute
    )
    return root, remote, parse_remote_url(remote_url)


class GitHubClient:
    """Small read-only JSON client that always supplies an explicit host."""

    def __init__(self, target: RepositoryTarget, runner: Runner | None = None) -> None:
        self.target = target
        self._runner = runner or subprocess.run

    def _run_json(self, command: list[str]) -> Any:
        try:
            result = self._runner(
                command,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        except FileNotFoundError as exc:
            raise BreadcrumbOperationalError(
                "gh_not_found", "GitHub CLI executable gh was not found"
            ) from exc
        except OSError as exc:
            raise BreadcrumbOperationalError(
                "github_api_error", f"could not execute gh api: {sanitized(exc)}"
            ) from exc
        if result.returncode != 0:
            detail = sanitized(result.stderr.strip())
            if not detail:
                detail = f"gh api exited with status {result.returncode}"
            raise BreadcrumbOperationalError("github_api_error", detail)
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise BreadcrumbOperationalError(
                "invalid_github_response", "gh api returned invalid JSON"
            ) from exc

    def _rest(
        self, endpoint: str, parameters: Sequence[tuple[str, object]] = ()
    ) -> Any:
        command = [
            "gh",
            "api",
            "--hostname",
            self.target.hostname,
            "--method",
            "GET",
            endpoint,
        ]
        for key, value in parameters:
            command.extend(("-f", f"{key}={value}"))
        return self._run_json(command)

    def get_object(
        self, endpoint: str, parameters: Sequence[tuple[str, object]] = ()
    ) -> Mapping[str, Any]:
        value = self._rest(endpoint, parameters)
        if not isinstance(value, dict):
            raise BreadcrumbOperationalError(
                "invalid_github_response",
                f"GitHub endpoint {endpoint} did not return an object",
            )
        return value

    def get_paginated(
        self, endpoint: str, parameters: Sequence[tuple[str, object]] = ()
    ) -> list[Mapping[str, Any]]:
        items: list[Mapping[str, Any]] = []
        page = 1
        while True:
            value = self._rest(
                endpoint,
                tuple(parameters) + (("per_page", _PER_PAGE), ("page", page)),
            )
            if not isinstance(value, list) or not all(
                isinstance(item, dict) for item in value
            ):
                raise BreadcrumbOperationalError(
                    "invalid_github_response",
                    f"GitHub endpoint {endpoint} returned a malformed collection",
                )
            items.extend(value)
            if len(value) < _PER_PAGE:
                return items
            page += 1

    def repository(self) -> Mapping[str, Any]:
        return self.get_object(self.target.api_root)

    def issue(self, number: int) -> Mapping[str, Any]:
        return self.get_object(f"{self.target.api_root}/issues/{number}")

    def issues_with_label(
        self, label: str, *, state: str
    ) -> list[Mapping[str, Any]]:
        return self.get_paginated(
            f"{self.target.api_root}/issues",
            (("state", state), ("labels", label)),
        )

    def issue_comments(self, number: int) -> list[Mapping[str, Any]]:
        return self.get_paginated(f"{self.target.api_root}/issues/{number}/comments")

    def _graphql(self, query: str, variables: Sequence[tuple[str, object]]) -> Any:
        command = [
            "gh",
            "api",
            "--hostname",
            self.target.hostname,
            "graphql",
            "--method",
            "POST",
            "-f",
            f"query={query}",
        ]
        for key, value in variables:
            flag = "-F" if isinstance(value, int) and not isinstance(value, bool) else "-f"
            command.extend((flag, f"{key}={value}"))
        return self._run_json(command)

    def closing_pull_requests(self, issue_number: int) -> list[Mapping[str, Any]]:
        query = """
query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    issue(number: $number) {
      closedByPullRequestsReferences(
        first: 100
        after: $cursor
        includeClosedPrs: true
      ) {
        nodes {
          number
          url
          state
          isDraft
          headRefName
          baseRefName
          createdAt
          closedAt
          mergedAt
        }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}
"""
        items: list[Mapping[str, Any]] = []
        cursor: str | None = None
        while True:
            variables: list[tuple[str, object]] = [
                ("owner", self.target.owner),
                ("name", self.target.name),
                ("number", issue_number),
            ]
            if cursor is not None:
                variables.append(("cursor", cursor))
            value = self._graphql(query, variables)
            try:
                repository = value["data"]["repository"]
                issue = repository["issue"]
                connection = issue["closedByPullRequestsReferences"]
                nodes = connection["nodes"]
                page_info = connection["pageInfo"]
            except (KeyError, TypeError) as exc:
                raise BreadcrumbOperationalError(
                    "invalid_github_response",
                    "GitHub GraphQL response is missing closing pull request data",
                ) from exc
            if not isinstance(nodes, list) or not all(
                isinstance(node, dict) for node in nodes
            ):
                raise BreadcrumbOperationalError(
                    "invalid_github_response",
                    "GitHub returned malformed closing pull request data",
                )
            items.extend(nodes)
            if not isinstance(page_info, dict) or not page_info.get("hasNextPage"):
                return items
            cursor_value = page_info.get("endCursor")
            if not isinstance(cursor_value, str) or not cursor_value:
                raise BreadcrumbOperationalError(
                    "invalid_github_response",
                    "GitHub closing pull request pagination cursor is missing",
                )
            cursor = cursor_value


def resolve_repository(
    *, git_runner: Runner | None = None, github_runner: Runner | None = None
) -> tuple[RepositoryContext, GitHubClient]:
    root, remote, target = discover_repository(git_runner)
    client = GitHubClient(target, github_runner)
    metadata = client.repository()
    full_name = metadata.get("full_name")
    if not isinstance(full_name, str) or full_name.casefold() != target.identity.casefold():
        raise BreadcrumbOperationalError(
            "repository_mismatch", "Git remote and GitHub repository metadata disagree"
        )
    if metadata.get("has_issues") is not True:
        raise BreadcrumbOperationalError(
            "issues_disabled", "GitHub Issues are not enabled for this repository"
        )
    default_branch = metadata.get("default_branch")
    if not isinstance(default_branch, str) or not default_branch:
        raise BreadcrumbOperationalError(
            "invalid_github_response", "GitHub repository default branch is missing"
        )
    return RepositoryContext(root, remote, target, default_branch), client
