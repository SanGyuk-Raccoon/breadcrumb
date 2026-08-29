from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from support import SCRIPT_ROOT  # noqa: F401

from internal.adrs import parse_adr_bytes, parse_finder_input_json, project_adr_corpus
from internal.errors import BreadcrumbOperationalError, CliUsageError


def adr_text(
    issue: int,
    *,
    title: str = "Use repository-local decisions",
    status: str = "accepted",
    supersedes: str = "none",
    superseded_by: str = "none",
    affected_paths: str = "src/**",
) -> str:
    return "\n".join(
        [
            f"# ADR: {title}",
            "",
            "- Schema Version: 1",
            f"- Status: {status}",
            f"- Work Issue: #{issue}",
            f"- Supersedes: {supersedes}",
            f"- Superseded By: {superseded_by}",
            "",
            "## Summary",
            "",
            "Keep a durable decision.",
            "",
            "## Context",
            "",
            "The implementation needs a stable constraint.",
            "",
            "## Affected Areas",
            "",
            "- Components: ADR projection",
            f"- Paths: {affected_paths}",
            "- Resources: Git repository",
            "- Behaviors: planning and implementation",
            "",
            "## Decision",
            "",
            "Track the decision with its implementation.",
            "",
            "## Consequences",
            "",
            "The repository gains a small documentation footprint.",
            "",
            "## Review Triggers",
            "",
            "Review when repository-local lookup no longer scales.",
            "",
        ]
    )


def write_adr(root: Path, filename: str, body: str) -> Path:
    directory = root / ".breadcrumb" / "adr"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_text(body, encoding="utf-8")
    return path


def project(root: Path, *, base: str | None = None) -> dict[str, object]:
    return project_adr_corpus(
        root,
        repository="acme/widgets",
        hostname="github.example.test",
        base_ref=base,
    )


class AdrDocumentTests(unittest.TestCase):
    def test_valid_document_exposes_full_and_compact_search_fields(self) -> None:
        document = parse_adr_bytes(
            ".breadcrumb/adr/18-repository-local-decisions.md",
            adr_text(18).encode("utf-8"),
        )
        self.assertTrue(document.valid, document.errors)
        projection = document.projection()
        self.assertEqual(projection["metadata"]["work_issue"], 18)
        self.assertEqual(projection["affected_areas"]["paths"], "src/**")
        compact = document.finder_projection()
        self.assertEqual(compact["content_sha256"], document.content_sha256)
        self.assertEqual(compact["summary"], "Keep a durable decision.")
        self.assertEqual(
            compact["review_triggers"],
            "Review when repository-local lookup no longer scales.",
        )

    def test_filename_metadata_and_affected_area_contracts_are_strict(self) -> None:
        body = (
            adr_text(18)
            .replace("- Schema Version: 1", "- Schema Version: ١")
            .replace("- Components: ADR projection", "- Component: ADR projection")
            .replace(
                "Track the decision with its implementation.",
                "Track the decision with its implementation.\n\n# Extra",
            )
        )
        document = parse_adr_bytes(
            ".breadcrumb/adr/019-Not-Kebab.md",
            body.encode("utf-8"),
        )
        codes = {problem.code for problem in document.errors}
        self.assertIn("invalid_filename", codes)
        self.assertIn("invalid_schema_version", codes)
        self.assertIn("unexpected_heading", codes)
        self.assertIn("unknown_affected_area", codes)
        self.assertIn("missing_affected_area", codes)

    def test_work_issue_status_and_relation_values_are_validated(self) -> None:
        body = adr_text(
            19,
            status="accepted",
            supersedes="20-z.md, 19-a.md, 19-a.md",
            superseded_by="19-successor.md",
        )
        document = parse_adr_bytes(
            ".breadcrumb/adr/18-current.md",
            body.encode("utf-8"),
        )
        codes = {problem.code for problem in document.errors}
        self.assertIn("work_issue_mismatch", codes)
        self.assertIn("duplicate_relation", codes)
        self.assertIn("unsorted_relation", codes)
        self.assertIn("status_relation_mismatch", codes)


