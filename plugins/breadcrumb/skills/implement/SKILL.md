---
name: implement
description: "Implement and verify one complete Breadcrumb work issue on its work branch. Use for product code, tests, and any planned ADR that ships with the code, through commit, push, and implementation recording; do not use to revise planning or create a pull request."
---

# Implement A Work Issue

Turn one open, valid, `complete` Breadcrumb work issue into a verified remote commit. Read
[common.md](../../references/common.md), [artifacts.md](../../references/artifacts.md),
[adr.md](../../references/adr.md), [delivery.md](../../references/delivery.md), and
[implement.md](../../references/implement.md).

Use `inspect_work_issue.py` to load durable authority and `project_adrs.py` to reconcile the planned
ADR snapshot. Implement code and tests before rendering any planned ADR with `render_adr.py`. Use
`render_implementation_comment.py` only after the exact committed HEAD has been verified and pushed.

This skill may modify scoped code, tests, and planned ADR files; create or continue the issue branch;
commit, verify, push; and post one implementation comment. It does not patch issue planning state or
create a pull request. Stop and return to `issue` when durable meaning, a long-term decision, or
material scope must change.
