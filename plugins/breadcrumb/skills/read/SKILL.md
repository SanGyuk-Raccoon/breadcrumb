---
name: read
description: "Read or review Breadcrumb work issues, comments, ADRs, implementations, and pull-request state without changing anything. Use for lists, durable-context loading, planning review, implementation review, or ambiguous Breadcrumb requests."
---

# Read Breadcrumb State

Provide the read-only surface of the Breadcrumb workflow.

- Use `list` for a compact issue overview.
- Use `load` to resume or explain one issue and its unprocessed decisions.
- Use `review` to critique a plan or implementation without persistence.
- When a Breadcrumb request is ambiguous, load the durable state and present allowed next actions.

Read [common.md](../../references/common.md), [read.md](../../references/read.md), and
[artifacts.md](../../references/artifacts.md). Read [adr.md](../../references/adr.md) when the
answer depends on ADR planning, lifecycle, or implementation evidence.

Use only the operation-specific read-only projections:

```text
<python> <plugin-root>/scripts/list_work_issues.py --gh-executable <gh> [--status <status>] [--include-closed]
<python> <plugin-root>/scripts/inspect_work_issue.py <issue-number> --gh-executable <gh> [--comments incremental|all]
<python> <plugin-root>/scripts/project_adrs.py [--compact] [--base <git-ref>]
```

Do not mutate GitHub, files, branches, commits, or local configuration. Recommend the appropriate
write skill when a review finds follow-up work, but do not invoke that mutation automatically.