class AdrCorpusTests(unittest.TestCase):
    def test_missing_directory_is_a_valid_empty_opt_in_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = project(Path(directory))
        corpus = result["adr_corpus"]
        self.assertTrue(result["valid"])
        self.assertFalse(corpus["present"])
        self.assertEqual(corpus["total"], 0)
        self.assertEqual(corpus["finder_projection"], [])

    def test_valid_supersession_is_bidirectional_and_search_keeps_all_statuses(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_adr(
                root,
                "18-old.md",
                adr_text(18, status="superseded", superseded_by="19-new.md"),
            )
            write_adr(
                root,
                "19-new.md",
                adr_text(19, supersedes="18-old.md"),
            )
            result = project(root)
        self.assertTrue(result["valid"], result["adr_corpus"]["errors"])
        finder = result["adr_corpus"]["finder_projection"]
        self.assertEqual(len(finder), 2)
        self.assertEqual({item["status"] for item in finder}, {"accepted", "superseded"})

    def test_missing_reverse_relation_and_cycle_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_adr(
                root,
                "18-a.md",
                adr_text(
                    18,
                    status="superseded",
                    supersedes="19-b.md",
                    superseded_by="19-b.md",
                ),
            )
            write_adr(
                root,
                "19-b.md",
                adr_text(
                    19,
                    status="superseded",
                    supersedes="18-a.md",
                    superseded_by="18-a.md",
                ),
            )
            result = project(root)
        codes = {error["code"] for error in result["adr_corpus"]["errors"]}
        self.assertIn("lifecycle_cycle", codes)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_adr(
                root,
                "18-old.md",
                adr_text(18, status="superseded", superseded_by="19-new.md"),
            )
            write_adr(root, "19-new.md", adr_text(19))
            result = project(root)
        codes = {error["code"] for error in result["adr_corpus"]["errors"]}
        self.assertIn("asymmetric_relation", codes)

    def test_symlink_nested_unsupported_and_invalid_utf8_entries_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adr_dir = root / ".breadcrumb" / "adr"
            adr_dir.mkdir(parents=True)
            outside = root / "outside.md"
            outside.write_text(adr_text(18), encoding="utf-8")
            (adr_dir / "18-link.md").symlink_to(outside)
            (adr_dir / "notes.txt").write_text("not an ADR", encoding="utf-8")
            (adr_dir / "nested").mkdir()
            (adr_dir / "19-invalid.md").write_bytes(b"\xff")
            result = project(root)
        codes = {error["code"] for error in result["adr_corpus"]["errors"]}
        self.assertTrue(
            {
                "unsafe_symlink",
                "unsupported_file",
                "unsupported_entry",
                "invalid_utf8",
            }.issubset(codes)
        )

    def test_digest_is_stable_and_changes_with_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = write_adr(root, "18-one.md", adr_text(18))
            first = project(root)["adr_corpus"]["digest"]
            second = project(root)["adr_corpus"]["digest"]
            path.write_text(adr_text(18, affected_paths="lib/**"), encoding="utf-8")
            changed = project(root)["adr_corpus"]["digest"]
        self.assertEqual(first, second)
        self.assertNotEqual(first, changed)

    def test_compact_projection_keeps_only_hash_bound_document_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_adr(root, "18-one.md", adr_text(18))
            result = project_adr_corpus(
                root,
                repository="acme/widgets",
                hostname="github.example.test",
                compact=True,
            )
        corpus = result["adr_corpus"]
        self.assertIsNone(corpus["documents"])
        self.assertIsNone(corpus["finder_projection"])
        self.assertEqual(len(corpus["document_index"]), 1)
        self.assertEqual(
            corpus["document_index"][0]["path"],
            ".breadcrumb/adr/18-one.md",
        )
        self.assertRegex(
            corpus["document_index"][0]["content_sha256"], r"^[0-9a-f]{64}$"
        )


class AdrBaseDiffTests(unittest.TestCase):
    def _repository(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
        subprocess.run(
            ["git", "-C", str(root), "config", "user.email", "test@example.test"],
            check=True,
        )
        return temporary, root

    def _commit(self, root: Path) -> str:
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "base"], check=True)
        return subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def test_base_diff_accepts_new_adrs_and_rejects_deletion(self) -> None:
        temporary, root = self._repository()
        self.addCleanup(temporary.cleanup)
        (root / "README.md").write_text("base", encoding="utf-8")
        base = self._commit(root)
        write_adr(root, "18-one.md", adr_text(18))
        result = project(root, base=base)
        self.assertTrue(result["valid"], result)
        self.assertEqual(result["diff"]["added"], [".breadcrumb/adr/18-one.md"])

        self._commit(root)
        (root / ".breadcrumb" / "adr" / "18-one.md").unlink()
        result = project(root, base="HEAD")
        self.assertFalse(result["valid"])
        self.assertIn("adr_deleted", {error["code"] for error in result["diff"]["errors"]})

    def test_base_diff_rejects_status_regression_and_relation_removal(self) -> None:
        temporary, root = self._repository()
        self.addCleanup(temporary.cleanup)
        old = write_adr(
            root,
            "18-old.md",
            adr_text(18, status="superseded", superseded_by="19-new.md"),
        )
        new = write_adr(root, "19-new.md", adr_text(19, supersedes="18-old.md"))
        self._commit(root)

        old.write_text(adr_text(18), encoding="utf-8")
        new.write_text(adr_text(19), encoding="utf-8")
        result = project(root, base="HEAD")
        codes = {error["code"] for error in result["diff"]["errors"]}
        self.assertIn("invalid_status_transition", codes)
        self.assertIn("lifecycle_relation_removed", codes)

    def test_base_diff_requires_new_adrs_to_be_accepted(self) -> None:
        temporary, root = self._repository()
        self.addCleanup(temporary.cleanup)
        (root / "README.md").write_text("base", encoding="utf-8")
        base = self._commit(root)
        write_adr(root, "18-expired.md", adr_text(18, status="deprecated"))
        result = project(root, base=base)
        self.assertFalse(result["valid"])
        self.assertIn(
            "new_adr_not_accepted",
            {error["code"] for error in result["diff"]["errors"]},
        )

    def test_finder_prioritizes_deterministic_signals_without_filtering(self) -> None:
        temporary, root = self._repository()
        self.addCleanup(temporary.cleanup)
        (root / "README.md").write_text("base", encoding="utf-8")
        base = self._commit(root)
        write_adr(root, "18-unrelated.md", adr_text(18, affected_paths="docs/**"))
        write_adr(root, "19-related.md", adr_text(19, affected_paths="src/api/**"))
        digest = project(root)["adr_corpus"]["digest"]
        finder_input = parse_finder_input_json(
            json.dumps(
                {
                    "work_issue": {
                        "number": 20,
                        "title": "Change the API",
                        "url": "https://github.example.test/acme/widgets/issues/20",
                    },
                    "goal": "Change API behavior.",
                    "planning_summary": "Update API request handling.",
                    "proposed_decisions": ["Retain compatibility."],
                    "planned_change_scope": {
                        "components": [],
                        "paths": ["src/api/client.py"],
                        "resources": [],
                        "behaviors": [],
                    },
                    "base_commit": base,
                    "corpus_digest": digest,
                }
            )
        )
        result = project_adr_corpus(
            root,
            repository="acme/widgets",
            hostname="github.example.test",
            base_ref=base,
            finder_input=finder_input,
        )
        candidates = result["finder"]["candidates"]
        self.assertEqual(result["finder"]["coverage_target"], 2)
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0]["path"], ".breadcrumb/adr/19-related.md")
        self.assertEqual(candidates[0]["deterministic_priority"], "path")
        self.assertRegex(candidates[0]["content_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(candidates[1]["deterministic_priority"], "no-explicit-signal")

    def test_empty_corpus_is_ready_with_zero_coverage_and_no_decisions(self) -> None:
        temporary, root = self._repository()
        self.addCleanup(temporary.cleanup)
        (root / "README.md").write_text("base", encoding="utf-8")
        base = self._commit(root)
        digest = project(root)["adr_corpus"]["digest"]
        finder_input = self._finder_input(base=base, digest=digest)

        result = project_adr_corpus(
            root,
            repository="acme/widgets",
            hostname="github.example.test",
            base_ref=base,
            finder_input=finder_input,
        )

        self.assertEqual(result["finder"]["status"], "ready")
        self.assertEqual(result["finder"]["coverage_target"], 0)
        self.assertEqual(result["finder"]["candidates"], [])
        self.assertEqual(result["finder_input"]["proposed_decisions"], [])
        self.assertEqual(result["adr_corpus"]["document_index"], [])
        self.assertIsNone(result["adr_corpus"]["documents"])
        self.assertIsNone(result["adr_corpus"]["finder_projection"])

    def test_invalid_corpus_blocks_finder_candidates(self) -> None:
        temporary, root = self._repository()
        self.addCleanup(temporary.cleanup)
        (root / "README.md").write_text("base", encoding="utf-8")
        base = self._commit(root)
        write_adr(root, "18-invalid.md", adr_text(19))
        digest = project(root)["adr_corpus"]["digest"]

        result = project_adr_corpus(
            root,
            repository="acme/widgets",
            hostname="github.example.test",
            base_ref=base,
            finder_input=self._finder_input(base=base, digest=digest),
        )

        self.assertFalse(result["valid"])
        self.assertEqual(result["finder"]["status"], "blocked")
        self.assertEqual(result["finder"]["coverage_target"], 1)
        self.assertEqual(result["finder"]["candidates"], [])

    def test_finder_rejects_changed_digest_and_non_full_commit(self) -> None:
        temporary, root = self._repository()
        self.addCleanup(temporary.cleanup)
        (root / "README.md").write_text("base", encoding="utf-8")
        base = self._commit(root)
        digest = project(root)["adr_corpus"]["digest"]

        with self.assertRaises(BreadcrumbOperationalError) as raised:
            project_adr_corpus(
                root,
                repository="acme/widgets",
                hostname="github.example.test",
                base_ref=base,
                finder_input=self._finder_input(base=base, digest="0" * 64),
            )
        self.assertEqual(raised.exception.code, "adr_corpus_changed")

        with self.assertRaises(CliUsageError):
            self._finder_input(base=f"{base}0", digest=digest)

    def test_finder_input_normalizes_outer_whitespace_and_duplicate_checks(self) -> None:
        payload = json.loads(
            json.dumps(self._finder_input(base="a" * 40, digest="b" * 64).projection())
        )
        payload["goal"] = "  Change API behavior.  "
        payload["planned_change_scope"]["paths"] = [" src/api/client.py "]
        normalized = parse_finder_input_json(json.dumps(payload))
        self.assertEqual(normalized.goal, "Change API behavior.")
        self.assertEqual(normalized.paths, ("src/api/client.py",))

        payload["planned_change_scope"]["paths"] = ["src/**", " src/** "]
        with self.assertRaises(CliUsageError):
            parse_finder_input_json(json.dumps(payload))

    def _finder_input(self, *, base: str, digest: str):
        return parse_finder_input_json(
            json.dumps(
                {
                    "work_issue": {
                        "number": 20,
                        "title": "Change the API",
                        "url": "https://github.example.test/acme/widgets/issues/20",
                    },
                    "goal": "Change API behavior.",
                    "planning_summary": "Update API request handling.",
                    "proposed_decisions": [],
                    "planned_change_scope": {
                        "components": [],
                        "paths": ["src/api/client.py"],
                        "resources": [],
                        "behaviors": [],
                    },
                    "base_commit": base,
                    "corpus_digest": digest,
                }
            )
        )


if __name__ == "__main__":
    unittest.main()
