"""Read-only GitHub transport backed by ``gh api``."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from .errors import BreadcrumbOperationalError, sanitized


_HOST_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?$")
_REPOSITORY_PART_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_PER_PAGE = 100


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


def parse_target(hostname: str, repository: str) -> RepositoryTarget:
    host = hostname.strip()
    if not _HOST_RE.fullmatch(host):
        raise BreadcrumbOperationalError(
            "invalid_hostname",
            "hostname must be a plain host name such as github.com",
        )

    parts = repository.strip().split("/")
    if (
        len(parts) != 2
        or not all(parts)
        or not all(_REPOSITORY_PART_RE.fullmatch(part) for part in parts)
    ):
        raise BreadcrumbOperationalError(
            "invalid_repository",
            "repository must use the owner/name form",
        )
    return RepositoryTarget(host, parts[0], parts[1])


Runner = Callable[..., subprocess.CompletedProcess[str]]


class GitHubClient:
    """Small JSON client that always supplies an explicit host and repository."""

    def __init__(self, target: RepositoryTarget, runner: Runner | None = None) -> None:
        self.target = target
        self._runner = runner or subprocess.run

    def _request(
        self,
        endpoint: str,
        parameters: Sequence[tuple[str, object]] = (),
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
                "gh_not_found", "GitHub CLI executable 'gh' was not found"
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

    def get_object(
        self,
        endpoint: str,
        parameters: Sequence[tuple[str, object]] = (),
    ) -> Mapping[str, Any]:
        value = self._request(endpoint, parameters)
        if not isinstance(value, dict):
            raise BreadcrumbOperationalError(
                "invalid_github_response",
                f"GitHub endpoint {endpoint} did not return an object",
            )
        return value

    def get_paginated(
        self,
        endpoint: str,
        parameters: Sequence[tuple[str, object]] = (),
    ) -> list[Mapping[str, Any]]:
        """Fetch every page of a REST collection using explicit page numbers."""

        items: list[Mapping[str, Any]] = []
        page = 1
        while True:
            page_parameters = tuple(parameters) + (
                ("per_page", _PER_PAGE),
                ("page", page),
            )
            value = self._request(endpoint, page_parameters)
            if not isinstance(value, list):
                raise BreadcrumbOperationalError(
                    "invalid_github_response",
                    f"GitHub endpoint {endpoint} did not return a collection",
                )
            if not all(isinstance(item, dict) for item in value):
                raise BreadcrumbOperationalError(
                    "invalid_github_response",
                    f"GitHub endpoint {endpoint} returned a malformed collection",
                )
            items.extend(value)
            if len(value) < _PER_PAGE:
                return items
            page += 1

    def issues_with_label(self, label: str) -> list[Mapping[str, Any]]:
        return self.get_paginated(
            f"{self.target.api_root}/issues",
            (("state", "all"), ("labels", label)),
        )

    def issue(self, number: int) -> Mapping[str, Any]:
        return self.get_object(f"{self.target.api_root}/issues/{number}")

    def issue_comments(self, number: int) -> list[Mapping[str, Any]]:
        return self.get_paginated(f"{self.target.api_root}/issues/{number}/comments")

    def pulls_for_branch(self, branch: str) -> list[Mapping[str, Any]]:
        return self.get_paginated(
            f"{self.target.api_root}/pulls",
            (("state", "all"), ("head", f"{self.target.owner}:{branch}")),
        )
