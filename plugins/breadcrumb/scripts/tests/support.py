from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"


def fixture(name: str) -> Any:
    with (FIXTURE_ROOT / name).open(encoding="utf-8") as source:
        return json.load(source)


def copied_fixture(name: str) -> Any:
    return copy.deepcopy(fixture(name))


def work_body(
    status: str,
    todo: list[str] | None = None,
    *,
    schema_version: str = "1",
) -> str:
    todo_lines = todo or []
    return "\n".join(
        [
            "## Background",
            "",
            "Background text.",
            "",
            "## Goal",
            "",
            "Goal text.",
            "",
            "## Requirements",
            "",
            "- Required behavior.",
            "",
            "## Design",
            "",
            "Use the existing component.",
            "",
            "## Verification",
            "",
            "Run unit tests.",
            "",
            "## Todo",
            "",
            *todo_lines,
            "",
            "## Breadcrumb Status",
            "",
            f"- Schema Version: {schema_version}",
            f"- Status: {status}",
        ]
    )


class FakeClient:
    def __init__(
        self,
        issues: list[dict[str, object]],
        *,
        comments: dict[int, list[dict[str, object]]] | None = None,
        pulls: dict[int, list[dict[str, object]]] | None = None,
    ) -> None:
        from internal.github import parse_target

        self.target = parse_target("ghe.example.test", "acme/widgets")
        self._issues = {int(issue["number"]): copy.deepcopy(issue) for issue in issues}
        self._comments = copy.deepcopy(comments or {})
        self._pulls = copy.deepcopy(pulls or {})
        self.comment_calls: list[int] = []
        self.pull_calls: list[int] = []

    def issue(self, number: int) -> dict[str, object]:
        return copy.deepcopy(self._issues[number])

    def issues_with_label(self, label: str, *, state: str) -> list[dict[str, object]]:
        result = []
        for issue in self._issues.values():
            names = {
                item["name"] if isinstance(item, dict) else item
                for item in issue.get("labels", [])
            }
            if label not in names:
                continue
            if state != "all" and issue.get("state") != state:
                continue
            result.append(copy.deepcopy(issue))
        return result

    def issue_comments(self, number: int) -> list[dict[str, object]]:
        self.comment_calls.append(number)
        return copy.deepcopy(self._comments.get(number, []))

    def closing_pull_requests(self, number: int) -> list[dict[str, object]]:
        self.pull_calls.append(number)
        return copy.deepcopy(self._pulls.get(number, []))
