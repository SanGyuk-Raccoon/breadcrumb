from __future__ import annotations

import copy
import unittest

from support import FakeClient, copied_fixture

from internal.projection import inspect_issue, list_issues


class ProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.issues = copied_fixture("work_issues.json")
        self.comments = copied_fixture("comments.json")
        self.pulls = copied_fixture("pull_requests.json")

    def test_absent_artifacts_are_null(self) -> None:
        result = inspect_issue(FakeClient([self.issues[2]]), 3)["issue"]
        self.assertTrue(result["valid"])
        self.assertIsNone(result["implementation"])
        self.assertIsNone(result["pull_request"])

    def test_latest_valid_comment_controls_current_or_stale(self) -> None:
        stale = inspect_issue(
            FakeClient([self.issues[2]], comments={3: self.comments[:2]}), 3
        )["issue"]
        current = inspect_issue(
            FakeClient([self.issues[2]], comments={3: self.comments}), 3
        )["issue"]
        self.assertEqual(stale["implementation"]["state"], "stale")
        self.assertEqual(current["implementation"], {
            "state": "current",
            "branch": "breadcrumb/3-implement-retry-policy",
        })

    def test_in_progress_safely_infers_old_implementation_as_stale(self) -> None:
        active = copy.deepcopy(self.issues[1])
        comment = copy.deepcopy(self.comments[0])
        comment["body"] = comment["body"].replace("breadcrumb/3-", "breadcrumb/2-")
        result = inspect_issue(FakeClient([active], comments={2: [comment]}), 2)["issue"]
        self.assertEqual(result["implementation"]["state"], "stale")

    def test_untrusted_only_comment_is_an_isolated_error(self) -> None:
        forged = copy.deepcopy(self.comments[0])
        forged["author_association"] = "NONE"
        result = inspect_issue(
            FakeClient([self.issues[2]], comments={3: [forged]}), 3
        )["issue"]
        self.assertFalse(result["valid"])
        self.assertIsNone(result["implementation"])
        self.assertIn(
            "invalid_implementation_comment", {item["code"] for item in result["errors"]}
        )

    def test_open_pull_wins_over_merged_pull(self) -> None:
        result = inspect_issue(
            FakeClient([self.issues[2]], pulls={3: self.pulls}), 3
        )["issue"]
        self.assertEqual(result["pull_request"], {
            "number": 20,
            "state": "open",
            "draft": False,
        })

    def test_latest_merged_pull_is_selected_when_none_is_open(self) -> None:
        older = copy.deepcopy(self.pulls[1])
        newer = copy.deepcopy(self.pulls[1])
        newer["number"] = 21
        newer["mergedAt"] = "2026-02-01T00:00:00Z"
        result = inspect_issue(
            FakeClient([self.issues[2]], pulls={3: [older, newer]}), 3
        )["issue"]
        self.assertEqual(result["pull_request"]["number"], 21)
        self.assertEqual(result["pull_request"]["state"], "merged")

    def test_multiple_open_pulls_are_a_conflict(self) -> None:
        second = copy.deepcopy(self.pulls[0])
        second["number"] = 21
        result = inspect_issue(
            FakeClient([self.issues[2]], pulls={3: [self.pulls[0], second]}), 3
        )["issue"]
        self.assertFalse(result["valid"])
        self.assertIsNone(result["pull_request"])
        self.assertIn(
            "conflicting_open_pull_requests", {item["code"] for item in result["errors"]}
        )

    def test_stale_implementation_requires_open_pr_to_be_draft(self) -> None:
        normal = inspect_issue(
            FakeClient(
                [self.issues[2]],
                comments={3: self.comments[:2]},
                pulls={3: [self.pulls[0]]},
            ),
            3,
        )["issue"]
        draft_pull = copy.deepcopy(self.pulls[0])
        draft_pull["isDraft"] = True
        draft = inspect_issue(
            FakeClient(
                [self.issues[2]],
                comments={3: self.comments[:2]},
                pulls={3: [draft_pull]},
            ),
            3,
        )["issue"]
        self.assertFalse(normal["valid"])
        self.assertIn(
            "stale_implementation_pr_not_draft",
            {item["code"] for item in normal["errors"]},
        )
        self.assertTrue(draft["valid"])

    def test_list_isolates_invalid_items_and_status_filter_keeps_them_visible(self) -> None:
        result = list_issues(FakeClient(self.issues), status_filter="complete")
        numbers = [item["number"] for item in result["issues"]]
        self.assertEqual(numbers, [3, 4])
        self.assertTrue(result["issues"][0]["valid"])
        self.assertFalse(result["issues"][1]["valid"])

    def test_closed_issues_are_opt_in(self) -> None:
        closed = copy.deepcopy(self.issues[2])
        closed["state"] = "closed"
        client = FakeClient([closed])
        self.assertEqual(list_issues(client)["issues"], [])
        self.assertEqual(len(list_issues(client, include_closed=True)["issues"]), 1)

    def test_inspect_requires_breadcrumb_label(self) -> None:
        issue = copy.deepcopy(self.issues[2])
        issue["labels"] = []
        result = inspect_issue(FakeClient([issue]), 3)["issue"]
        self.assertFalse(result["valid"])
        self.assertIn(
            "missing_breadcrumb_label", {item["code"] for item in result["errors"]}
        )


if __name__ == "__main__":
    unittest.main()
