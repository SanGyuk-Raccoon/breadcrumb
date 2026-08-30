# Pull-request Publication

## Validate The Handoff

1. Require a valid open issue and current trusted implementation comment. Stop when implementation
   is absent or stale. Require the recorded remote branch to exist at its verified commit.
2. Resolve the current GitHub default branch as base and the implementation branch as head. Load the
   committed merge-base diff and ensure GitHub can form a PR.
3. Run `project_adrs.py --compact --base <planning-base>` and require every ADR addition or lifecycle
   edit to match the issue plan and share the implementation PR.

## Find Existing Delivery

Fully paginate the issue's closing PR relationship and exact open head/base matches:

- return the existing matching open PR instead of duplicating it;
- stop on multiple open closing PRs or conflicting head/base matches;
- return a merged closing PR and create nothing;
- do not treat a closed unmerged PR as successful delivery without explicit direction.

## Render And Create

Read Overall from the latest trusted implementation comment. Use a normal PR by default for
`passed`. For `failed` or `pending`, ask whether to create normal or draft without changing evidence.

Render `render_pull_request.py` using the issue title by default, concise Summary, and Changes based
only on issue, commits, and diff. Changes include:

- `ADR: not required`, or one `ADR: <path>` per created/updated ADR;
- `ADR supersedes: <old> -> <new>` for each replacement;
- concise code/test/documentation changes.

The body ends with exact `Closes #<issue-number>` and targets the current default branch.

Immediately before POST, revalidate repository, issue, implementation comment, remote ref,
head/base tuple, linked/matching PRs, ADR diff, and PR-write capability. Send structured title, body,
head, base, and draft exactly once. Verify returned positive number, URL, head, base, exact body,
draft state, and closing relationship. On ambiguity, query the exact tuple once; never repeat POST
blindly. Do not roll back a successful implementation push when PR publication fails.

This operation performs no worktree edit, commit, push, issue-body update, or implementation repair.
