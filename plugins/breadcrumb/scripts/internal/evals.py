"""Side-effect-free validation for public issue-planning evaluation artifacts."""

from __future__ import annotations

import json
import re
import stat
from pathlib import Path
from typing import Any


EVALUATION_VERSION = 1
CATALOG_SCHEMA_VERSION = 1
RESULT_SCHEMA_VERSION = 1
CATALOG_SUITE = "issue-planning"
SOURCE_ISSUES = frozenset({37, 38, 39, 40})
WORK_STATUSES = frozenset({"backlog", "in-progress", "complete"})
IMPLEMENTATION_STATES = frozenset({"none", "current"})
PULL_REQUEST_STATES = frozenset({"none", "open-normal", "open-draft"})
OPERATIONS = frozenset({"open", "update"})
WRITE_KINDS = frozenset(
    {
        "issue:create-selected",
        "issue:create-approved-leaves",
        "issue:patch-selected",
        "issue:patch-approved-created-leaves",
        "issue:comment-update",
        "issue:comment-stale",
        "pull-request:convert-draft",
    }
)
MAX_INPUT_BYTES = 1_000_000

_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class EvaluationInputError(Exception):
    """A file cannot safely provide one evaluation input."""

    def __init__(self, code: str, path: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.path = path
        self.message = message


class _DuplicateJsonKey(ValueError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json_file(path: Path) -> Any:
    """Read one bounded regular non-symlink UTF-8 JSON file."""

    display = str(path)
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise EvaluationInputError(
            "unreadable_input", display, f"cannot inspect input: {exc}"
        ) from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise EvaluationInputError(
            "unsafe_input", display, "input must be a regular non-symlink file"
        )
    if metadata.st_size > MAX_INPUT_BYTES:
        raise EvaluationInputError(
            "input_too_large",
            display,
            f"input exceeds the {MAX_INPUT_BYTES}-byte limit",
        )
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise EvaluationInputError(
            "unreadable_input", display, f"input must be readable UTF-8: {exc}"
        ) from exc
    try:
        return json.loads(text, object_pairs_hook=_strict_object)
    except (json.JSONDecodeError, _DuplicateJsonKey) as exc:
        raise EvaluationInputError(
            "invalid_json", display, f"input must be unambiguous JSON: {exc}"
        ) from exc


def input_error_projection(error: EvaluationInputError) -> dict[str, object]:
    violation = _problem(
        kind="structural",
        source=error.path,
        code=error.code,
        message=error.message,
    )
    return {
        "evaluation_version": EVALUATION_VERSION,
        "valid": False,
        "passed": False,
        "catalog": None,
        "results": [],
        "violations": [violation],
    }


def _problem(
    *,
    kind: str,
    source: str,
    code: str,
    message: str,
    scenario_id: str | None = None,
    expectation_id: str | None = None,
) -> dict[str, object]:
    return {
        "kind": kind,
        "source": source,
        "scenario_id": scenario_id,
        "code": code,
        "expectation_id": expectation_id,
        "message": message,
    }


def _add(
    violations: list[dict[str, object]],
    *,
    source: str,
    code: str,
    message: str,
    scenario_id: str | None = None,
    expectation_id: str | None = None,
    kind: str = "structural",
) -> None:
    violations.append(
        _problem(
            kind=kind,
            source=source,
            scenario_id=scenario_id,
            code=code,
            expectation_id=expectation_id,
            message=message,
        )
    )


def _object(
    value: Any,
    keys: set[str],
    *,
    source: str,
    location: str,
    violations: list[dict[str, object]],
    scenario_id: str | None = None,
) -> dict[str, Any] | None:
    if type(value) is not dict:
        _add(
            violations,
            source=source,
            scenario_id=scenario_id,
            code="invalid_type",
            message=f"{location} must be an object",
        )
        return None
    actual = set(value)
    missing = sorted(keys - actual)
    unknown = sorted(actual - keys)
    if missing:
        _add(
            violations,
            source=source,
            scenario_id=scenario_id,
            code="missing_fields",
            message=f"{location} is missing fields: {', '.join(missing)}",
        )
    if unknown:
        _add(
            violations,
            source=source,
            scenario_id=scenario_id,
            code="unknown_fields",
            message=f"{location} has unknown fields: {', '.join(unknown)}",
        )
    return value


def _text(
    value: Any,
    *,
    source: str,
    location: str,
    violations: list[dict[str, object]],
    scenario_id: str | None = None,
    identifier: bool = False,
) -> str | None:
    if type(value) is not str or not value.strip() or "\x00" in value:
        _add(
            violations,
            source=source,
            scenario_id=scenario_id,
            code="invalid_text",
            message=f"{location} must be a non-empty string without null bytes",
        )
        return None
    normalized = value.strip()
    if identifier and _ID_RE.fullmatch(normalized) is None:
        _add(
            violations,
            source=source,
            scenario_id=scenario_id,
            code="invalid_identifier",
            message=f"{location} must be lowercase ASCII kebab-case",
        )
        return None
    return normalized


def _string_array(
    value: Any,
    *,
    source: str,
    location: str,
    violations: list[dict[str, object]],
    scenario_id: str | None = None,
    required: bool = False,
    identifiers: bool = False,
    allowed: frozenset[str] | None = None,
) -> list[str] | None:
    if type(value) is not list:
        _add(
            violations,
            source=source,
            scenario_id=scenario_id,
            code="invalid_type",
            message=f"{location} must be an array",
        )
        return None
    if required and not value:
        _add(
            violations,
            source=source,
            scenario_id=scenario_id,
            code="empty_array",
            message=f"{location} must not be empty",
        )
    result: list[str] = []
    for index, item in enumerate(value):
        parsed = _text(
            item,
            source=source,
            location=f"{location}[{index}]",
            violations=violations,
            scenario_id=scenario_id,
            identifier=identifiers,
        )
        if parsed is None:
            continue
        if allowed is not None and parsed not in allowed:
            _add(
                violations,
                source=source,
                scenario_id=scenario_id,
                code="unknown_value",
                message=f"{location}[{index}] has unsupported value {parsed}",
            )
            continue
        result.append(parsed)
    if len(result) != len(set(result)):
        _add(
            violations,
            source=source,
            scenario_id=scenario_id,
            code="duplicate_value",
            message=f"{location} must not contain duplicates",
        )
    return result


def _expectation_entries(
    value: Any,
    *,
    source: str,
    location: str,
    violations: list[dict[str, object]],
    scenario_id: str,
) -> dict[str, str] | None:
    if type(value) is not list:
        _add(
            violations,
            source=source,
            scenario_id=scenario_id,
            code="invalid_type",
            message=f"{location} must be an array",
        )
        return None
    if not value:
        _add(
            violations,
            source=source,
            scenario_id=scenario_id,
            code="empty_array",
            message=f"{location} must not be empty",
        )
    result: dict[str, str] = {}
    for index, item in enumerate(value):
        entry = _object(
            item,
            {"id", "description"},
            source=source,
            location=f"{location}[{index}]",
            violations=violations,
            scenario_id=scenario_id,
        )
        if entry is None:
            continue
        identifier = _text(
            entry.get("id"),
            source=source,
            location=f"{location}[{index}].id",
            violations=violations,
            scenario_id=scenario_id,
            identifier=True,
        )
        description = _text(
            entry.get("description"),
            source=source,
            location=f"{location}[{index}].description",
            violations=violations,
            scenario_id=scenario_id,
        )
        if identifier is None or description is None:
            continue
        if identifier in result:
            _add(
                violations,
                source=source,
                scenario_id=scenario_id,
                expectation_id=identifier,
                code="duplicate_expectation",
                message=f"{location} repeats expectation {identifier}",
            )
            continue
        result[identifier] = description
    return result


def _validate_catalog(
    payload: Any, *, source: str
) -> tuple[dict[str, object], dict[str, dict[str, object]], list[dict[str, object]]]:
    violations: list[dict[str, object]] = []
    root = _object(
        payload,
        {"schema_version", "suite", "rules", "scenarios"},
        source=source,
        location="catalog",
        violations=violations,
    )
    if root is None:
        return (
            {"path": source, "suite": None, "rule_count": 0, "scenario_count": 0},
            {},
            violations,
        )

    if (
        type(root.get("schema_version")) is not int
        or root.get("schema_version") != CATALOG_SCHEMA_VERSION
    ):
        _add(
            violations,
            source=source,
            code="unsupported_schema",
            message=(
                "catalog.schema_version must be integer "
                f"{CATALOG_SCHEMA_VERSION}"
            ),
        )
    suite = _text(
        root.get("suite"),
        source=source,
        location="catalog.suite",
        violations=violations,
    )
    if suite is not None and suite != CATALOG_SUITE:
        _add(
            violations,
            source=source,
            code="unsupported_suite",
            message=f"catalog.suite must be {CATALOG_SUITE}",
        )

    rules_value = root.get("rules")
    rules: dict[str, dict[str, object]] = {}
    if type(rules_value) is not list or not rules_value:
        _add(
            violations,
            source=source,
            code="invalid_rules",
            message="catalog.rules must be a non-empty array",
        )
        rules_value = []
    for index, item in enumerate(rules_value):
        entry = _object(
            item,
            {"id", "source_issue", "description"},
            source=source,
            location=f"catalog.rules[{index}]",
            violations=violations,
        )
        if entry is None:
            continue
        identifier = _text(
            entry.get("id"),
            source=source,
            location=f"catalog.rules[{index}].id",
            violations=violations,
            identifier=True,
        )
        source_issue = entry.get("source_issue")
        if type(source_issue) is not int or source_issue not in SOURCE_ISSUES:
            _add(
                violations,
                source=source,
                code="invalid_source_issue",
                message=f"catalog.rules[{index}].source_issue must be 37, 38, 39, or 40",
            )
            source_issue = None
        description = _text(
            entry.get("description"),
            source=source,
            location=f"catalog.rules[{index}].description",
            violations=violations,
        )
        if identifier is None or source_issue is None or description is None:
            continue
        if identifier in rules:
            _add(
                violations,
                source=source,
                code="duplicate_rule",
                expectation_id=identifier,
                message=f"catalog repeats rule {identifier}",
            )
            continue
        rules[identifier] = {
            "source_issue": source_issue,
            "description": description,
        }
    present_sources = {int(rule["source_issue"]) for rule in rules.values()}
    if present_sources != SOURCE_ISSUES:
        missing = sorted(SOURCE_ISSUES - present_sources)
        _add(
            violations,
            source=source,
            code="missing_source_coverage",
            message=f"catalog.rules lacks source issues: {', '.join(map(str, missing))}",
        )

    scenarios_value = root.get("scenarios")
    if type(scenarios_value) is not list or not scenarios_value:
        _add(
            violations,
            source=source,
            code="invalid_scenarios",
            message="catalog.scenarios must be a non-empty array",
        )
        scenarios_value = []
    scenarios: dict[str, dict[str, object]] = {}
    covered_rules: set[str] = set()
    for index, item in enumerate(scenarios_value):
        location = f"catalog.scenarios[{index}]"
        entry = _object(
            item,
            {"id", "title", "covers", "user_prompt", "initial_state", "expected"},
            source=source,
            location=location,
            violations=violations,
        )
        if entry is None:
            continue
        identifier = _text(
            entry.get("id"),
            source=source,
            location=f"{location}.id",
            violations=violations,
            identifier=True,
        )
        scenario_id = identifier
        if identifier is not None and identifier in scenarios:
            _add(
                violations,
                source=source,
                scenario_id=identifier,
                code="duplicate_scenario",
                message=f"catalog repeats scenario {identifier}",
            )
            scenario_id = None
        context_id = identifier
        _text(
            entry.get("title"),
            source=source,
            location=f"{location}.title",
            violations=violations,
            scenario_id=context_id,
        )
        _text(
            entry.get("user_prompt"),
            source=source,
            location=f"{location}.user_prompt",
            violations=violations,
            scenario_id=context_id,
        )
        covers = _string_array(
            entry.get("covers"),
            source=source,
            location=f"{location}.covers",
            violations=violations,
            scenario_id=context_id,
            required=True,
            identifiers=True,
        )
        for rule_id in covers or []:
            if rule_id not in rules:
                _add(
                    violations,
                    source=source,
                    scenario_id=context_id,
                    expectation_id=rule_id,
                    code="unknown_rule",
                    message=f"scenario references undeclared rule {rule_id}",
                )
            else:
                covered_rules.add(rule_id)

        initial = _object(
            entry.get("initial_state"),
            {
                "repository_facts",
                "work_issue",
                "ordinary_comments",
                "implementation",
                "pull_request",
            },
            source=source,
            location=f"{location}.initial_state",
            violations=violations,
            scenario_id=context_id,
        )
        work_issue: dict[str, Any] | None = None
        implementation: str | None = None
        pull_request: str | None = None
        comments: list[str] | None = None
        if initial is not None:
            _string_array(
                initial.get("repository_facts"),
                source=source,
                location=f"{location}.initial_state.repository_facts",
                violations=violations,
                scenario_id=context_id,
                required=True,
            )
            comments = _string_array(
                initial.get("ordinary_comments"),
                source=source,
                location=f"{location}.initial_state.ordinary_comments",
                violations=violations,
                scenario_id=context_id,
            )
            raw_issue = initial.get("work_issue")
            if raw_issue is not None:
                work_issue = _object(
                    raw_issue,
                    {"status", "summary"},
                    source=source,
                    location=f"{location}.initial_state.work_issue",
                    violations=violations,
                    scenario_id=context_id,
                )
                if work_issue is not None:
                    status_value = _text(
                        work_issue.get("status"),
                        source=source,
                        location=f"{location}.initial_state.work_issue.status",
                        violations=violations,
                        scenario_id=context_id,
                    )
                    if status_value is not None and status_value not in WORK_STATUSES:
                        _add(
                            violations,
                            source=source,
                            scenario_id=context_id,
                            code="invalid_work_status",
                            message=f"{location}.initial_state.work_issue.status is unsupported",
                        )
                    _text(
                        work_issue.get("summary"),
                        source=source,
                        location=f"{location}.initial_state.work_issue.summary",
                        violations=violations,
                        scenario_id=context_id,
                    )
            implementation = _text(
                initial.get("implementation"),
                source=source,
                location=f"{location}.initial_state.implementation",
                violations=violations,
                scenario_id=context_id,
            )
            if implementation is not None and implementation not in IMPLEMENTATION_STATES:
                _add(
                    violations,
                    source=source,
                    scenario_id=context_id,
                    code="invalid_implementation_state",
                    message=f"{location}.initial_state.implementation is unsupported",
                )
            pull_request = _text(
                initial.get("pull_request"),
                source=source,
                location=f"{location}.initial_state.pull_request",
                violations=violations,
                scenario_id=context_id,
            )
            if pull_request is not None and pull_request not in PULL_REQUEST_STATES:
                _add(
                    violations,
                    source=source,
                    scenario_id=context_id,
                    code="invalid_pull_request_state",
                    message=f"{location}.initial_state.pull_request is unsupported",
                )

        expected = _object(
            entry.get("expected"),
            {
                "selected_skill",
                "operation",
                "allowed_writes",
                "required_outcomes",
                "forbidden_behaviors",
                "evidence_assertions",
            },
            source=source,
            location=f"{location}.expected",
            violations=violations,
            scenario_id=context_id,
        )
        selected_skill: str | None = None
        operation: str | None = None
        allowed_writes: list[str] | None = None
        outcomes: dict[str, str] | None = None
        forbidden: dict[str, str] | None = None
        assertions: dict[str, str] | None = None
        if expected is not None:
            selected_skill = _text(
                expected.get("selected_skill"),
                source=source,
                location=f"{location}.expected.selected_skill",
                violations=violations,
                scenario_id=context_id,
            )
            if selected_skill is not None and selected_skill != "issue":
                _add(
                    violations,
                    source=source,
                    scenario_id=context_id,
                    code="invalid_selected_skill",
                    message=f"{location}.expected.selected_skill must be issue",
                )
            operation = _text(
                expected.get("operation"),
                source=source,
                location=f"{location}.expected.operation",
                violations=violations,
                scenario_id=context_id,
            )
            if operation is not None and operation not in OPERATIONS:
                _add(
                    violations,
                    source=source,
                    scenario_id=context_id,
                    code="invalid_operation",
                    message=f"{location}.expected.operation must be open or update",
                )
            allowed_writes = _string_array(
                expected.get("allowed_writes"),
                source=source,
                location=f"{location}.expected.allowed_writes",
                violations=violations,
                scenario_id=context_id,
                allowed=WRITE_KINDS,
            )
            outcomes = _expectation_entries(
                expected.get("required_outcomes"),
                source=source,
                location=f"{location}.expected.required_outcomes",
                violations=violations,
                scenario_id=context_id or f"scenario-{index}",
            )
            forbidden = _expectation_entries(
                expected.get("forbidden_behaviors"),
                source=source,
                location=f"{location}.expected.forbidden_behaviors",
                violations=violations,
                scenario_id=context_id or f"scenario-{index}",
            )
            assertions = _expectation_entries(
                expected.get("evidence_assertions"),
                source=source,
                location=f"{location}.expected.evidence_assertions",
                violations=violations,
                scenario_id=context_id or f"scenario-{index}",
            )
            expectation_ids = [
                set(outcomes or {}),
                set(forbidden or {}),
                set(assertions or {}),
            ]
            combined = set().union(*expectation_ids)
            total = sum(len(group) for group in expectation_ids)
            if len(combined) != total:
                _add(
                    violations,
                    source=source,
                    scenario_id=context_id,
                    code="duplicate_expectation",
                    message="expectation IDs must be unique across all categories",
                )

        if operation == "open":
            if (
                work_issue is not None
                or comments
                or implementation != "none"
                or pull_request != "none"
            ):
                _add(
                    violations,
                    source=source,
                    scenario_id=context_id,
                    code="invalid_open_state",
                    message=(
                        "open scenarios must start without issue, comments, "
                        "implementation, or pull request"
                    ),
                )
        elif operation == "update" and work_issue is None:
            _add(
                violations,
                source=source,
                scenario_id=context_id,
                code="invalid_update_state",
                message="update scenarios must start with a work issue",
            )
        if pull_request not in {None, "none"} and implementation != "current":
            _add(
                violations,
                source=source,
                scenario_id=context_id,
                code="orphan_pull_request",
                message="pull-request state requires a current implementation",
            )
        if implementation == "current" and work_issue is not None:
            if work_issue.get("status") != "complete":
                _add(
                    violations,
                    source=source,
                    scenario_id=context_id,
                    code="invalid_current_implementation",
                    message="a current implementation requires a complete initial issue",
                )

        if scenario_id is not None:
            scenarios[scenario_id] = {
                "selected_skill": selected_skill,
                "operation": operation,
                "allowed_writes": frozenset(allowed_writes or []),
                "required_outcomes": frozenset(outcomes or {}),
                "forbidden_behaviors": frozenset(forbidden or {}),
                "evidence_assertions": frozenset(assertions or {}),
            }

    uncovered = sorted(set(rules) - covered_rules)
    for rule_id in uncovered:
        _add(
            violations,
            source=source,
            expectation_id=rule_id,
            code="uncovered_rule",
            message=f"no scenario covers rule {rule_id}",
        )

    projection = {
        "path": source,
        "suite": suite,
        "rule_count": len(rules),
        "scenario_count": len(scenarios),
    }
    return projection, scenarios, violations


def _observed_entries(
    value: Any,
    *,
    source: str,
    location: str,
    scenario_id: str | None,
    violations: list[dict[str, object]],
) -> dict[str, str] | None:
    if type(value) is not list:
        _add(
            violations,
            source=source,
            scenario_id=scenario_id,
            code="invalid_type",
            message=f"{location} must be an array",
        )
        return None
    result: dict[str, str] = {}
    for index, item in enumerate(value):
        entry = _object(
            item,
            {"id", "evidence"},
            source=source,
            location=f"{location}[{index}]",
            violations=violations,
            scenario_id=scenario_id,
        )
        if entry is None:
            continue
        identifier = _text(
            entry.get("id"),
            source=source,
            location=f"{location}[{index}].id",
            violations=violations,
            scenario_id=scenario_id,
            identifier=True,
        )
        evidence = _text(
            entry.get("evidence"),
            source=source,
            location=f"{location}[{index}].evidence",
            violations=violations,
            scenario_id=scenario_id,
        )
        if identifier is None or evidence is None:
            continue
        if identifier in result:
            _add(
                violations,
                source=source,
                scenario_id=scenario_id,
                expectation_id=identifier,
                code="duplicate_observation",
                message=f"{location} repeats {identifier}",
            )
            continue
        result[identifier] = evidence
    return result


def _assertion_entries(
    value: Any,
    *,
    source: str,
    scenario_id: str | None,
    violations: list[dict[str, object]],
) -> dict[str, tuple[bool, str]] | None:
    location = "result.evidence_assertions"
    if type(value) is not list:
        _add(
            violations,
            source=source,
            scenario_id=scenario_id,
            code="invalid_type",
            message=f"{location} must be an array",
        )
        return None
    result: dict[str, tuple[bool, str]] = {}
    for index, item in enumerate(value):
        entry = _object(
            item,
            {"id", "passed", "evidence"},
            source=source,
            location=f"{location}[{index}]",
            violations=violations,
            scenario_id=scenario_id,
        )
        if entry is None:
            continue
        identifier = _text(
            entry.get("id"),
            source=source,
            location=f"{location}[{index}].id",
            violations=violations,
            scenario_id=scenario_id,
            identifier=True,
        )
        passed = entry.get("passed")
        if type(passed) is not bool:
            _add(
                violations,
                source=source,
                scenario_id=scenario_id,
                expectation_id=identifier,
                code="invalid_type",
                message=f"{location}[{index}].passed must be a boolean",
            )
            passed = None
        evidence = _text(
            entry.get("evidence"),
            source=source,
            location=f"{location}[{index}].evidence",
            violations=violations,
            scenario_id=scenario_id,
        )
        if identifier is None or passed is None or evidence is None:
            continue
        if identifier in result:
            _add(
                violations,
                source=source,
                scenario_id=scenario_id,
                expectation_id=identifier,
                code="duplicate_observation",
                message=f"{location} repeats {identifier}",
            )
            continue
        result[identifier] = (passed, evidence)
    return result


def _validate_result(
    payload: Any,
    *,
    source: str,
    scenarios: dict[str, dict[str, object]],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    violations: list[dict[str, object]] = []
    root = _object(
        payload,
        {
            "schema_version",
            "scenario_id",
            "selected_skill",
            "operation",
            "proposed_writes",
            "performed_writes",
            "observed_outcomes",
            "observed_forbidden_behaviors",
            "evidence_assertions",
            "residual_judgments",
        },
        source=source,
        location="result",
        violations=violations,
    )
    if root is None:
        return {"path": source, "scenario_id": None}, violations
    if (
        type(root.get("schema_version")) is not int
        or root.get("schema_version") != RESULT_SCHEMA_VERSION
    ):
        _add(
            violations,
            source=source,
            code="unsupported_schema",
            message=(
                "result.schema_version must be integer "
                f"{RESULT_SCHEMA_VERSION}"
            ),
        )
    scenario_id = _text(
        root.get("scenario_id"),
        source=source,
        location="result.scenario_id",
        violations=violations,
        identifier=True,
    )
    scenario = scenarios.get(scenario_id or "")
    if scenario_id is not None and scenario is None:
        _add(
            violations,
            source=source,
            scenario_id=scenario_id,
            code="unknown_scenario",
            message=f"result references unknown scenario {scenario_id}",
        )
    selected_skill = _text(
        root.get("selected_skill"),
        source=source,
        location="result.selected_skill",
        violations=violations,
        scenario_id=scenario_id,
    )
    operation = _text(
        root.get("operation"),
        source=source,
        location="result.operation",
        violations=violations,
        scenario_id=scenario_id,
    )
    if operation is not None and operation not in OPERATIONS:
        _add(
            violations,
            source=source,
            scenario_id=scenario_id,
            code="invalid_operation",
            message="result.operation must be open or update",
        )
    proposed = _string_array(
        root.get("proposed_writes"),
        source=source,
        location="result.proposed_writes",
        violations=violations,
        scenario_id=scenario_id,
        allowed=WRITE_KINDS,
    )
    performed = _string_array(
        root.get("performed_writes"),
        source=source,
        location="result.performed_writes",
        violations=violations,
        scenario_id=scenario_id,
        allowed=WRITE_KINDS,
    )
    if proposed is not None and performed is not None:
        unexpected_performed = sorted(set(performed) - set(proposed))
        if unexpected_performed:
            _add(
                violations,
                source=source,
                scenario_id=scenario_id,
                code="unproposed_write",
                message="performed writes were not proposed: "
                + ", ".join(unexpected_performed),
            )
    outcomes = _observed_entries(
        root.get("observed_outcomes"),
        source=source,
        location="result.observed_outcomes",
        scenario_id=scenario_id,
        violations=violations,
    )
    forbidden = _observed_entries(
        root.get("observed_forbidden_behaviors"),
        source=source,
        location="result.observed_forbidden_behaviors",
        scenario_id=scenario_id,
        violations=violations,
    )
    assertions = _assertion_entries(
        root.get("evidence_assertions"),
        source=source,
        scenario_id=scenario_id,
        violations=violations,
    )
    _string_array(
        root.get("residual_judgments"),
        source=source,
        location="result.residual_judgments",
        violations=violations,
        scenario_id=scenario_id,
    )

    structural_count = len(violations)
    if scenario is not None and structural_count == 0:
        if selected_skill != scenario["selected_skill"]:
            _add(
                violations,
                source=source,
                scenario_id=scenario_id,
                code="selected_skill_mismatch",
                kind="behavioral",
                message=f"expected selected skill {scenario['selected_skill']}",
            )
        if operation != scenario["operation"]:
            _add(
                violations,
                source=source,
                scenario_id=scenario_id,
                code="operation_mismatch",
                kind="behavioral",
                message=f"expected operation {scenario['operation']}",
            )
        allowed = set(scenario["allowed_writes"])
        unexpected_writes = sorted((set(proposed or []) | set(performed or [])) - allowed)
        for write in unexpected_writes:
            _add(
                violations,
                source=source,
                scenario_id=scenario_id,
                code="write_not_allowed",
                expectation_id=write,
                kind="behavioral",
                message=f"write is outside the current authorization boundary: {write}",
            )

        expected_outcomes = set(scenario["required_outcomes"])
        observed_outcome_ids = set(outcomes or {})
        for unknown in sorted(observed_outcome_ids - expected_outcomes):
            _add(
                violations,
                source=source,
                scenario_id=scenario_id,
                expectation_id=unknown,
                code="unknown_expectation",
                message=f"unknown required-outcome ID {unknown}",
            )
        for missing in sorted(expected_outcomes - observed_outcome_ids):
            _add(
                violations,
                source=source,
                scenario_id=scenario_id,
                expectation_id=missing,
                code="missing_outcome",
                kind="behavioral",
                message=f"required public outcome was not observed: {missing}",
            )

        expected_forbidden = set(scenario["forbidden_behaviors"])
        for observed in sorted(set(forbidden or {})):
            if observed not in expected_forbidden:
                _add(
                    violations,
                    source=source,
                    scenario_id=scenario_id,
                    expectation_id=observed,
                    code="unknown_expectation",
                    message=f"unknown forbidden-behavior ID {observed}",
                )
            else:
                _add(
                    violations,
                    source=source,
                    scenario_id=scenario_id,
                    expectation_id=observed,
                    code="forbidden_behavior_observed",
                    kind="behavioral",
                    message=f"forbidden behavior was observed: {observed}",
                )

        expected_assertions = set(scenario["evidence_assertions"])
        observed_assertions = set(assertions or {})
        for unknown in sorted(observed_assertions - expected_assertions):
            _add(
                violations,
                source=source,
                scenario_id=scenario_id,
                expectation_id=unknown,
                code="unknown_expectation",
                message=f"unknown evidence-assertion ID {unknown}",
            )
        for missing in sorted(expected_assertions - observed_assertions):
            _add(
                violations,
                source=source,
                scenario_id=scenario_id,
                expectation_id=missing,
                code="missing_assertion",
                kind="behavioral",
                message=f"evidence assertion was not reported: {missing}",
            )
        for assertion_id, (passed, _) in (assertions or {}).items():
            if assertion_id in expected_assertions and not passed:
                _add(
                    violations,
                    source=source,
                    scenario_id=scenario_id,
                    expectation_id=assertion_id,
                    code="assertion_failed",
                    kind="behavioral",
                    message=f"evidence assertion failed: {assertion_id}",
                )

    valid = not any(item["kind"] == "structural" for item in violations)
    passed = valid and not any(item["kind"] == "behavioral" for item in violations)
    return {
        "path": source,
        "scenario_id": scenario_id,
        "valid": valid,
        "passed": passed,
    }, violations


def validate_evaluation(
    catalog_payload: Any,
    result_payloads: list[tuple[str, Any]] | None = None,
    *,
    catalog_source: str = "<catalog>",
) -> dict[str, object]:
    """Validate one catalog and zero or more public result summaries."""

    catalog, scenarios, violations = _validate_catalog(
        catalog_payload, source=catalog_source
    )
    catalog_valid = not any(item["kind"] == "structural" for item in violations)
    catalog["valid"] = catalog_valid
    results: list[dict[str, object]] = []
    for source, payload in result_payloads or []:
        if not catalog_valid:
            problem = _problem(
                kind="structural",
                source=source,
                code="catalog_invalid",
                message="result cannot be evaluated against an invalid catalog",
            )
            violations.append(problem)
            results.append(
                {
                    "path": source,
                    "scenario_id": None,
                    "valid": False,
                    "passed": False,
                }
            )
            continue
        result, result_violations = _validate_result(
            payload, source=source, scenarios=scenarios
        )
        results.append(result)
        violations.extend(result_violations)
    valid = not any(item["kind"] == "structural" for item in violations)
    passed = valid and not any(item["kind"] == "behavioral" for item in violations)
    return {
        "evaluation_version": EVALUATION_VERSION,
        "valid": valid,
        "passed": passed,
        "catalog": catalog,
        "results": results,
        "violations": violations,
    }
