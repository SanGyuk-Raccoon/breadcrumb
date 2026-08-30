---
name: issue
description: "Create or update a Breadcrumb work issue and its durable planning state. Use for requirements, design, Todo, status, comment decisions, or implementation-stale transitions; do not use to edit ADR files, product code, commits, or delivery PR content."
---

# Manage A Work Issue

Own the durable planning transaction for one Breadcrumb work issue. Choose `open` for a new issue
and `update` for an existing issue.

Read [common.md](../../references/common.md), [planning.md](../../references/planning.md),
[issue.md](../../references/issue.md), and [artifacts.md](../../references/artifacts.md). Read
[adr.md](../../references/adr.md) before publishing a `complete` plan or materially reopening one.

Use `inspect_work_issue.py` for current issue and comment state, `project_adrs.py` for the planning
gate, `render_work_issue.py` for a complete issue payload, and `render_update_comment.py` for its
checkpoint. For a coordinated implemented `complete -> in-progress` transition, use
`render_stale_comment.py` after the required confirmation.

When one request needs multiple PR-sized issues, keep it as one planning operation and follow the
leaf proposal, dependency-wave validation, and approved multi-issue creation transaction in the
loaded references.

An ordinary transaction may create or patch only the selected issue and post its update comments.
The approved multi-issue creation transaction may additionally create and link only its exact
previewed leaf set, then keeps one issue selected. The skill's only PR mutation is converting the
already-linked open PR to draft during the confirmed stale transition. It does not write ADR files,
modify product code, commit, push, create a PR, or silently start implementation.
