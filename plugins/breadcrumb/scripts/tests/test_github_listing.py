from __future__ import annotations

import json
import subprocess
import unittest

from support import copied_fixture

from internal.errors import BreadcrumbOperationalError
from internal.github import GitHubClient, parse_target
from internal.listing import DESIGN_LABEL, REQUIREMENT_LABEL, list_issue_numbers


class PagingRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def __call__(self, command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        self.calls.append((command, kwargs))
        fields = [command[index + 1] for index, value in enumerate(command) if value == "-f"]
        page = int(next(field.split("=", 1)[1] for field in fields if field.startswith("page=")))
        if page == 1:
            payload = [{"number": number} for number in range(1, 101)]
        else:
            payload = [{"number": 101}]
        return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")


class PaginationTests(unittest.TestCase):
    def test_collection_is_fully_paginated_with_argument_arrays(self) -> None:
        runner = PagingRunner()
        client = GitHubClient(parse_target("ghe.example.test", "acme/widgets"), runner)
        items = client.get_paginated("repos/acme/widgets/issues")
        self.assertEqual(len(items), 101)
        self.assertEqual(len(runner.calls), 2)
        first_command, first_kwargs = runner.calls[0]
        self.assertEqual(first_command[:7], [
            "gh", "api", "--hostname", "ghe.example.test", "--method", "GET", "repos/acme/widgets/issues"
        ])
        self.assertNotIn("shell", first_kwargs)

    def test_non_json_response_is_operational_failure(self) -> None:
        def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(command, 0, "not json", "")

        client = GitHubClient(parse_target("github.com", "acme/widgets"), runner)
        with self.assertRaises(BreadcrumbOperationalError) as raised:
            client.get_object("repos/acme/widgets")
        self.assertEqual(raised.exception.code, "invalid_github_response")


class FakeListingClient:
    def __init__(self, by_label: dict[str, list[dict[str, object]]]) -> None:
        self.target = parse_target("ghe.example.test", "acme/widgets")
        self.by_label = by_label
        self.calls: list[str] = []

    def issues_with_label(self, label: str) -> list[dict[str, object]]:
        self.calls.append(label)
        return self.by_label.get(label, [])


class ListingTests(unittest.TestCase):
    def test_filters_prs_and_reports_conflicting_labels(self) -> None:
        requirement = copied_fixture("requirement_issue.json")
        design = copied_fixture("design_issue.json")
        conflict = copied_fixture("requirement_issue.json")
        conflict["number"] = 40
        conflict["labels"].append({"name": DESIGN_LABEL})
        pull = copied_fixture("requirement_issue.json")
        pull["number"] = 50
        pull["pull_request"] = {"url": "example"}
        client = FakeListingClient(
            {
                REQUIREMENT_LABEL: [requirement, conflict, pull],
                DESIGN_LABEL: [design, conflict],
            }
        )
        result = list_issue_numbers(client, "all")
        self.assertEqual(result["hostname"], "ghe.example.test")
        self.assertEqual(result["repository"], "acme/widgets")
        self.assertEqual(result["requirements"], [12])
        self.assertEqual(result["designs"], [21])
        self.assertEqual(
            result["invalid"],
            [{
                "number": 40,
                "code": "conflicting_type_labels",
                "message": "issue has both breadcrumb:requirement and breadcrumb:design labels",
            }],
        )

    def test_type_filter_queries_only_requested_label(self) -> None:
        requirement = copied_fixture("requirement_issue.json")
        client = FakeListingClient({REQUIREMENT_LABEL: [requirement]})
        result = list_issue_numbers(client, "requirement")
        self.assertEqual(client.calls, [REQUIREMENT_LABEL])
        self.assertEqual(result["requirements"], [12])
        self.assertEqual(result["designs"], [])


if __name__ == "__main__":
    unittest.main()
