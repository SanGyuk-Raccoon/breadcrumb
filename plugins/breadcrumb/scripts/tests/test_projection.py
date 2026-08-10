from __future__ import annotations

import copy
import hashlib
import unittest

from support import FakeClient, copied_fixture

from internal.projection import inspect_issue, list_issues


def ordinary_comment(
    identifier: int,
    created_at: str,
    body: str,
    *,
    association: str = "MEMBER",
    updated_at: str | None = None,
) -> dict[str, object]:
    return {
        "id": identifier,
        "created_at": created_at,
        "updated_at": updated_at or created_at,
        "author_association": association,
        "user": {"login": "decision-maker"},
        "html_url": f"https://ghe.example.test/acme/widgets/issues/3#issuecomment-{identifier}",
        "body": body,
    }


def update_comment(
    identifier: int,
    created_at: str,
    body_sha256: str,
    *,
    applied_through: int | None,
    association: str = "MEMBER",
    malformed: bool = False,
) -> dict[str, object]:
    applied = (
        "none"
        if applied_through is None
        else (
            "[comment](https://ghe.example.test/acme/widgets/issues/3"
            f"#issuecomment-{applied_through})"
        )
    )
    schema = "2" if malformed else "1"
    return ordinary_comment(
        identifier,
        created_at,
        "\n".join(
            [
                "## Breadcrumb Update",
                "",
                f"- Schema Version: {schema}",
                f"- Applied Through: {applied}",
                f"- Body SHA-256: `{body_sha256}`",
                "",
                "## Summary",
                "",
                "Applied reviewed decisions.",
            ]
        ),
        association=association,
    )


class ProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.issues = copied_fixture("work_issues.json")
        self.comments = copied_fixture("comments.json")
        self.pulls = copied_fixture("pull_requests.json")

    def test_absent_artifacts_are_null(self) -> None:
        projection = inspect_issue(FakeClient([self.issues[2]]), 3)
        self.assertNotIn("comments", projection)
        issue = projection["issue"]
        self.assertTrue(issue["valid"])
        self.assertIsNone(issue["implementation"])
        self.assertIsNone(issue["pull_request"])

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
        comment["html_url"] = comment["html_url"].replace("/issues/3#", "/issues/2#")
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

    def test_incremental_and_all_comment_modes_share_one_snapshot(self) -> None:
        issue = self.issues[2]
        body_hash = hashlib.sha256(issue["body"].encode("utf-8")).hexdigest()
        comments = [
            ordinary_comment(200, "2026-01-04T00:00:00Z", "T1: A"),
            ordinary_comment(201, "2026-01-05T00:00:00Z", "T2: B"),
            update_comment(
                202,
                "2026-01-06T00:00:00Z",
                body_hash,
                applied_through=200,
            ),
        ]
        incremental_client = FakeClient([issue], comments={3: comments})
        incremental = inspect_issue(
            incremental_client, 3, comment_mode="incremental"
        )
        self.assertEqual(incremental_client.comment_calls, [3])
        self.assertEqual(incremental["comments"]["requested_mode"], "incremental")
        self.assertEqual(incremental["comments"]["effective_mode"], "incremental")
        self.assertEqual(incremental["comments"]["body_sha256"], body_hash)
        self.assertEqual(
            [item["id"] for item in incremental["comments"]["items"]], [201]
        )
        self.assertEqual(
            incremental["comments"]["items"][0]["updated_at"],
            "2026-01-05T00:00:00Z",
        )
        self.assertEqual(
            incremental["comments"]["checkpoint"]["applied_through_id"], 200
        )
        self.assertEqual(len(incremental["comments"]["updates"]), 1)

        all_client = FakeClient([issue], comments={3: comments})
        complete = inspect_issue(all_client, 3, comment_mode="all")
        self.assertEqual(
            [item["id"] for item in complete["comments"]["items"]], [200, 201]
        )
        self.assertEqual(complete["comments"]["effective_mode"], "all")

    def test_implementation_and_comment_projection_reuse_the_same_snapshot(self) -> None:
        issue = self.issues[2]
        body_hash = hashlib.sha256(issue["body"].encode("utf-8")).hexdigest()
        source = ordinary_comment(205, "2026-01-04T00:00:00Z", "T1: A")
        marker = update_comment(
            206,
            "2026-01-05T00:00:00Z",
            body_hash,
            applied_through=205,
        )
        implementation = copy.deepcopy(self.comments[0])
        implementation["created_at"] = "2026-01-03T00:00:00Z"
        client = FakeClient(
            [issue], comments={3: [implementation, source, marker]}
        )
        result = inspect_issue(client, 3, comment_mode="incremental")
        self.assertEqual(client.comment_calls, [3])
        self.assertEqual(result["issue"]["implementation"]["state"], "current")
        self.assertEqual(result["comments"]["items"], [])

    def test_comment_order_uses_id_when_timestamps_match(self) -> None:
        issue = self.issues[2]
        body_hash = hashlib.sha256(issue["body"].encode("utf-8")).hexdigest()
        comments = [
            ordinary_comment(210, "2026-01-04T00:00:00Z", "T1: A"),
            ordinary_comment(211, "2026-01-04T00:00:00Z", "T2: B"),
            update_comment(
                212,
                "2026-01-05T00:00:00Z",
                body_hash,
                applied_through=210,
            ),
        ]
        result = inspect_issue(
            FakeClient([issue], comments={3: comments}),
            3,
            comment_mode="incremental",
        )
        self.assertEqual([item["id"] for item in result["comments"]["items"]], [211])

    def test_stale_checkpoint_falls_back_to_all_without_losing_comments(self) -> None:
        issue = self.issues[2]
        comments = [
            ordinary_comment(220, "2026-01-04T00:00:00Z", "T1: A"),
            update_comment(
                221,
                "2026-01-05T00:00:00Z",
                "b" * 64,
                applied_through=220,
            ),
        ]
        result = inspect_issue(
            FakeClient([issue], comments={3: comments}),
            3,
            comment_mode="incremental",
        )
        projection = result["comments"]
        self.assertEqual(projection["effective_mode"], "all")
        self.assertIsNone(projection["checkpoint"])
        self.assertEqual([item["id"] for item in projection["items"]], [220])
        self.assertIn(
            "stale_update_checkpoint",
            {warning["code"] for warning in projection["warnings"]},
        )

    def test_latest_trusted_malformed_marker_forces_safe_fallback(self) -> None:
        issue = self.issues[2]
        body_hash = hashlib.sha256(issue["body"].encode("utf-8")).hexdigest()
        comments = [
            ordinary_comment(230, "2026-01-04T00:00:00Z", "T1: A"),
            update_comment(
                231,
                "2026-01-05T00:00:00Z",
                body_hash,
                applied_through=230,
            ),
            update_comment(
                232,
                "2026-01-06T00:00:00Z",
                body_hash,
                applied_through=230,
                malformed=True,
            ),
        ]
        result = inspect_issue(
            FakeClient([issue], comments={3: comments}),
            3,
            comment_mode="incremental",
        )["comments"]
        self.assertEqual(result["effective_mode"], "all")
        self.assertIn(
            "invalid_update_checkpoint",
            {warning["code"] for warning in result["warnings"]},
        )

    def test_untrusted_marker_does_not_advance_the_checkpoint(self) -> None:
        issue = self.issues[2]
        body_hash = hashlib.sha256(issue["body"].encode("utf-8")).hexdigest()
        comments = [
            ordinary_comment(240, "2026-01-04T00:00:00Z", "T1: A"),
            update_comment(
                241,
                "2026-01-05T00:00:00Z",
                body_hash,
                applied_through=240,
                association="NONE",
            ),
        ]
        result = inspect_issue(
            FakeClient([issue], comments={3: comments}),
            3,
            comment_mode="incremental",
        )["comments"]
        self.assertIsNone(result["checkpoint"])
        self.assertEqual([item["id"] for item in result["items"]], [240])
        self.assertIn(
            "untrusted_update_comment",
            {warning["code"] for warning in result["warnings"]},
        )

    def test_out_of_order_applied_comment_forces_safe_fallback(self) -> None:
        issue = self.issues[2]
        body_hash = hashlib.sha256(issue["body"].encode("utf-8")).hexdigest()
        comments = [
            update_comment(
                250,
                "2026-01-04T00:00:00Z",
                body_hash,
                applied_through=251,
            ),
            ordinary_comment(251, "2026-01-05T00:00:00Z", "T1: A"),
        ]
        result = inspect_issue(
            FakeClient([issue], comments={3: comments}),
            3,
            comment_mode="incremental",
        )["comments"]
        self.assertEqual(result["effective_mode"], "all")
        self.assertEqual([item["id"] for item in result["items"]], [251])
        self.assertIn(
            "invalid_update_checkpoint",
            {warning["code"] for warning in result["warnings"]},
        )

    def test_comment_edited_after_checkpoint_forces_safe_fallback(self) -> None:
        issue = self.issues[2]
        body_hash = hashlib.sha256(issue["body"].encode("utf-8")).hexdigest()
        comments = [
            ordinary_comment(
                255,
                "2026-01-04T00:00:00Z",
                "T1: changed answer",
                updated_at="2026-01-06T00:00:00Z",
            ),
            update_comment(
                256,
                "2026-01-05T00:00:00Z",
                body_hash,
                applied_through=255,
            ),
        ]
        result = inspect_issue(
            FakeClient([issue], comments={3: comments}),
            3,
            comment_mode="incremental",
        )["comments"]
        self.assertEqual(result["effective_mode"], "all")
        self.assertEqual([item["id"] for item in result["items"]], [255])
        self.assertIn(
            "edited_comment_before_checkpoint",
            {warning["code"] for warning in result["warnings"]},
        )

    def test_missing_checkpoint_returns_all_comments_without_warning(self) -> None:
        issue = self.issues[2]
        result = inspect_issue(
            FakeClient(
                [issue],
                comments={3: [ordinary_comment(260, "2026-01-04T00:00:00Z", "T1: A")]},
            ),
            3,
            comment_mode="incremental",
        )["comments"]
        self.assertEqual(result["effective_mode"], "incremental")
        self.assertIsNone(result["checkpoint"])
        self.assertEqual([item["id"] for item in result["items"]], [260])
        self.assertEqual(result["warnings"], [])


if __name__ == "__main__":
    unittest.main()
