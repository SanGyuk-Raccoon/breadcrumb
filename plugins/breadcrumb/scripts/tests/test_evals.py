from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from support import SCRIPT_ROOT  # noqa: F401

import validate_planning_evals
from internal.evals import (
    MAX_INPUT_BYTES,
    EvaluationInputError,
    read_json_file,
    validate_evaluation,
)


CATALOG_PATH = SCRIPT_ROOT.parent / "evals" / "scenarios.json"
REQUIRED_SCENARIOS = {
    "underspecified-open-decision",
    "cohesive-large-change",
    "independent-outcomes-split",
    "coupled-migration-one-pr",
    "cyclic-dependency-rejected",
    "unsupported-decision-uncertainty",
    "placeholder-complete-rejected",
    "conflicting-update-comments",
    "requirements-update-propagation",
    "dependency-update-no-cross-write",
    "material-update-stale",
    "background-clarification-current",
}


def catalog() -> dict[str, object]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def scenario_map(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    return {
        str(item["id"]): item
        for item in payload["scenarios"]  # type: ignore[union-attr]
    }


def passing_result(scenario: dict[str, object]) -> dict[str, object]:
    expected = scenario["expected"]
    assert isinstance(expected, dict)
    return {
        "schema_version": 1,
        "scenario_id": scenario["id"],
        "selected_skill": expected["selected_skill"],
        "operation": expected["operation"],
        "proposed_writes": list(expected["allowed_writes"]),
        "performed_writes": [],
        "observed_outcomes": [
            {"id": item["id"], "evidence": f"Public evidence for {item['id']}."}
            for item in expected["required_outcomes"]
        ],
        "observed_forbidden_behaviors": [],
        "evidence_assertions": [
            {
                "id": item["id"],
                "passed": True,
                "evidence": f"Public evidence for {item['id']}.",
            }
            for item in expected["evidence_assertions"]
        ],
        "residual_judgments": [
            "A reviewer must still judge whether the cited public evidence is persuasive."
        ],
    }


def invoke(arguments: list[str]) -> tuple[int, dict[str, object], str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = validate_planning_evals.main(arguments)
    return exit_code, json.loads(stdout.getvalue()), stderr.getvalue()


class PlanningEvaluationCatalogTests(unittest.TestCase):
    def test_bundled_catalog_covers_every_source_and_required_scenario(self) -> None:
        payload = catalog()
        projection = validate_evaluation(payload, catalog_source=str(CATALOG_PATH))
        self.assertTrue(projection["valid"])
        self.assertTrue(projection["passed"])
        self.assertEqual(projection["violations"], [])
        self.assertEqual(projection["catalog"]["rule_count"], 15)  # type: ignore[index]
        self.assertEqual(projection["catalog"]["scenario_count"], 12)  # type: ignore[index]
        self.assertEqual(set(scenario_map(payload)), REQUIRED_SCENARIOS)
        self.assertEqual(
            {item["source_issue"] for item in payload["rules"]},  # type: ignore[union-attr]
            {37, 38, 39, 40},
        )

    def test_catalog_rejects_unknown_fields_and_uncovered_rules(self) -> None:
        payload = catalog()
        payload["unknown"] = True
        payload["rules"].append(  # type: ignore[union-attr]
            {
                "id": "new-uncovered-rule",
                "source_issue": 37,
                "description": "A new rule must be covered before publication.",
            }
        )
        projection = validate_evaluation(payload)
        self.assertFalse(projection["valid"])
        codes = {item["code"] for item in projection["violations"]}  # type: ignore[union-attr]
        self.assertIn("unknown_fields", codes)
        self.assertIn("uncovered_rule", codes)

    def test_catalog_rejects_inconsistent_open_and_implementation_state(self) -> None:
        payload = catalog()
        scenarios = scenario_map(payload)
        scenarios["underspecified-open-decision"]["initial_state"]["work_issue"] = {  # type: ignore[index]
            "status": "complete",
            "summary": "An open scenario cannot already have a work issue.",
        }
        scenarios["background-clarification-current"]["initial_state"][  # type: ignore[index]
            "work_issue"
        ]["status"] = "in-progress"

        projection = validate_evaluation(payload)

        self.assertFalse(projection["valid"])
        codes = {item["code"] for item in projection["violations"]}  # type: ignore[union-attr]
        self.assertIn("invalid_open_state", codes)
        self.assertIn("invalid_current_implementation", codes)

    def test_every_scenario_accepts_one_complete_public_result(self) -> None:
        payload = catalog()
        results = [
            (f"<{identifier}>", passing_result(scenario))
            for identifier, scenario in scenario_map(payload).items()
        ]
        projection = validate_evaluation(payload, results)
        self.assertTrue(projection["valid"])
        self.assertTrue(projection["passed"])
        self.assertEqual(projection["violations"], [])
        self.assertEqual(len(projection["results"]), 12)

    def test_unresolved_comment_conflict_has_no_write_authority(self) -> None:
        scenario = scenario_map(catalog())["conflicting-update-comments"]
        initial = scenario["initial_state"]
        expected = scenario["expected"]
        assert isinstance(initial, dict)
        assert isinstance(expected, dict)

        self.assertEqual(len(initial["ordinary_comments"]), 2)
        self.assertIn("I have not decided", scenario["user_prompt"])
        self.assertEqual(expected["allowed_writes"], [])
        self.assertEqual(
            {item["id"] for item in expected["required_outcomes"]},
            {"prefix-stops-at-conflict", "conflict-needs-resolution"},
        )

    def test_invalid_complete_request_remains_an_open_operation(self) -> None:
        scenario = scenario_map(catalog())["placeholder-complete-rejected"]
        initial = scenario["initial_state"]
        expected = scenario["expected"]
        assert isinstance(initial, dict)
        assert isinstance(expected, dict)

        self.assertIsNone(initial["work_issue"])
        self.assertIn("Open a work issue", scenario["user_prompt"])
        self.assertEqual(expected["operation"], "open")
        self.assertEqual(expected["allowed_writes"], ["issue:create-selected"])

    def test_underspecified_open_keeps_the_remediation_decision_visible(self) -> None:
        scenario = scenario_map(catalog())["underspecified-open-decision"]
        expected = scenario["expected"]
        assert isinstance(expected, dict)
        outcomes = {
            item["id"]: item["description"]
            for item in expected["required_outcomes"]
        }

        self.assertIn("typed-decision-todo", outcomes)
        self.assertIn("remediation choice", outcomes["typed-decision-todo"])
        self.assertIn("complete-decision-brief", outcomes)

    def test_dependency_and_stale_replays_require_boundary_evidence(self) -> None:
        scenarios = scenario_map(catalog())
        dependency = scenarios["dependency-update-no-cross-write"]["expected"]
        stale = scenarios["material-update-stale"]["expected"]
        assert isinstance(dependency, dict)
        assert isinstance(stale, dict)

        self.assertEqual(
            {item["id"] for item in dependency["required_outcomes"]},
            {
                "dependency-replan-classified",
                "complete-dag-recomputed",
                "related-update-separate",
            },
        )
        self.assertIn(
            "snapshot-rechecks",
            {item["id"] for item in stale["required_outcomes"]},
        )
        self.assertEqual(
            {item["id"] for item in stale["evidence_assertions"]},
            {"partial-result-boundary"},
        )

    def test_behavioral_failure_identifies_scenario_and_expectations(self) -> None:
        payload = catalog()
        scenario = scenario_map(payload)["underspecified-open-decision"]
        result = passing_result(scenario)
        missing = result["observed_outcomes"].pop()  # type: ignore[union-attr]
        expected = scenario["expected"]
        assert isinstance(expected, dict)
        forbidden = expected["forbidden_behaviors"][0]
        result["observed_forbidden_behaviors"] = [
            {"id": forbidden["id"], "evidence": "The response asserted a cause."}
        ]
        failed_assertion = result["evidence_assertions"][0]  # type: ignore[index]
        failed_assertion["passed"] = False

        projection = validate_evaluation(payload, [("<failed>", result)])
        self.assertTrue(projection["valid"])
        self.assertFalse(projection["passed"])
        violations = projection["violations"]
        codes = {item["code"] for item in violations}  # type: ignore[union-attr]
        self.assertEqual(
            codes,
            {"missing_outcome", "forbidden_behavior_observed", "assertion_failed"},
        )
        self.assertTrue(
            all(
                item["scenario_id"] == "underspecified-open-decision"
                for item in violations  # type: ignore[union-attr]
            )
        )
        expectation_ids = {
            item["expectation_id"] for item in violations  # type: ignore[union-attr]
        }
        self.assertIn(missing["id"], expectation_ids)
        self.assertIn(forbidden["id"], expectation_ids)

    def test_result_rejects_unknown_expectation_and_unproposed_write(self) -> None:
        payload = catalog()
        scenario = scenario_map(payload)["independent-outcomes-split"]
        result = passing_result(scenario)
        result["performed_writes"] = ["issue:create-approved-leaves"]
        projection = validate_evaluation(payload, [("<unproposed>", result)])
        self.assertFalse(projection["valid"])
        codes = {item["code"] for item in projection["violations"]}  # type: ignore[union-attr]
        self.assertIn("unproposed_write", codes)

        result = passing_result(scenario)
        result["proposed_writes"] = ["issue:create-approved-leaves"]
        result["performed_writes"] = ["issue:create-approved-leaves"]
        result["observed_outcomes"].append(  # type: ignore[union-attr]
            {"id": "not-declared", "evidence": "Unexpected evidence."}
        )
        projection = validate_evaluation(payload, [("<unexpected>", result)])
        self.assertFalse(projection["valid"])
        codes = {item["code"] for item in projection["violations"]}  # type: ignore[union-attr]
        self.assertIn("unknown_expectation", codes)
        self.assertIn("write_not_allowed", codes)


class PlanningEvaluationEntrypointTests(unittest.TestCase):
    def test_default_entrypoint_is_catalog_only_and_side_effect_free(self) -> None:
        before = CATALOG_PATH.read_bytes()
        exit_code, payload, diagnostic = invoke([])
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["valid"])
        self.assertTrue(payload["passed"])
        self.assertEqual(payload["results"], [])
        self.assertEqual(diagnostic, "")
        self.assertEqual(CATALOG_PATH.read_bytes(), before)

    def test_entrypoint_distinguishes_behavioral_and_structural_failure(self) -> None:
        payload = catalog()
        scenario = scenario_map(payload)["background-clarification-current"]
        result = passing_result(scenario)
        result["evidence_assertions"][0]["passed"] = False  # type: ignore[index]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            failed_path = root / "failed.json"
            failed_path.write_text(json.dumps(result), encoding="utf-8")
            exit_code, projection, _ = invoke(["--result", str(failed_path)])
            self.assertEqual(exit_code, 1)
            self.assertTrue(projection["valid"])
            self.assertFalse(projection["passed"])

            invalid_path = root / "invalid.json"
            invalid_path.write_text('{"schema_version": 1, "schema_version": 1}', encoding="utf-8")
            exit_code, projection, diagnostic = invoke(
                ["--catalog", str(invalid_path)]
            )
            self.assertEqual(exit_code, 2)
            self.assertFalse(projection["valid"])
            self.assertEqual(
                projection["violations"][0]["code"],  # type: ignore[index]
                "invalid_json",
            )
            self.assertTrue(diagnostic)

    def test_reader_rejects_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "catalog.json"
            target.write_text(json.dumps(catalog()), encoding="utf-8")
            link = root / "link.json"
            link.symlink_to(target)
            with self.assertRaises(EvaluationInputError) as raised:
                read_json_file(link)
        self.assertEqual(raised.exception.code, "unsafe_input")

    def test_reader_rejects_oversized_and_non_utf8_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            oversized = root / "oversized.json"
            oversized.write_bytes(b" " * (MAX_INPUT_BYTES + 1))
            with self.assertRaises(EvaluationInputError) as raised:
                read_json_file(oversized)
            self.assertEqual(raised.exception.code, "input_too_large")

            non_utf8 = root / "non-utf8.json"
            non_utf8.write_bytes(b"\xff")
            with self.assertRaises(EvaluationInputError) as raised:
                read_json_file(non_utf8)
            self.assertEqual(raised.exception.code, "unreadable_input")

    def test_entrypoint_rejects_other_operation_shapes(self) -> None:
        exit_code, projection, diagnostic = invoke(["result.json"])
        self.assertEqual(exit_code, 2)
        self.assertFalse(projection["valid"])
        self.assertEqual(
            projection["violations"][0]["code"],  # type: ignore[index]
            "invalid_arguments",
        )
        self.assertTrue(diagnostic)


if __name__ == "__main__":
    unittest.main()
