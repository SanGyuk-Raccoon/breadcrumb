from __future__ import annotations

import json
import subprocess
import unittest

from support import SCRIPT_ROOT  # noqa: F401

from internal.errors import BreadcrumbOperationalError
from internal.github import (
    GitHubClient,
    discover_repository,
    parse_remote_url,
    parse_target,
    resolve_repository,
)


class GitRunner:
    def __init__(self, remotes: str = "origin\n", url: str = "git@ghe.example.test:acme/widgets.git") -> None:
        self.remotes = remotes
        self.url = url
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        if command[-2:] == ["rev-parse", "--show-toplevel"]:
            return subprocess.CompletedProcess(command, 0, "/workspace/widgets\n", "")
        if command[-1] == "remote":
            return subprocess.CompletedProcess(command, 0, self.remotes, "")
        if command[-3:-1] == ["remote", "get-url"]:
            return subprocess.CompletedProcess(command, 0, self.url + "\n", "")
        raise AssertionError(command)


class PagingRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        self.calls.append(command)
        fields = [command[index + 1] for index, item in enumerate(command) if item == "-f"]
        page = int(next(item.split("=", 1)[1] for item in fields if item.startswith("page=")))
        payload = [{"number": item} for item in range(1, 101)] if page == 1 else [{"number": 101}]
        return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")


class RepositoryRunner:
    def __init__(self, full_name: str = "acme/widgets") -> None:
        self.full_name = full_name
        self.calls: list[list[str]] = []

    def __call__(self, command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        self.calls.append(command)
        payload = {
            "full_name": self.full_name,
            "has_issues": True,
            "default_branch": "main",
        }
        return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")


class GraphqlRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        self.calls.append(command)
        has_cursor = any(item == "cursor=next" for item in command)
        node = {
            "number": 2 if has_cursor else 1,
            "url": "https://example.test/pull/1",
            "state": "CLOSED",
            "isDraft": False,
            "headRefName": "breadcrumb/1-example",
            "baseRefName": "main",
            "createdAt": "2026-01-01T00:00:00Z",
            "closedAt": "2026-01-02T00:00:00Z",
            "mergedAt": None,
        }
        payload = {
            "data": {
                "repository": {
                    "issue": {
                        "closedByPullRequestsReferences": {
                            "nodes": [node],
                            "pageInfo": {
                                "hasNextPage": not has_cursor,
                                "endCursor": None if has_cursor else "next",
                            },
                        }
                    }
                }
            }
        }
        return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")


class RepositoryDiscoveryTests(unittest.TestCase):
    def test_parse_https_ssh_and_scp_remotes(self) -> None:
        for value in (
            "https://ghe.example.test/acme/widgets.git",
            "ssh://git@ghe.example.test/acme/widgets.git",
            "git@ghe.example.test:acme/widgets.git",
        ):
            with self.subTest(value=value):
                target = parse_remote_url(value)
                self.assertEqual(target.hostname, "ghe.example.test")
                self.assertEqual(target.identity, "acme/widgets")

    def test_discovery_prefers_origin(self) -> None:
        runner = GitRunner(remotes="upstream\norigin\n")
        root, remote, target = discover_repository(runner)
        self.assertEqual(str(root), "/workspace/widgets")
        self.assertEqual(remote, "origin")
        self.assertEqual(target.identity, "acme/widgets")

    def test_discovery_rejects_ambiguous_remote(self) -> None:
        with self.assertRaises(BreadcrumbOperationalError) as raised:
            discover_repository(GitRunner(remotes="upstream\nfork\n"))
        self.assertEqual(raised.exception.code, "ambiguous_remote")

    def test_resolution_uses_canonical_repository_identity(self) -> None:
        git_runner = GitRunner(url="git@GHE.EXAMPLE.TEST:ACME/Widgets.git")
        github_runner = RepositoryRunner(full_name="acme/widgets")
        context, client = resolve_repository(
            git_runner=git_runner, github_runner=github_runner
        )
        self.assertEqual(context.target.hostname, "ghe.example.test")
        self.assertEqual(context.target.identity, "acme/widgets")
        self.assertEqual(client.target, context.target)


class GitHubTransportTests(unittest.TestCase):
    def test_rest_collection_is_fully_paginated(self) -> None:
        runner = PagingRunner()
        client = GitHubClient(parse_target("ghe.example.test", "acme/widgets"), runner)
        issues = client.issues_with_label("breadcrumb", state="all")
        self.assertEqual(len(issues), 101)
        self.assertEqual(len(runner.calls), 2)
        self.assertTrue(all("--hostname" in command for command in runner.calls))

    def test_closing_pull_relationship_is_fully_paginated(self) -> None:
        runner = GraphqlRunner()
        client = GitHubClient(parse_target("ghe.example.test", "acme/widgets"), runner)
        pulls = client.closing_pull_requests(1)
        self.assertEqual([item["number"] for item in pulls], [1, 2])
        self.assertEqual(len(runner.calls), 2)
        query_argument = next(
            item for item in runner.calls[0] if item.startswith("query=")
        )
        self.assertIn("includeClosedPrs: true", query_argument)


if __name__ == "__main__":
    unittest.main()
