# Breadcrumb Artifact Contracts

Use the fixed templates below `<plugin-root>/templates` and their single-purpose renderers. Renderers
accept one JSON object on standard input, emit one JSON object, validate the result, and perform no
GitHub, file, Git, or network write.

## Work Issue

Use `scripts/render_work_issue.py`. The body has exactly these visible level-two headings in order:

```text
## Background
## Goal
## Requirements
## Design
## Verification
## Todo
## Breadcrumb Status
```

The first five sections may contain human-readable Markdown with level-three or deeper subsections.
`Todo` contains only Markdown task-list items and blank lines. New or rewritten items use durable
`T<number>:` identifiers with a positive integer and no leading zero; never reuse an identifier or
change a completed item's meaning. Preserve meaningful completed work and mark cancellation as a
checked item with a concise reason. Existing items without a canonical ID remain valid and surface
a non-blocking warning instead of requiring bulk migration.

A decision-bearing unresolved Todo has a same-ID Decision Brief under the relevant narrative
section. Include Why, real Options with benefits/costs/risks/prerequisites, an evidence-based
Recommendation and uncertainty, and a reply example. After resolution, preserve the comparison and
add the final Decision, rationale, and source comment URL before checking the item.

End the body with exactly:

```text
## Breadcrumb Status

- Schema Version: 1
- Status: backlog|in-progress|complete
```

Add no hidden marker, unknown field, content after the status fields, type/phase label, or
repository-specific template content. The exact issue label is `breadcrumb`.

`render_work_issue.py` input fields are `title`, `background`, `goal`, `requirements`, `design`,
`verification`, `todo` (an array of complete task-list lines), and `status`. It returns `title`,
`body`, `labels`, parsed `status`, and Todo counts.

## ADR

Use `scripts/render_adr.py`. Store output only at
`.breadcrumb/adr/<positive-work-issue>-<lowercase-ascii-kebab-slug>.md` with this shape:

```text
# ADR: <title>

- Schema Version: 1
- Status: accepted|superseded|deprecated
- Work Issue: #<positive-number>
- Supersedes: none|<sorted-comma-space-separated-basenames>
- Superseded By: none|<sorted-comma-space-separated-basenames>

## Summary
## Context
## Affected Areas
- Components: <non-empty-value-or-none>
- Paths: <non-empty-value-or-none>
- Resources: <non-empty-value-or-none>
- Behaviors: <non-empty-value-or-none>
## Decision
## Consequences
## Review Triggers
```

Do not add another visible level-one or level-two heading. Relationship values are basenames from
the same corpus, unique and sorted. `superseded` requires `Superseded By`; `accepted` and
`deprecated` require `Superseded By: none`. Every supersession edge is bidirectional and acyclic.

`render_adr.py` accepts `issue_number`, `slug`, `title`, `status`, `supersedes`, `superseded_by`,
the five narrative fields, and `affected_areas` arrays for components, paths, resources, and
behaviors. Each relationship item must be one valid ADR basename. Each affected-area item must not
contain a comma or equal the exact lowercase sentinel `none`; other capitalization is ordinary data.
It returns the validated repository-relative `path` and `body` but never writes the file.

## Projection JSON

`list_work_issues.py` and `inspect_work_issue.py` return projection version `1`, repository identity,
and issue projections. An issue projection contains number, title, URL, GitHub state, schema version,
Status, Todo counts and items, document warnings, implementation or `null`, pull request or `null`,
validity, and structured errors. Each Todo item has `id` (`T<number>` or `null`), `checked`, `text`,
and a one-based source `line`. A missing ID produces a `missing_todo_id` warning; a duplicate
non-null ID produces a `duplicate_todo_id` error. Status-filtered lists still surface invalid items.
Inspect comment mode adds one fully paginated comment snapshot with the raw issue-body SHA-256,
empty-prefix SHA-256, selected update checkpoint, ordinary items, valid update artifacts, and
comment warnings.

