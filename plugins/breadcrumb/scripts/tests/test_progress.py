from __future__ import annotations

import copy
import unittest

from support import copied_fixture

from internal.github import parse_target
from internal.listing import DESIGN_LABEL
from internal.progress import get_issue_progress


class FakeProgressClient:
    def __init__(
        self,
        issues: list[dict[str, object]],
        *,
        design_candidates: list[dict[str, object]] | None = None,
        comments: dict[int, list[dict[str, object]]] | None = None,
        pulls: dict[str, list[dict[str, object]]] | None = None,
    ) -> None:
        self.target = parse_target("ghe.example.test", "acme/widgets")
        self.issues = {int(issue["number"]): issue for issue in issues}
        self.design_candidates = design_candidates or []
        self.comments = comments or {}
        self.pulls = pulls or {}
        self.comment_calls: list[int] = []
        self.pull_calls: list[str] = []
        self.label_calls: list[str] = []

    def issue(self, number: int) -> dict[str, object]:
        return copy.deepcopy(self.issues[number])

    def issues_with_label(self, label: str) -> list[dict[str, object]]:
        self.label_calls.append(label)
        return copy.deepcopy(self.design_candidates)

    def issue_comments(self, number: int) -> list[dict[str, object]]:
        self.comment_calls.append(number)
        return copy.deepcopy(self.comments.get(number, []))

    def pulls_for_branch(self, branch: str) -> list[dict[str, object]]:
        self.pull_calls.append(branch)
        return copy.deepcopy(self.pulls.get(branch, []))


