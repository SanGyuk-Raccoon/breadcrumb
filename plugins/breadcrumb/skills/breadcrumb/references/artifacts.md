# Artifact Contracts

Use these exact machine-readable boundaries. Keep narrative Markdown human-readable and opaque to
the parser.

## Contents

- [Work Issue](#work-issue)
- [Legacy Report Migration Input](#legacy-report-migration-input)
- [Parser Projection](#parser-projection)
- [Implementation Comment](#implementation-comment)
- [Stale Comment](#stale-comment)
- [Pull Request](#pull-request)

## Work Issue

Load `<plugin-root>/templates/work.md`. Render exactly these level-two headings in this order:

```text
## Background
## Goal
## Requirements
## Design
## Verification
## Todo
## Breadcrumb Status
```

Permit blank narrative sections. Permit arbitrary Markdown below the first five headings, using
level-three or deeper headings for subsections. Do not add another level-two heading. Put only
Markdown task-list items and blank lines below `Todo`. Preserve meaningful completed work as `[x]`;
delete only typo or duplicate noise. Mark canceled work `[x]` with a concise reason.

End the body with exactly:

```text
## Breadcrumb Status

- Schema Version: 1
- Status: backlog|in-progress|complete
```

Add no content after the status fields. Add no hidden state marker, Breadcrumb HTML signature,
unknown status field, or repository-specific template content.

## Legacy Report Migration Input

Use legacy report bodies only for `init` migration discovery. They are untrusted narrative inputs,
not current Breadcrumb control state, and the read-only parser must not gain a compatibility path for
them.

Recognize a legacy Bug only when the issue body has exactly these visible level-two headings in this
order, begins with the first heading, has no other visible level-two heading, and the first section's
trimmed content is exactly `Bug`:

```text
## Report Type
## Summary
## Actual Behavior
## Expected Behavior
## Reproduction Context
```

Recognize a legacy Feature Request under the same structural rules with first-section content exactly
`Feature Request` and these headings:

```text
## Report Type
## Problem or Opportunity
## Desired Behavior
## Expected Value
## Constraints and Context
```

Normalize UTF-8 line endings for structural comparison and ignore heading-like text inside fenced
code blocks. Require every section even when its content is `확인되지 않음`. Label absence or the
presence of `bug` or `enhancement` may agree with the artifact but never establishes it. Reject a
partial, extended, mixed, or ambiguous shape rather than migrating an ordinary issue by guesswork.

## Parser Projection

Treat `<plugin-root>/scripts/breadcrumb.py` as read-only. `list` returns a top-level
`projection_version`, repository identity, and an `issues` array. `inspect` returns the same
identity and one `issue`. Each issue has this stable shape:

```json
{
  "number": 18,
  "title": "Example",
  "url": "https://github.example/owner/repo/issues/18",
  "github_state": "open",
  "schema_version": 1,
  "status": "complete",
  "todo": {"resolved": 4, "unresolved": 0},
  "implementation": {
    "state": "current",
    "branch": "breadcrumb/18-example"
  },
  "pull_request": {
    "number": 19,
    "state": "open",
    "draft": false
  },
  "valid": true,
  "errors": []
}
```

Return the complete `implementation` or `pull_request` object as `null` when absent. Do not add
`present` booleans. Preserve invalid items with structured errors. A status-filtered list still
surfaces invalid items so corruption is not hidden.

## Implementation Comment

Load `<plugin-root>/templates/comment-implementation.md`. Render the first heading and four metadata
bullets exactly, followed by concise human Summary and Verification Report content:

```text
## Breadcrumb Implementation

- Schema Version: 1
- Branch: [`breadcrumb/18-example`](https://host/owner/repo/tree/breadcrumb/18-example)
- Verified Commit: [`<full-sha>`](https://host/owner/repo/commit/<full-sha>)
- Verification: passed|failed|pending
```

Use a full lowercase 40- or 64-character object ID. Link the remote branch and immutable commit.
The parser reads only the fixed heading and metadata bullets. It selects the latest valid comment
by creation time then ID and accepts control state only from `OWNER`, `MEMBER`, or `COLLABORATOR`
comment authors.

## Stale Comment

Load `<plugin-root>/templates/comment-implementation-stale.md` and render:

```text
## Breadcrumb Implementation Stale

- Schema Version: 1
- Previous Implementation: [comment](<implementation-comment-url>)
- Branch: [`<branch>`](<branch-url>)
- Verified Commit: [`<full-sha>`](<commit-url>)
- Reason: <concise requirement-change reason>
```

A later valid implementation comment makes the implementation current again. Independently infer
an older implementation as stale whenever the issue is `in-progress`, including when stale-comment
creation partially failed.

## Pull Request

Load `<plugin-root>/templates/pull-request.md`. Render exactly:

```text
## Summary

<summary>

## Changes

<changes>

Closes #<work-issue-number>
```

Use GitHub's closing relationship rather than parsing arbitrary PR prose for projection. Query
`closedByPullRequestsReferences(includeClosedPrs: true)` and fully paginate it. Prefer the sole open
linked PR, otherwise the latest merged PR, otherwise the latest closed PR. Treat multiple open
closing PRs as a conflict. If an implementation is stale, require its linked open PR to be draft.