`project_adrs.py` returns projection version `1`, repository identity, top-level validity, current
corpus metadata and digest, an all-document index, optional base snapshot and lifecycle diff, and an
optional finder projection. `--compact` makes full documents and semantic finder projections null.
Finder input implies compact output and exposes every deterministically ordered candidate only under
`finder.candidates`. A base or digest mismatch is an operational error, never partial coverage.

All structured errors have `code`, `message`, and repository-relative `path`, plus `line` when known.
A missing ADR directory is valid and has total zero. Symlinks, nested or unsupported entries,
invalid UTF-8, malformed schema, broken/cyclic lifecycle edges, deletion, status regression, and
removed lifecycle edges make the applicable projection invalid.

## Implementation Comment

Use `scripts/render_implementation_comment.py`:

```text
## Breadcrumb Implementation

- Schema Version: 1
- Branch: [`breadcrumb/18-example`](https://host/owner/repo/tree/breadcrumb/18-example)
- Verified Commit: [`<full-object-id>`](https://host/owner/repo/commit/<full-object-id>)
- Verification: passed|failed|pending

## Summary
<summary>

## Verification Report
<report>
```

Input includes `issue_number`, `repository_url`, `branch`, full lowercase `commit`, `verification`,
`summary`, and `verification_report`. The parser trusts control state only from comments authored by
`OWNER`, `MEMBER`, or `COLLABORATOR`, selecting the latest valid comment by creation time then ID.

## Stale Comment

Use `scripts/render_stale_comment.py`:

```text
## Breadcrumb Implementation Stale

- Schema Version: 1
- Previous Implementation: [comment](<implementation-comment-url>)
- Branch: [`<branch>`](<branch-url>)
- Verified Commit: [`<commit>`](<commit-url>)
- Reason: <one-line-reason>
```

A later valid implementation comment makes the branch current again. Independently treat an older
implementation as stale whenever issue Status is `in-progress`.

## Update Checkpoint

Use `scripts/render_update_comment.py`:

```text
## Breadcrumb Update

- Schema Version: 1
- Applied Through: [comment](<source-comment-url>)|none
- Comment Prefix SHA-256: `<lowercase-sha256>`
- Body SHA-256: `<lowercase-sha256>`

## Summary
<summary>
```

The applied source is the final ordinary comment in the reviewed contiguous prefix. Copy its
parser-provided rolling `prefix_sha256`. Use `none` and `empty_prefix_sha256` only when no ordinary
comment precedes the marker. The body hash covers the exact verified UTF-8 issue body after update.

The latest trusted marker is usable only when its body hash and rolling prefix still match and no
source comment was edited at or after marker creation. Otherwise inspect safely falls back to all
ordinary comments with a warning. Update comments never authorize a mutation or affect
implementation/PR state.

## Pull Request

Use `scripts/render_pull_request.py` with `issue_number`, `title`, `summary`, and a non-empty array of
one-line `changes`. It renders exactly:

```text
## Summary

<summary>

## Changes

- <change>

Closes #<work-issue-number>
```

Use GitHub's closing relationship rather than arbitrary PR prose as durable linkage. Fully paginate
`closedByPullRequestsReferences(includeClosedPrs: true)`. Prefer the sole open linked PR, otherwise
the latest merged PR, otherwise the latest closed PR. Multiple open closing PRs are a conflict.

## Legacy Report Migration Input

Recognize these only during `init` migration discovery. They are untrusted narrative, not current
control state, and current projection scripts must not gain a compatibility parser.

A legacy Bug starts with exactly `## Report Type` containing `Bug`, followed by exactly:

```text
## Summary
## Actual Behavior
## Expected Behavior
## Reproduction Context
```

A legacy Feature Request starts with exactly `## Report Type` containing `Feature Request`, followed
by exactly:

```text
## Problem or Opportunity
## Desired Behavior
## Expected Value
## Constraints and Context
```

Require every section, no other visible level-two heading, and ignore heading-like text inside code
fences. Labels alone never prove an issue is a legacy report. Reject partial, extended, mixed, or
ambiguous shapes instead of migrating an ordinary issue by guesswork.