class ProgressProjectionTests(unittest.TestCase):
    def test_batch_projection_reuses_design_artifacts(self) -> None:
        requirement = copied_fixture("requirement_issue.json")
        design = copied_fixture("design_issue.json")
        comments = copied_fixture("implementation_comments.json")
        pulls = copied_fixture("pulls.json")
        client = FakeProgressClient(
            [requirement, design],
            design_candidates=[design],
            comments={21: comments},
            pulls={"breadcrumb/21-login-rate-limit": pulls},
        )

        result = get_issue_progress(client, [12, 21])

        self.assertEqual(result["hostname"], "ghe.example.test")
        self.assertEqual(result["repository"], "acme/widgets")
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["backlogs"], [])
        self.assertEqual(len(result["requirements"]), 1)
        self.assertEqual(len(result["designs"]), 1)
        requirement_projection = result["requirements"][0]
        design_projection = result["designs"][0]
        self.assertEqual(requirement_projection["type"], "requirement")
        self.assertEqual(design_projection["type"], "design")
        self.assertEqual(
            requirement_projection["related_design"], {"present": True, "number": 21}
        )
        self.assertEqual(
            design_projection["related_requirement"], {"present": True, "number": 12}
        )
        self.assertEqual(
            design_projection["implementation"],
            {"comment_present": True, "branch": "breadcrumb/21-login-rate-limit"},
        )
        self.assertEqual(
            design_projection["pull_request"],
            {"present": True, "number": 30, "state": "open"},
        )
        self.assertEqual(client.comment_calls, [21])
        self.assertEqual(client.pull_calls, ["breadcrumb/21-login-rate-limit"])

    def test_backlog_projection_is_minimal_and_fetches_no_artifacts(self) -> None:
        backlog = copied_fixture("backlog_issue.json")
        client = FakeProgressClient([backlog])
        result = get_issue_progress(client, [8])
        self.assertEqual(result["backlogs"], [{
            "number": 8,
            "title": "Consider saved search filters",
            "type": "backlog",
            "state": "open",
        }])
        self.assertEqual(result["requirements"], [])
        self.assertEqual(result["designs"], [])
        self.assertEqual(result["errors"], [])
        self.assertEqual(client.label_calls, [])
        self.assertEqual(client.comment_calls, [])
        self.assertEqual(client.pull_calls, [])

    def test_malformed_backlog_is_isolated_from_valid_requirement(self) -> None:
        backlog = copied_fixture("backlog_issue.json")
        backlog["body"] = backlog["body"].replace(
            "- Last Breadcrumb Step: backlog", "- Last Breadcrumb Step: open"
        )
        requirement = copied_fixture("requirement_issue.json")
        client = FakeProgressClient([backlog, requirement], design_candidates=[])
        result = get_issue_progress(client, [8, 12])
        self.assertEqual(result["backlogs"], [])
        self.assertEqual(len(result["requirements"]), 1)
        self.assertEqual(result["errors"], [{
            "number": 8,
            "code": "invalid_last_step",
            "message": "Last Breadcrumb Step is invalid for backlog",
        }])

    def test_multiple_open_related_designs_are_an_issue_error(self) -> None:
        requirement = copied_fixture("requirement_issue.json")
        first = copied_fixture("design_issue.json")
        second = copied_fixture("design_issue.json")
        second["number"] = 22
        second["title"] = "Competing design"
        second["created_at"] = "2026-01-03T00:00:00Z"
        client = FakeProgressClient(
            [requirement], design_candidates=[first, second]
        )
        result = get_issue_progress(client, [12])
        self.assertEqual(result["requirements"], [])
        self.assertEqual(result["errors"][0]["code"], "conflicting_related_designs")
        self.assertEqual(client.comment_calls, [])

    def test_open_design_wins_over_newer_closed_design(self) -> None:
        requirement = copied_fixture("requirement_issue.json")
        open_design = copied_fixture("design_issue.json")
        closed_design = copied_fixture("design_issue.json")
        closed_design["number"] = 22
        closed_design["state"] = "closed"
        closed_design["created_at"] = "2026-02-01T00:00:00Z"
        client = FakeProgressClient(
            [requirement], design_candidates=[open_design, closed_design]
        )
        result = get_issue_progress(client, [12])
        self.assertEqual(result["requirements"][0]["related_design"]["number"], 21)

    def test_most_recent_closed_design_is_selected_when_none_is_open(self) -> None:
        requirement = copied_fixture("requirement_issue.json")
        older = copied_fixture("design_issue.json")
        older["state"] = "closed"
        newer = copied_fixture("design_issue.json")
        newer["number"] = 22
        newer["title"] = "New design"
        newer["state"] = "closed"
        newer["created_at"] = "2026-02-01T00:00:00Z"
        client = FakeProgressClient(
            [requirement], design_candidates=[older, newer]
        )
        result = get_issue_progress(client, [12])
        self.assertEqual(result["requirements"][0]["related_design"]["number"], 22)

    def test_untrusted_forged_implementation_footprint_is_rejected(self) -> None:
        design = copied_fixture("design_issue.json")
        body = copied_fixture("implementation_comments.json")[-1]["body"]
        forged = {
            "id": 99,
            "created_at": "2026-03-01T00:00:00Z",
            "author_association": "NONE",
            "body": body,
        }
        client = FakeProgressClient([design], comments={21: [forged]})
        result = get_issue_progress(client, [21])
        self.assertEqual(result["designs"], [])
        self.assertEqual(result["errors"][0]["code"], "invalid_footprint")
        self.assertIn("trusted author provenance", result["errors"][0]["message"])
        self.assertEqual(client.pull_calls, [])

    def test_malformed_issue_is_isolated_from_valid_batch_item(self) -> None:
        malformed = copied_fixture("requirement_issue.json")
        malformed["body"] = malformed["body"].replace("- Phase: ready", "- Phase: done")
        design = copied_fixture("design_issue.json")
        client = FakeProgressClient([malformed, design], comments={21: []})
        result = get_issue_progress(client, [12, 21])
        self.assertEqual(result["requirements"], [])
        self.assertEqual(len(result["designs"]), 1)
        self.assertEqual(result["errors"], [{
            "number": 12,
            "code": "invalid_phase",
            "message": "Breadcrumb Phase must be draft or ready",
        }])


if __name__ == "__main__":
    unittest.main()
