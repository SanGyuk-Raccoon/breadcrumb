---
name: adr
description: "Implement a complete Breadcrumb issue whose repository change is ADR-only. Use to create, supersede, deprecate, verify, commit, push, and record planned ADR changes; do not use for product-code changes, issue-plan mutation, or pull-request creation."
---

# Implement An ADR-only Change

Apply only the ADR files planned by one open, valid, `complete` work issue. Read
[common.md](../../references/common.md), [artifacts.md](../../references/artifacts.md),
[adr.md](../../references/adr.md), and [delivery.md](../../references/delivery.md).

Use `inspect_work_issue.py` to load the complete durable plan and current implementation state.
Use `project_adrs.py` to enforce the recorded Planning Base, corpus digest, lifecycle graph, and
planned diff. Use `render_adr.py` for each planned ADR and `render_implementation_comment.py` for the
verified handoff.

This skill may write only planned `.breadcrumb/adr/*.md` files, create or continue the issue branch,
commit, verify, push, and post one implementation comment. Stop and return to `issue` when the
decision, lifecycle edit, or material scope differs from the plan. Do not modify product code or
tests, change the issue body, or create a pull request.
