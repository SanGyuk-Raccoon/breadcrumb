"""Project repository-local Breadcrumb ADRs without following unsafe paths."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import stat
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from . import ADR_SCHEMA_VERSION, ADR_STATUSES, PROJECTION_VERSION
from .documents import normalize_markdown
from .errors import BreadcrumbOperationalError, CliUsageError, sanitized


ADR_DIRECTORY = ".breadcrumb/adr"
ADR_HEADINGS = (
    "## Summary",
    "## Context",
    "## Affected Areas",
    "## Decision",
    "## Consequences",
    "## Review Triggers",
)
ADR_METADATA_FIELDS = (
    "Schema Version",
    "Status",
    "Work Issue",
    "Supersedes",
    "Superseded By",
)
ADR_AFFECTED_FIELDS = ("Components", "Paths", "Resources", "Behaviors")

_CORPUS_DIGEST_DOMAIN = b"Breadcrumb ADR Corpus v1\0"
_FILENAME_RE = re.compile(
    r"^(?P<issue>[1-9][0-9]*)-(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)\.md$"
)
_TITLE_RE = re.compile(r"^# ADR: (?P<title>\S(?:.*\S)?)$")
_METADATA_RE = re.compile(r"^- ([A-Za-z][A-Za-z ]*): (\S(?:.*\S)?)$")
_AFFECTED_RE = re.compile(r"^- ([A-Za-z][A-Za-z ]*): (\S(?:.*\S)?)$")
_LEVEL_ONE_HEADING_RE = re.compile(r"^#(?:\s|$).*$")
_LEVEL_TWO_HEADING_RE = re.compile(r"^##(?:\s|$).*$")
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(?:.*)$")
_COMMIT_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")

GitRunner = Callable[..., subprocess.CompletedProcess[bytes]]


def is_valid_adr_basename(value: str) -> bool:
    """Return whether value is one schema 1 ADR basename."""

    return _FILENAME_RE.fullmatch(value) is not None


@dataclass(frozen=True)
class FinderInput:
    work_issue_number: int
    work_issue_title: str
    work_issue_url: str
    goal: str
    planning_summary: str
    proposed_decisions: tuple[str, ...]
    components: tuple[str, ...]
    paths: tuple[str, ...]
    resources: tuple[str, ...]
    behaviors: tuple[str, ...]
    base_commit: str
    corpus_digest: str

    def projection(self) -> dict[str, object]:
        return {
            "work_issue": {
                "number": self.work_issue_number,
                "title": self.work_issue_title,
                "url": self.work_issue_url,
            },
            "goal": self.goal,
            "planning_summary": self.planning_summary,
            "proposed_decisions": list(self.proposed_decisions),
            "planned_change_scope": {
                "components": list(self.components),
                "paths": list(self.paths),
                "resources": list(self.resources),
                "behaviors": list(self.behaviors),
            },
            "base_commit": self.base_commit,
            "corpus_digest": self.corpus_digest,
        }


@dataclass(frozen=True)
class AdrProblem:
    code: str
    message: str
    path: str
    line: int | None = None

    def as_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "code": self.code,
            "message": self.message,
            "path": self.path,
        }
        if self.line is not None:
            result["line"] = self.line
        return result


@dataclass
class _AdrDocument:
    path: str
    basename: str
    content_sha256: str
    title: str | None = None
    schema_version: int | None = None
    status: str | None = None
    work_issue: int | None = None
    supersedes: tuple[str, ...] = ()
    superseded_by: tuple[str, ...] = ()
    sections: dict[str, str] = field(default_factory=dict)
    affected_areas: dict[str, str] = field(default_factory=dict)
    errors: list[AdrProblem] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors

    def projection(self) -> dict[str, object]:
        return {
            "path": self.path,
            "title": self.title,
            "content_sha256": self.content_sha256,
            "metadata": {
                "schema_version": self.schema_version,
                "status": self.status,
                "work_issue": self.work_issue,
                "supersedes": list(self.supersedes),
                "superseded_by": list(self.superseded_by),
            },
            "sections": dict(self.sections),
            "affected_areas": dict(self.affected_areas),
            "valid": self.valid,
            "errors": [problem.as_dict() for problem in self.errors],
        }

    def index_projection(self) -> dict[str, object]:
        return {
            "path": self.path,
            "content_sha256": self.content_sha256,
            "status": self.status,
            "work_issue": self.work_issue,
            "supersedes": list(self.supersedes),
            "superseded_by": list(self.superseded_by),
            "valid": self.valid,
        }

    def finder_projection(self) -> dict[str, object]:
        return {
            "path": self.path,
            "content_sha256": self.content_sha256,
            "title": self.title,
            "status": self.status,
            "work_issue": self.work_issue,
            "supersedes": list(self.supersedes),
            "superseded_by": list(self.superseded_by),
            "summary": self.sections.get("summary", ""),
            "affected_areas": dict(self.affected_areas),
            "review_triggers": self.sections.get("review_triggers", ""),
        }


@dataclass
class _Snapshot:
    present: bool
    documents: dict[str, _AdrDocument]
    errors: list[AdrProblem]
    descriptors: list[dict[str, str]]

    @property
    def digest(self) -> str:
        encoded = json.dumps(
            sorted(self.descriptors, key=lambda item: (item["path"], item["kind"])),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(_CORPUS_DIGEST_DOMAIN + encoded).hexdigest()

    @property
    def valid(self) -> bool:
        return not self.errors


def _exact_keys(value: Mapping[str, Any], expected: set[str], description: str) -> None:
    if set(value) != expected:
        raise CliUsageError(
            f"{description} must contain exactly: {', '.join(sorted(expected))}"
        )


def _nonempty_string(value: object, description: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CliUsageError(f"{description} must be a non-empty string")
    return value.strip()


def _string_list(value: object, description: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise CliUsageError(f"{description} must be an array of non-empty strings")
    normalized = tuple(item.strip() for item in value)
    if len(set(normalized)) != len(normalized):
        raise CliUsageError(f"{description} must not contain duplicates")
    return normalized


def parse_finder_input_json(value: str) -> FinderInput:
    """Parse the compact, exact input contract used by the semantic ADR finder."""

    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise CliUsageError("ADR finder input must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise CliUsageError("ADR finder input must be a JSON object")
    _exact_keys(
        payload,
        {
            "work_issue",
            "goal",
            "planning_summary",
            "proposed_decisions",
            "planned_change_scope",
            "base_commit",
            "corpus_digest",
        },
        "ADR finder input",
    )
    issue = payload["work_issue"]
    if not isinstance(issue, dict):
        raise CliUsageError("ADR finder work_issue must be an object")
    _exact_keys(issue, {"number", "title", "url"}, "ADR finder work_issue")
    number = issue["number"]
    if not isinstance(number, int) or isinstance(number, bool) or number <= 0:
        raise CliUsageError("ADR finder work_issue.number must be a positive integer")

    scope = payload["planned_change_scope"]
    if not isinstance(scope, dict):
        raise CliUsageError("ADR finder planned_change_scope must be an object")
    _exact_keys(
        scope,
        {"components", "paths", "resources", "behaviors"},
        "ADR finder planned_change_scope",
    )
    base_commit = _nonempty_string(payload["base_commit"], "ADR finder base_commit")
    corpus_digest = _nonempty_string(
        payload["corpus_digest"], "ADR finder corpus_digest"
    )
    if not _COMMIT_RE.fullmatch(base_commit):
        raise CliUsageError("ADR finder base_commit must be a full lowercase commit ID")
    if not re.fullmatch(r"[0-9a-f]{64}", corpus_digest):
        raise CliUsageError("ADR finder corpus_digest must be a lowercase SHA-256")
    return FinderInput(
        work_issue_number=number,
        work_issue_title=_nonempty_string(
            issue["title"], "ADR finder work_issue.title"
        ),
        work_issue_url=_nonempty_string(issue["url"], "ADR finder work_issue.url"),
        goal=_nonempty_string(payload["goal"], "ADR finder goal"),
        planning_summary=_nonempty_string(
            payload["planning_summary"], "ADR finder planning_summary"
        ),
        proposed_decisions=_string_list(
            payload["proposed_decisions"],
            "ADR finder proposed_decisions",
        ),
        components=_string_list(scope["components"], "ADR finder components"),
        paths=_string_list(scope["paths"], "ADR finder paths"),
        resources=_string_list(scope["resources"], "ADR finder resources"),
        behaviors=_string_list(scope["behaviors"], "ADR finder behaviors"),
        base_commit=base_commit,
        corpus_digest=corpus_digest,
    )


def _add_problem(
    problems: list[AdrProblem],
    code: str,
    message: str,
    path: str,
    line: int | None = None,
) -> None:
    candidate = AdrProblem(code, message, path, line)
    if candidate not in problems:
        problems.append(candidate)


def _visible_lines(lines: list[str], problems: list[AdrProblem], path: str) -> list[bool]:
    visible: list[bool] = []
    fence_character: str | None = None
    fence_length = 0
    for line in lines:
        if fence_character is None:
            match = _FENCE_RE.fullmatch(line)
            if match is None:
                visible.append(True)
                continue
            marker = match.group(1)
            fence_character = marker[0]
            fence_length = len(marker)
            visible.append(False)
            continue
        visible.append(False)
        closing = line.lstrip(" ")
        if len(line) - len(closing) <= 3:
            marker = closing.rstrip()
            if marker and set(marker) == {fence_character} and len(marker) >= fence_length:
                fence_character = None
                fence_length = 0
    if fence_character is not None:
        _add_problem(
            problems,
            "unterminated_fence",
            "ADR contains an unterminated Markdown fence",
            path,
        )
    return visible


def _parse_relation(
    value: str,
    *,
    field_name: str,
    path: str,
    line: int,
    problems: list[AdrProblem],
) -> tuple[str, ...]:
    if value == "none":
        return ()
    items = value.split(", ")
    if any(not is_valid_adr_basename(item) for item in items):
        _add_problem(
            problems,
            "invalid_relation",
            f"{field_name} must be none or ADR basenames separated by comma-space",
            path,
            line,
        )
    if len(set(items)) != len(items):
        _add_problem(
            problems,
            "duplicate_relation",
            f"{field_name} contains duplicate ADR basenames",
            path,
            line,
        )
    if items != sorted(items):
        _add_problem(
            problems,
            "unsorted_relation",
            f"{field_name} ADR basenames must be sorted",
            path,
            line,
        )
    return tuple(items)


def parse_adr_bytes(path: str, content: bytes) -> _AdrDocument:
    """Parse one ADR and preserve structured errors instead of hiding the file."""

    basename = path.rsplit("/", 1)[-1]
    document = _AdrDocument(path, basename, hashlib.sha256(content).hexdigest())
    filename_match = _FILENAME_RE.fullmatch(basename)
    if filename_match is None:
        _add_problem(
            document.errors,
            "invalid_filename",
            "ADR filename must be <positive-work-issue>-<lowercase-kebab-slug>.md",
            path,
        )

    try:
        value = content.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        _add_problem(
            document.errors,
            "invalid_utf8",
            "ADR must contain valid UTF-8",
            path,
        )
        return document

    lines = normalize_markdown(value).split("\n")
    visible = _visible_lines(lines, document.errors, path)
    title_match = _TITLE_RE.fullmatch(lines[0]) if lines else None
    if title_match is None:
        _add_problem(
            document.errors,
            "invalid_title",
            "ADR must begin with # ADR: <non-empty-title>",
            path,
            1,
        )
    else:
        document.title = title_match.group("title")

    title_matches = [
        index for index, line in enumerate(lines) if visible[index] and _TITLE_RE.fullmatch(line)
    ]
    if len(title_matches) > 1:
        _add_problem(
            document.errors,
            "duplicate_title",
            "ADR title appears more than once",
            path,
            title_matches[1] + 1,
        )

    positions: dict[str, int] = {}
    for heading in ADR_HEADINGS:
        matches = [
            index for index, line in enumerate(lines) if visible[index] and line == heading
        ]
        if not matches:
            _add_problem(
                document.errors,
                "missing_heading",
                f"{heading} is missing",
                path,
            )
        elif len(matches) > 1:
            _add_problem(
                document.errors,
                "duplicate_heading",
                f"{heading} appears more than once",
                path,
                matches[1] + 1,
            )
        else:
            positions[heading] = matches[0]

    for index, line in enumerate(lines):
        if (
            visible[index]
            and index > 0
            and _LEVEL_ONE_HEADING_RE.fullmatch(line)
            and not _TITLE_RE.fullmatch(line)
        ):
            _add_problem(
                document.errors,
                "unexpected_heading",
                f"unexpected level-one heading: {line}",
                path,
                index + 1,
            )
        if (
            visible[index]
            and _LEVEL_TWO_HEADING_RE.fullmatch(line)
            and line not in ADR_HEADINGS
        ):
            _add_problem(
                document.errors,
                "unexpected_heading",
                f"unexpected level-two heading: {line}",
                path,
                index + 1,
            )

    if len(positions) == len(ADR_HEADINGS):
        heading_positions = [positions[heading] for heading in ADR_HEADINGS]
        if heading_positions != sorted(heading_positions):
            _add_problem(
                document.errors,
                "invalid_heading_order",
                "ADR headings do not follow the fixed order",
                path,
            )

    first_heading = min(positions.values(), default=len(lines))
    metadata_lines = [
        (index, lines[index])
        for index in range(1, first_heading)
        if lines[index].strip()
    ]
    metadata: dict[str, tuple[str, int]] = {}
    field_order: list[str] = []
    for index, line in metadata_lines:
        match = _METADATA_RE.fullmatch(line)
        if match is None:
            _add_problem(
                document.errors,
                "invalid_metadata_line",
                "ADR metadata contains an invalid line",
                path,
                index + 1,
            )
            continue
        name, field_value = match.groups()
        if name not in ADR_METADATA_FIELDS:
            _add_problem(
                document.errors,
                "unknown_metadata",
                f"unknown ADR metadata field: {name}",
                path,
                index + 1,
            )
            continue
        if name in metadata:
            _add_problem(
                document.errors,
                "duplicate_metadata",
                f"ADR metadata field {name} appears more than once",
                path,
                index + 1,
            )
            continue
        metadata[name] = (field_value, index + 1)
        field_order.append(name)

    for name in ADR_METADATA_FIELDS:
        if name not in metadata:
            _add_problem(
                document.errors,
                "missing_metadata",
                f"ADR metadata field {name} is missing",
                path,
            )
    if all(name in metadata for name in ADR_METADATA_FIELDS) and tuple(
        field_order
    ) != ADR_METADATA_FIELDS:
        _add_problem(
            document.errors,
            "invalid_metadata_order",
            "ADR metadata fields do not follow the fixed order",
            path,
        )

    if "Schema Version" in metadata:
        raw, line = metadata["Schema Version"]
        if not re.fullmatch(r"[1-9][0-9]*", raw):
            _add_problem(
                document.errors,
                "invalid_schema_version",
                "ADR Schema Version must be a positive ASCII decimal integer",
                path,
                line,
            )
        else:
            document.schema_version = int(raw)
            if document.schema_version != ADR_SCHEMA_VERSION:
                _add_problem(
                    document.errors,
                    "unsupported_schema_version",
                    f"ADR Schema Version {document.schema_version} is not supported",
                    path,
                    line,
                )

    if "Status" in metadata:
        raw, line = metadata["Status"]
        if raw not in ADR_STATUSES:
            _add_problem(
                document.errors,
                "invalid_status",
                "ADR Status must be accepted, superseded, or deprecated",
                path,
                line,
            )
        else:
            document.status = raw

    if "Work Issue" in metadata:
        raw, line = metadata["Work Issue"]
        if not re.fullmatch(r"#[1-9][0-9]*", raw):
            _add_problem(
                document.errors,
                "invalid_work_issue",
                "ADR Work Issue must be # followed by a positive decimal integer",
                path,
                line,
            )
        else:
            document.work_issue = int(raw[1:])
            if filename_match is not None and document.work_issue != int(
                filename_match.group("issue")
            ):
                _add_problem(
                    document.errors,
                    "work_issue_mismatch",
                    "ADR Work Issue does not match the filename",
                    path,
                    line,
                )

    if "Supersedes" in metadata:
        raw, line = metadata["Supersedes"]
        document.supersedes = _parse_relation(
            raw,
            field_name="Supersedes",
            path=path,
            line=line,
            problems=document.errors,
        )
    if "Superseded By" in metadata:
        raw, line = metadata["Superseded By"]
        document.superseded_by = _parse_relation(
            raw,
            field_name="Superseded By",
            path=path,
            line=line,
            problems=document.errors,
        )

    if document.status == "superseded" and not document.superseded_by:
        _add_problem(
            document.errors,
            "missing_successor",
            "a superseded ADR must name at least one successor",
            path,
        )
    if document.status in {"accepted", "deprecated"} and document.superseded_by:
        _add_problem(
            document.errors,
            "status_relation_mismatch",
            f"a {document.status} ADR must use Superseded By: none",
            path,
        )

    if len(positions) == len(ADR_HEADINGS):
        ordered = [positions[heading] for heading in ADR_HEADINGS]
        if ordered == sorted(ordered):
            for offset, heading in enumerate(ADR_HEADINGS):
                start = positions[heading] + 1
                end = (
                    positions[ADR_HEADINGS[offset + 1]]
                    if offset + 1 < len(ADR_HEADINGS)
                    else len(lines)
                )
                key = heading.removeprefix("## ").lower().replace(" ", "_")
                document.sections[key] = "\n".join(lines[start:end]).strip()

    affected = document.sections.get("affected_areas")
    if affected is not None:
        fields: dict[str, tuple[str, int]] = {}
        order: list[str] = []
        affected_start = positions.get("## Affected Areas", -1)
        affected_end = positions.get("## Decision", len(lines))
        for index in range(affected_start + 1, affected_end):
            line = lines[index]
            if not line.strip():
                continue
            match = _AFFECTED_RE.fullmatch(line)
            source_line = index + 1
            if match is None:
                _add_problem(
                    document.errors,
                    "invalid_affected_area",
                    "Affected Areas may contain only its four fixed non-empty fields",
                    path,
                    source_line,
                )
                continue
            name, field_value = match.groups()
            if name not in ADR_AFFECTED_FIELDS:
                _add_problem(
                    document.errors,
                    "unknown_affected_area",
                    f"unknown Affected Areas field: {name}",
                    path,
                    source_line,
                )
                continue
            if name in fields:
                _add_problem(
                    document.errors,
                    "duplicate_affected_area",
                    f"Affected Areas field {name} appears more than once",
                    path,
                    source_line,
                )
                continue
            fields[name] = (field_value, source_line)
            order.append(name)
        for name in ADR_AFFECTED_FIELDS:
            if name not in fields:
                _add_problem(
                    document.errors,
                    "missing_affected_area",
                    f"Affected Areas field {name} is missing or empty",
                    path,
                )
        if all(name in fields for name in ADR_AFFECTED_FIELDS) and tuple(
            order
        ) != ADR_AFFECTED_FIELDS:
            _add_problem(
                document.errors,
                "invalid_affected_area_order",
                "Affected Areas fields do not follow the fixed order",
                path,
            )
        document.affected_areas = {
            name.lower(): fields[name][0]
            for name in ADR_AFFECTED_FIELDS
            if name in fields
        }

    return document


def _safe_worktree_snapshot(root: Path) -> _Snapshot:
    problems: list[AdrProblem] = []
    descriptors: list[dict[str, str]] = []
    documents: dict[str, _AdrDocument] = {}
    breadcrumb_path = root / ".breadcrumb"
    adr_path = breadcrumb_path / "adr"

    for candidate, relative in (
        (breadcrumb_path, ".breadcrumb"),
        (adr_path, ADR_DIRECTORY),
    ):
        try:
            candidate_stat = candidate.lstat()
        except FileNotFoundError:
            return _Snapshot(False, documents, problems, descriptors)
        except OSError as exc:
            _add_problem(
                problems,
                "unreadable_directory",
                f"cannot inspect {relative}: {sanitized(exc)}",
                relative,
            )
            return _Snapshot(False, documents, problems, descriptors)
        if stat.S_ISLNK(candidate_stat.st_mode):
            _add_problem(
                problems,
                "unsafe_symlink",
                f"{relative} must not be a symlink",
                relative,
            )
            descriptors.append({"path": relative, "kind": "symlink", "sha256": "none"})
            return _Snapshot(False, documents, problems, descriptors)
        if not stat.S_ISDIR(candidate_stat.st_mode):
            _add_problem(
                problems,
                "invalid_directory",
                f"{relative} must be a directory",
                relative,
            )
            descriptors.append({"path": relative, "kind": "non-directory", "sha256": "none"})
            return _Snapshot(False, documents, problems, descriptors)

    try:
        entries = sorted(adr_path.iterdir(), key=lambda item: item.name)
    except OSError as exc:
        _add_problem(
            problems,
            "unreadable_directory",
            f"cannot enumerate {ADR_DIRECTORY}: {sanitized(exc)}",
            ADR_DIRECTORY,
        )
        return _Snapshot(True, documents, problems, descriptors)

    for entry in entries:
        try:
            entry.name.encode("utf-8", errors="strict")
            relative = f"{ADR_DIRECTORY}/{entry.name}"
        except UnicodeEncodeError:
            relative = f"{ADR_DIRECTORY}/<invalid-utf8-name>"
            _add_problem(
                problems,
                "invalid_path_encoding",
                "ADR filename must be valid UTF-8",
                relative,
            )
            descriptors.append({"path": relative, "kind": "invalid-name", "sha256": "none"})
            continue
        try:
            before = entry.lstat()
        except OSError as exc:
            _add_problem(
                problems,
                "unreadable_entry",
                f"cannot inspect ADR entry: {sanitized(exc)}",
                relative,
            )
            descriptors.append({"path": relative, "kind": "unreadable", "sha256": "none"})
            continue
        if stat.S_ISLNK(before.st_mode):
            _add_problem(
                problems,
                "unsafe_symlink",
                "ADR entries must not be symlinks",
                relative,
            )
            descriptors.append({"path": relative, "kind": "symlink", "sha256": "none"})
            continue
        if not stat.S_ISREG(before.st_mode):
            _add_problem(
                problems,
                "unsupported_entry",
                "ADR directory may contain only regular Markdown files",
                relative,
            )
            descriptors.append({"path": relative, "kind": "unsupported", "sha256": "none"})
            continue
        if entry.suffix != ".md":
            _add_problem(
                problems,
                "unsupported_file",
                "ADR directory may contain only .md files",
                relative,
            )
            descriptors.append({"path": relative, "kind": "unsupported-file", "sha256": "none"})
            continue
        try:
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(entry, flags)
            try:
                after = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(after.st_mode)
                    or (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)
                ):
                    raise OSError("ADR entry changed while it was being opened")
                with os.fdopen(descriptor, "rb", closefd=False) as source:
                    content = source.read()
            finally:
                os.close(descriptor)
        except OSError as exc:
            _add_problem(
                problems,
                "unreadable_file",
                f"cannot read ADR file: {sanitized(exc)}",
                relative,
            )
            descriptors.append({"path": relative, "kind": "unreadable", "sha256": "none"})
            continue
        document = parse_adr_bytes(relative, content)
        documents[relative] = document
        descriptors.append(
            {"path": relative, "kind": "file", "sha256": document.content_sha256}
        )

    _validate_graph(documents, problems)
    for document in documents.values():
        for problem in document.errors:
            if problem not in problems:
                problems.append(problem)
    return _Snapshot(True, documents, problems, descriptors)


def _run_git_bytes(
    command: list[str], runner: GitRunner, *, code: str, message: str
) -> bytes:
    try:
        result = runner(command, check=False, capture_output=True)
    except FileNotFoundError as exc:
        raise BreadcrumbOperationalError("git_not_found", "git was not found") from exc
    except OSError as exc:
        raise BreadcrumbOperationalError(code, sanitized(exc)) from exc
    if result.returncode != 0:
        detail = sanitized(result.stderr.decode("utf-8", errors="replace").strip())
        raise BreadcrumbOperationalError(code, detail or message)
    return result.stdout


def _git_snapshot(
    root: Path,
    ref: str,
    runner: GitRunner | None = None,
) -> tuple[str, _Snapshot]:
    execute = runner or subprocess.run
    commit_bytes = _run_git_bytes(
        ["git", "-C", str(root), "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}"],
        execute,
        code="invalid_adr_base",
        message="ADR base ref does not identify a commit",
    )
    try:
        commit = commit_bytes.strip().decode("ascii")
    except UnicodeDecodeError as exc:
        raise BreadcrumbOperationalError(
            "invalid_git_response", "Git returned a non-ASCII commit ID"
        ) from exc
    if not _COMMIT_RE.fullmatch(commit):
        raise BreadcrumbOperationalError(
            "invalid_git_response", "Git returned an invalid commit ID"
        )

    tree = _run_git_bytes(
        ["git", "-C", str(root), "ls-tree", "-rz", "--full-tree", commit, "--", ".breadcrumb"],
        execute,
        code="git_error",
        message="Git could not read the ADR base tree",
    )
    problems: list[AdrProblem] = []
    descriptors: list[dict[str, str]] = []
    documents: dict[str, _AdrDocument] = {}
    present = False
    for record in tree.split(b"\0"):
        if not record:
            continue
        try:
            header, raw_path = record.split(b"\t", 1)
            mode, object_type, object_id = header.decode("ascii").split(" ", 2)
            path = raw_path.decode("utf-8", errors="strict")
        except (ValueError, UnicodeDecodeError) as exc:
            raise BreadcrumbOperationalError(
                "invalid_git_response", "Git returned malformed ADR tree data"
            ) from exc

        if path == ".breadcrumb":
            kind = "symlink" if mode == "120000" else "non-directory"
            code = "unsafe_symlink" if mode == "120000" else "invalid_directory"
            _add_problem(
                problems,
                code,
                ".breadcrumb must be a directory in the base tree",
                ".breadcrumb",
            )
            descriptors.append({"path": path, "kind": kind, "sha256": object_id})
            continue
        if path == ADR_DIRECTORY:
            present = True
            kind = "symlink" if mode == "120000" else "non-directory"
            code = "unsafe_symlink" if mode == "120000" else "invalid_directory"
            _add_problem(
                problems,
                code,
                f"{ADR_DIRECTORY} must be a directory in the base tree",
                ADR_DIRECTORY,
            )
            descriptors.append({"path": path, "kind": kind, "sha256": object_id})
            continue
        prefix = f"{ADR_DIRECTORY}/"
        if not path.startswith(prefix):
            continue
        present = True
        remainder = path.removeprefix(prefix)
        if "/" in remainder:
            _add_problem(
                problems,
                "unsupported_entry",
                "ADR directory may not contain nested paths",
                path,
            )
            descriptors.append({"path": path, "kind": "nested", "sha256": object_id})
            continue
        if mode == "120000":
            _add_problem(
                problems,
                "unsafe_symlink",
                "ADR entries must not be symlinks",
                path,
            )
            descriptors.append({"path": path, "kind": "symlink", "sha256": object_id})
            continue
        if object_type != "blob" or not mode.startswith("100"):
            _add_problem(
                problems,
                "unsupported_entry",
                "ADR directory may contain only regular Markdown files",
                path,
            )
            descriptors.append({"path": path, "kind": "unsupported", "sha256": object_id})
            continue
        if not path.endswith(".md"):
            _add_problem(
                problems,
                "unsupported_file",
                "ADR directory may contain only .md files",
                path,
            )
            descriptors.append({"path": path, "kind": "unsupported-file", "sha256": object_id})
            continue
        content = _run_git_bytes(
            ["git", "-C", str(root), "cat-file", "blob", object_id],
            execute,
            code="git_error",
            message="Git could not read an ADR base blob",
        )
        document = parse_adr_bytes(path, content)
        documents[path] = document
        descriptors.append({"path": path, "kind": "file", "sha256": document.content_sha256})

    _validate_graph(documents, problems)
    for document in documents.values():
        for problem in document.errors:
            if problem not in problems:
                problems.append(problem)
    return commit, _Snapshot(present, documents, problems, descriptors)


def _document_problem(
    document: _AdrDocument,
    corpus_problems: list[AdrProblem],
    code: str,
    message: str,
) -> None:
    _add_problem(document.errors, code, message, document.path)
    _add_problem(corpus_problems, code, message, document.path)


def _validate_graph(
    documents: dict[str, _AdrDocument], corpus_problems: list[AdrProblem]
) -> None:
    by_basename = {document.basename: document for document in documents.values()}
    for document in documents.values():
        for relation_name, related_names, reverse_name in (
            ("Supersedes", document.supersedes, "superseded_by"),
            ("Superseded By", document.superseded_by, "supersedes"),
        ):
            for related_name in related_names:
                if related_name == document.basename:
                    _document_problem(
                        document,
                        corpus_problems,
                        "self_relation",
                        f"{relation_name} must not reference the ADR itself",
                    )
                    continue
                related = by_basename.get(related_name)
                if related is None:
                    _document_problem(
                        document,
                        corpus_problems,
                        "missing_relation_target",
                        f"{relation_name} references missing ADR {related_name}",
                    )
                    continue
                reverse = getattr(related, reverse_name)
                if document.basename not in reverse:
                    _document_problem(
                        document,
                        corpus_problems,
                        "asymmetric_relation",
                        f"{relation_name} relationship with {related_name} is not bidirectional",
                    )

    graph = {
        document.basename: tuple(
            related for related in document.supersedes if related in by_basename
        )
        for document in documents.values()
    }
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str, trail: tuple[str, ...]) -> None:
        if name in visiting:
            cycle = trail[trail.index(name) :]
            for member in set(cycle):
                _document_problem(
                    by_basename[member],
                    corpus_problems,
                    "lifecycle_cycle",
                    f"ADR lifecycle contains a cycle: {' -> '.join(cycle)}",
                )
            return
        if name in visited:
            return
        visiting.add(name)
        for related in graph[name]:
            visit(related, trail + (related,))
        visiting.remove(name)
        visited.add(name)

    for basename in sorted(graph):
        visit(basename, (basename,))


def _snapshot_projection(snapshot: _Snapshot, *, include_content: bool) -> dict[str, object]:
    ordered = [snapshot.documents[path] for path in sorted(snapshot.documents)]
    result: dict[str, object] = {
        "schema_version": ADR_SCHEMA_VERSION,
        "path": ADR_DIRECTORY,
        "present": snapshot.present,
        "digest": snapshot.digest,
        "total": len(snapshot.documents),
        "valid": snapshot.valid,
        "errors": [problem.as_dict() for problem in snapshot.errors],
        "document_index": [document.index_projection() for document in ordered],
        "documents": None,
        "finder_projection": None,
    }
    if include_content:
        result["documents"] = [document.projection() for document in ordered]
        result["finder_projection"] = [
            document.finder_projection() for document in ordered
        ]
    return result


def _compare_snapshots(base: _Snapshot, current: _Snapshot) -> dict[str, object]:
    base_paths = set(base.documents)
    current_paths = set(current.documents)
    added = sorted(current_paths - base_paths)
    deleted = sorted(base_paths - current_paths)
    modified = sorted(
        path
        for path in base_paths & current_paths
        if base.documents[path].content_sha256 != current.documents[path].content_sha256
    )
    problems: list[AdrProblem] = []
    for path in deleted:
        _add_problem(
            problems,
            "adr_deleted",
            "ADR files must be retained instead of deleted",
            path,
        )
    for path in added:
        if current.documents[path].status not in {None, "accepted"}:
            _add_problem(
                problems,
                "new_adr_not_accepted",
                "a newly added ADR must use Status: accepted",
                path,
            )
    allowed_transitions = {
        ("accepted", "accepted"),
        ("accepted", "superseded"),
        ("accepted", "deprecated"),
        ("superseded", "superseded"),
        ("deprecated", "deprecated"),
    }
    for path in sorted(base_paths & current_paths):
        previous = base.documents[path]
        candidate = current.documents[path]
        if (
            previous.status is not None
            and candidate.status is not None
            and (previous.status, candidate.status) not in allowed_transitions
        ):
            _add_problem(
                problems,
                "invalid_status_transition",
                f"ADR status may not transition from {previous.status} to {candidate.status}",
                path,
            )
        for field_name, old_values, new_values in (
            ("Supersedes", previous.supersedes, candidate.supersedes),
            ("Superseded By", previous.superseded_by, candidate.superseded_by),
        ):
            removed = sorted(set(old_values) - set(new_values))
            if removed:
                _add_problem(
                    problems,
                    "lifecycle_relation_removed",
                    f"{field_name} must retain existing relationships: {', '.join(removed)}",
                    path,
                )
    return {
        "valid": not problems,
        "added": added,
        "modified": modified,
        "deleted": deleted,
        "errors": [problem.as_dict() for problem in problems],
    }


def _affected_values(value: str) -> tuple[str, ...]:
    if value.strip() == "none":
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def _text_matches(planned: tuple[str, ...], affected: str) -> list[str]:
    affected_values = {_normalized(value) for value in _affected_values(affected)}
    return [value for value in planned if _normalized(value) in affected_values]


def _path_pair_matches(planned: str, affected: str) -> bool:
    left = planned.strip().casefold().rstrip("/")
    right = affected.strip().casefold().rstrip("/")
    if not left or not right:
        return False
    if left == right:
        return True
    if fnmatch.fnmatchcase(left, right) or fnmatch.fnmatchcase(right, left):
        return True
    left_prefix = left.removesuffix("/**").removesuffix("/*")
    right_prefix = right.removesuffix("/**").removesuffix("/*")
    return (
        left_prefix == right_prefix
        or left_prefix.startswith(f"{right_prefix}/")
        or right_prefix.startswith(f"{left_prefix}/")
    )


def _path_matches(planned: tuple[str, ...], affected: str) -> list[str]:
    affected_values = _affected_values(affected)
    return [
        value
        for value in planned
        if any(_path_pair_matches(value, candidate) for candidate in affected_values)
    ]


def _finder_candidates(
    snapshot: _Snapshot, finder_input: FinderInput
) -> list[dict[str, object]]:
    candidates: list[tuple[int, str, dict[str, object]]] = []
    direct_basenames: set[str] = set()
    matches_by_path: dict[str, dict[str, object]] = {}
    for path in sorted(snapshot.documents):
        document = snapshot.documents[path]
        matches: dict[str, object] = {
            "work_issue": document.work_issue == finder_input.work_issue_number,
            "paths": _path_matches(
                finder_input.paths, document.affected_areas.get("paths", "")
            ),
            "components": _text_matches(
                finder_input.components,
                document.affected_areas.get("components", ""),
            ),
            "resources": _text_matches(
                finder_input.resources,
                document.affected_areas.get("resources", ""),
            ),
            "behaviors": _text_matches(
                finder_input.behaviors,
                document.affected_areas.get("behaviors", ""),
            ),
            "relationships": [],
        }
        matches_by_path[path] = matches
        if bool(matches["work_issue"]) or any(
            matches[field]
            for field in ("paths", "components", "resources", "behaviors")
        ):
            direct_basenames.add(document.basename)

    for path in sorted(snapshot.documents):
        document = snapshot.documents[path]
        matches = matches_by_path[path]
        relationships = sorted(
            name
            for name in (*document.supersedes, *document.superseded_by)
            if name in direct_basenames
        )
        matches["relationships"] = relationships
        if matches["work_issue"]:
            priority = 0
            reason = "work-issue"
        elif matches["paths"]:
            priority = 1
            reason = "path"
        elif any(
            matches[field] for field in ("components", "resources", "behaviors")
        ):
            priority = 2
            reason = "affected-area"
        elif relationships:
            priority = 3
            reason = "lifecycle-neighbor"
        else:
            priority = 4
            reason = "no-explicit-signal"
        projection = document.finder_projection()
        projection["deterministic_priority"] = reason
        projection["deterministic_matches"] = matches
        candidates.append((priority, path, projection))
    return [projection for _, _, projection in sorted(candidates)]


def project_adr_corpus(
    root: Path,
    *,
    repository: str,
    hostname: str,
    base_ref: str | None = None,
    finder_input: FinderInput | None = None,
    compact: bool = False,
    git_runner: GitRunner | None = None,
) -> dict[str, object]:
    """Return the current ADR corpus and an optional structural base diff."""

    current = _safe_worktree_snapshot(root.resolve())
    base_projection: dict[str, object] | None = None
    diff: dict[str, object] | None = None
    valid = current.valid
    if base_ref is not None:
        commit, base = _git_snapshot(root.resolve(), base_ref, git_runner)
        base_projection = {
            "ref": base_ref,
            "commit": commit,
            "corpus": _snapshot_projection(base, include_content=False),
        }
        diff = _compare_snapshots(base, current)
        valid = valid and base.valid and bool(diff["valid"])
    finder: dict[str, object] | None = None
    if finder_input is not None:
        if base_projection is None:
            raise CliUsageError("ADR finder input requires --base")
        if finder_input.base_commit != base_projection["commit"]:
            raise BreadcrumbOperationalError(
                "adr_base_changed",
                "ADR finder base commit does not match the resolved --base commit",
            )
        if finder_input.corpus_digest != current.digest:
            raise BreadcrumbOperationalError(
                "adr_corpus_changed",
                "ADR finder corpus digest does not match the current corpus",
            )
        if not valid:
            finder = {
                "status": "blocked",
                "reason": "invalid-corpus-or-diff",
                "coverage_target": len(current.documents),
                "candidates": [],
            }
        else:
            finder = {
                "status": "ready",
                "reason": None,
                "coverage_target": len(current.documents),
                "candidates": _finder_candidates(current, finder_input),
            }
    compact_output = compact or finder_input is not None
    return {
        "projection_version": PROJECTION_VERSION,
        "hostname": hostname,
        "repository": repository,
        "valid": valid,
        "adr_corpus": _snapshot_projection(current, include_content=not compact_output),
        "base": base_projection,
        "diff": diff,
        "finder_input": finder_input.projection() if finder_input is not None else None,
        "finder": finder,
    }
