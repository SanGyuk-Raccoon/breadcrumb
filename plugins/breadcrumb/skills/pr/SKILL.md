---
name: pr
description: "Create or reuse the pull request for a current Breadcrumb implementation comment. Use after ADR-only or code implementation has been verified and pushed; do not use to edit files, create commits, push changes, or revise issue planning."
---

# Publish A Pull Request

Consume the current verified implementation handoff and create or reuse exactly one closing pull
request. Read [common.md](../../references/common.md),
[artifacts.md](../../references/artifacts.md), [adr.md](../../references/adr.md), and
[pr.md](../../references/pr.md).

Use `inspect_work_issue.py` for the trusted implementation comment and linked PR state, and
`project_adrs.py` to validate the committed ADR diff. Use `render_pull_request.py` for the exact title
and body.

This skill may query and create or reuse the matching PR. It does not edit the worktree, commit,
push, alter the issue body, or repair implementation drift. Return to `adr`, `implement`, or `issue`
when its required handoff is absent, stale, or inconsistent.
