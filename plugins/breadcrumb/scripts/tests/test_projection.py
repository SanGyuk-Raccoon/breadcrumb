from __future__ import annotations

import copy
import hashlib
import json
import unittest

from support import FakeClient, copied_fixture

from internal.errors import BreadcrumbOperationalError
from internal.projection import inspect_issue, list_issues


COMMENT_PREFIX_DOMAIN = b"Breadcrumb Comment Prefix v1\0"
EMPTY_COMMENT_PREFIX_SHA256 = hashlib.sha256(COMMENT_PREFIX_DOMAIN).hexdigest()


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


def comment_prefix_sha256(comments: list[dict[str, object]]) -> str:
    current = EMPTY_COMMENT_PREFIX_SHA256
    for comment in sorted(
        comments, key=lambda item: (str(item["created_at"]), int(item["id"]))
    ):
        user = comment.get("user")
        item = {
            "id": comment["id"],
            "url": comment["html_url"],
            "created_at": comment["created_at"],
            "updated_at": comment["updated_at"],
            "author": user.get("login") if isinstance(user, dict) else None,
            "author_association": comment["author_association"],
            "body": comment["body"],
        }
        payload = json.dumps(
            item, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
        current = hashlib.sha256(bytes.fromhex(current) + b"\0" + payload).hexdigest()
    return current


def update_comment(
    identifier: int,
    created_at: str,
    body_sha256: str,
    *,
    applied_through: int | None,
    comment_prefix_sha256: str,
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
                f"- Comment Prefix SHA-256: `{comment_prefix_sha256}`",
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
        first = ordinary_comment(200, "2026-01-04T00:00:00Z", "T1: A")
        second = ordinary_comment(201, "2026-01-05T00:00:00Z", "T2: B")
        comments = [
            first,
            second,
            update_comment(
                202,
                "2026-01-06T00:00:00Z",
                body_hash,
                applied_through=200,
                comment_prefix_sha256=comment_prefix_sha256([first]),
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
        self.assertEqual(
            incremental["comments"]["checkpoint"]["comment_prefix_sha256"],
            comment_prefix_sha256([first]),
        )
        self.assertEqual(
            incremental["comments"]["items"][0]["prefix_sha256"],
            comment_prefix_sha256([first, second]),
        )
        self.assertEqual(
            incremental["comments"]["empty_prefix_sha256"],
            EMPTY_COMMENT_PREFIX_SHA256,
        )
        self.assertEqual(
            EMPTY_COMMENT_PREFIX_SHA256,
            "a25dd454655d825beca003c0269521003571d31a1513eba2bb301f348cde223c",
        )
        self.assertEqual(
            comment_prefix_sha256([first]),
            "45ea42df950f84cf918adfada3f6e3bc2c9200931221d6753c7bcbd96d711080",
        )
        self.assertEqual(
            comment_prefix_sha256([first, second]),
            "0cffb1636a04dd02aa0c2b087022ad8b8afa42f7f4e237800ae42ac0cab46287",
        )
        self.assertEqual(len(incremental["comments"]["updates"]), 1)
        self.assertEqual(
            incremental["comments"]["updates"][0]["comment_prefix_sha256"],
            comment_prefix_sha256([first]),
        )

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
            comment_prefix_sha256=comment_prefix_sha256([source]),
        )
        implementation = copy.deepcopy(self.comments[0])
        implementation["created_at"] = "2026-01-03T00:00:00Z"
        implementation["updated_at"] = "2026-01-03T00:00:00Z"
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
        ]
        comments.append(
            update_comment(
                212,
                "2026-01-05T00:00:00Z",
                body_hash,
                applied_through=210,
                comment_prefix_sha256=comment_prefix_sha256([comments[0]]),
            )
        )
        result = inspect_issue(
            FakeClient([issue], comments={3: comments}),
            3,
            comment_mode="incremental",
        )
        self.assertEqual([item["id"] for item in result["comments"]["items"]], [211])

    def test_stale_checkpoint_falls_back_to_all_without_losing_comments(self) -> None:
        issue = self.issues[2]
        source = ordinary_comment(220, "2026-01-04T00:00:00Z", "T1: A")
        comments = [
            source,
            update_comment(
                221,
                "2026-01-05T00:00:00Z",
                "b" * 64,
                applied_through=220,
                comment_prefix_sha256=comment_prefix_sha256([source]),
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
        source = ordinary_comment(230, "2026-01-04T00:00:00Z", "T1: A")
        comments = [
            source,
            update_comment(
                231,
                "2026-01-05T00:00:00Z",
                body_hash,
                applied_through=230,
                comment_prefix_sha256=comment_prefix_sha256([source]),
            ),
            update_comment(
                232,
                "2026-01-06T00:00:00Z",
                body_hash,
                applied_through=230,
                comment_prefix_sha256=comment_prefix_sha256([source]),
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

    def test_latest_valid_marker_supersedes_older_stale_history(self) -> None:
        issue = self.issues[2]
        body_hash = hashlib.sha256(issue["body"].encode("utf-8")).hexdigest()
        source = ordinary_comment(235, "2026-01-04T00:00:00Z", "T1: A")
        prefix = comment_prefix_sha256([source])
        comments = [
            source,
            update_comment(
                236,
                "2026-01-05T00:00:00Z",
                "b" * 64,
                applied_through=235,
                comment_prefix_sha256=prefix,
            ),
            update_comment(
                237,
                "2026-01-06T00:00:00Z",
                body_hash,
                applied_through=235,
                comment_prefix_sha256=prefix,
            ),
        ]
        result = inspect_issue(
            FakeClient([issue], comments={3: comments}),
            3,
            comment_mode="incremental",
        )["comments"]
        self.assertEqual(result["checkpoint"]["comment_id"], 237)
        self.assertEqual(result["items"], [])
        self.assertEqual(
            [update["comment_id"] for update in result["updates"]], [236, 237]
        )
        self.assertEqual(result["warnings"], [])

    def test_untrusted_marker_does_not_advance_the_checkpoint(self) -> None:
        issue = self.issues[2]
        body_hash = hashlib.sha256(issue["body"].encode("utf-8")).hexdigest()
        source = ordinary_comment(240, "2026-01-04T00:00:00Z", "T1: A")
        comments = [
            source,
            update_comment(
                241,
                "2026-01-05T00:00:00Z",
                body_hash,
                applied_through=240,
                comment_prefix_sha256=comment_prefix_sha256([source]),
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
        self.assertEqual(result["updates"], [])

    def test_out_of_order_applied_comment_forces_safe_fallback(self) -> None:
        issue = self.issues[2]
        body_hash = hashlib.sha256(issue["body"].encode("utf-8")).hexdigest()
        comments = [
            update_comment(
                250,
                "2026-01-04T00:00:00Z",
                body_hash,
                applied_through=251,
                comment_prefix_sha256="a" * 64,
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
        source = ordinary_comment(
            255,
            "2026-01-04T00:00:00Z",
            "T1: changed answer",
            updated_at="2026-01-06T00:00:00Z",
        )
        comments = [
            source,
            update_comment(
                256,
                "2026-01-05T00:00:00Z",
                body_hash,
                applied_through=255,
                comment_prefix_sha256=comment_prefix_sha256([source]),
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

    def test_prefix_digest_detects_edit_before_marker_creation(self) -> None:
        issue = self.issues[2]
        body_hash = hashlib.sha256(issue["body"].encode("utf-8")).hexdigest()
        reviewed = ordinary_comment(270, "2026-01-04T00:00:00Z", "T1: original")
        reviewed_prefix = comment_prefix_sha256([reviewed])
        edited = copy.deepcopy(reviewed)
        edited["body"] = "T1: changed after final revalidation"
        edited["updated_at"] = "2026-01-05T00:00:01Z"
        marker = update_comment(
            271,
            "2026-01-05T00:00:02Z",
            body_hash,
            applied_through=270,
            comment_prefix_sha256=reviewed_prefix,
        )
        result = inspect_issue(
            FakeClient([issue], comments={3: [edited, marker]}),
            3,
            comment_mode="incremental",
        )["comments"]
        self.assertEqual(result["effective_mode"], "all")
        self.assertEqual([item["id"] for item in result["items"]], [270])
        self.assertIn(
            "changed_comment_prefix",
            {warning["code"] for warning in result["warnings"]},
        )

    def test_prefix_digest_binds_every_comment_before_the_source(self) -> None:
        issue = self.issues[2]
        body_hash = hashlib.sha256(issue["body"].encode("utf-8")).hexdigest()
        first = ordinary_comment(272, "2026-01-03T00:00:00Z", "T1: original")
        source = ordinary_comment(273, "2026-01-04T00:00:00Z", "T2: B")
        reviewed_prefix = comment_prefix_sha256([first, source])
        edited_first = copy.deepcopy(first)
        edited_first["body"] = "T1: edited before marker creation"
        edited_first["updated_at"] = "2026-01-05T00:00:01Z"
        marker = update_comment(
            274,
            "2026-01-05T00:00:02Z",
            body_hash,
            applied_through=273,
            comment_prefix_sha256=reviewed_prefix,
        )
        result = inspect_issue(
            FakeClient([issue], comments={3: [edited_first, source, marker]}),
            3,
            comment_mode="incremental",
        )["comments"]
        self.assertEqual(result["effective_mode"], "all")
        self.assertEqual([item["id"] for item in result["items"]], [272, 273])
        self.assertIn(
            "changed_comment_prefix",
            {warning["code"] for warning in result["warnings"]},
        )

    def test_none_checkpoint_requires_no_earlier_ordinary_comment(self) -> None:
        issue = self.issues[2]
        body_hash = hashlib.sha256(issue["body"].encode("utf-8")).hexdigest()
        earlier = ordinary_comment(280, "2026-01-04T00:00:00Z", "T1: A")
        marker = update_comment(
            281,
            "2026-01-05T00:00:00Z",
            body_hash,
            applied_through=None,
            comment_prefix_sha256=EMPTY_COMMENT_PREFIX_SHA256,
        )
        invalid = inspect_issue(
            FakeClient([issue], comments={3: [earlier, marker]}),
            3,
            comment_mode="incremental",
        )["comments"]
        self.assertEqual(invalid["effective_mode"], "all")
        self.assertIsNone(invalid["checkpoint"])
        self.assertIn(
            "invalid_update_checkpoint",
            {warning["code"] for warning in invalid["warnings"]},
        )

        later = ordinary_comment(282, "2026-01-06T00:00:00Z", "T2: B")
        valid = inspect_issue(
            FakeClient([issue], comments={3: [marker, later]}),
            3,
            comment_mode="incremental",
        )["comments"]
        self.assertEqual(valid["effective_mode"], "incremental")
        self.assertEqual(valid["checkpoint"]["applied_through_id"], None)
        self.assertEqual([item["id"] for item in valid["items"]], [282])

        wrong_digest_marker = update_comment(
            283,
            "2026-01-05T00:00:00Z",
            body_hash,
            applied_through=None,
            comment_prefix_sha256="b" * 64,
        )
        wrong_digest = inspect_issue(
            FakeClient([issue], comments={3: [wrong_digest_marker, later]}),
            3,
            comment_mode="incremental",
        )["comments"]
        self.assertEqual(wrong_digest["effective_mode"], "all")
        self.assertIn(
            "changed_comment_prefix",
            {warning["code"] for warning in wrong_digest["warnings"]},
        )

    def test_missing_or_control_source_forces_safe_fallback(self) -> None:
        issue = self.issues[2]
        body_hash = hashlib.sha256(issue["body"].encode("utf-8")).hexdigest()
        ordinary = ordinary_comment(290, "2026-01-04T00:00:00Z", "T1: A")
        for source_id, extra in ((289, []), (100, [self.comments[0]])):
            with self.subTest(source_id=source_id):
                marker = update_comment(
                    291,
                    "2026-01-05T00:00:00Z",
                    body_hash,
                    applied_through=source_id,
                    comment_prefix_sha256="a" * 64,
                )
                result = inspect_issue(
                    FakeClient([issue], comments={3: [*extra, ordinary, marker]}),
                    3,
                    comment_mode="incremental",
                )["comments"]
                self.assertEqual(result["effective_mode"], "all")
                self.assertIn(
                    "invalid_update_checkpoint",
                    {warning["code"] for warning in result["warnings"]},
                )

    def test_control_comments_are_excluded_from_all_items(self) -> None:
        issue = self.issues[2]
        ordinary = ordinary_comment(300, "2026-01-04T00:00:00Z", "T1: A")
        result = inspect_issue(
            FakeClient([issue], comments={3: [*self.comments[:2], ordinary]}),
            3,
            comment_mode="all",
        )["comments"]
        self.assertEqual([item["id"] for item in result["items"]], [300])

    def test_comment_identity_allows_repository_url_case_variance(self) -> None:
        issue = self.issues[2]
        body_hash = hashlib.sha256(issue["body"].encode("utf-8")).hexdigest()
        comment = ordinary_comment(310, "2026-01-04T00:00:00Z", "T1: A")
        comment["html_url"] = str(comment["html_url"]).replace(
            "/acme/widgets/", "/ACME/Widgets/"
        )
        marker = update_comment(
            311,
            "2026-01-05T00:00:00Z",
            body_hash,
            applied_through=310,
            comment_prefix_sha256=comment_prefix_sha256([comment]),
        )
        result = inspect_issue(
            FakeClient([issue], comments={3: [comment, marker]}),
            3,
            comment_mode="incremental",
        )["comments"]
        self.assertEqual(result["items"], [])
        self.assertEqual(result["checkpoint"]["applied_through_id"], 310)

    def test_malformed_comment_metadata_is_an_operational_error(self) -> None:
        issue = self.issues[2]
        source = ordinary_comment(320, "2026-01-04T00:00:00Z", "T1: A")
        variants: list[tuple[str, object]] = [
            ("id", 0),
            ("created_at", None),
            ("created_at", "not-a-timestamp"),
            ("updated_at", None),
            ("updated_at", "2026-01-03T23:59:59Z"),
            ("author_association", None),
            ("body", None),
            ("html_url", "https://ghe.example.test/acme/widgets/issues/3#issuecomment-999"),
            ("user", {"login": 123}),
            ("user", "decision-maker"),
        ]
        for field, value in variants:
            with self.subTest(field=field, value=value):
                malformed = copy.deepcopy(source)
                malformed[field] = value
                with self.assertRaises(BreadcrumbOperationalError) as raised:
                    inspect_issue(
                        FakeClient([issue], comments={3: [malformed]}),
                        3,
                        comment_mode="all",
                    )
                self.assertEqual(raised.exception.code, "invalid_github_response")

    def test_duplicate_comment_identity_is_an_operational_error(self) -> None:
        issue = self.issues[2]
        source = ordinary_comment(330, "2026-01-04T00:00:00Z", "T1: A")
        with self.assertRaises(BreadcrumbOperationalError) as raised:
            inspect_issue(
                FakeClient([issue], comments={3: [source, copy.deepcopy(source)]}),
                3,
                comment_mode="all",
            )
        self.assertEqual(raised.exception.code, "invalid_github_response")


if __name__ == "__main__":
    unittest.main()
