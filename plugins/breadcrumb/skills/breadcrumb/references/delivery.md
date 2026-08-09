# Implementation And Pull Request Operations

Apply the shared rules in `SKILL.md` and the exact contracts in `artifacts.md`.

## Load Durable Implementation Sources

1. Require an open work issue with exactly the `breadcrumb` label, supported schema 1, Status
   `complete`, and no unresolved Todo. Load its complete Background, Goal, Requirements, Design, and
   Verification sections. Treat them and repository evidence as implementation authority; do not
   add product behavior from chat.
2. Require `.breadcrumb/verification.md` as a regular tracked file identical to current HEAD and to
   the fetched default-branch copy. Stop with `init` guidance when missing, modified, unpublished,
   unsafe, or stale.
3. Fully load comments and select the latest trusted valid implementation or stale comment. Use its
   branch when present. Otherwise derive a lowercase ASCII slug from the current issue title and
   use `breadcrumb/<issue-number>-<slug>`. Keep that branch name stable after creation.

## Resolve The Branch

1. Inspect tracked and untracked work before switching. Stop rather than stash, discard, or absorb
   unrelated changes.
2. Fetch the selected remote and current GitHub default branch. Record its exact remote-tracking
   commit. Check the exact local and remote implementation refs.
3. If neither implementation ref exists, create the branch from the fetched default branch without
   another question.
4. If either ref exists, ask once for `continue` or `start over` unless the user supplied the choice:
   - For continue, check out the branch, establish its upstream safely, and inspect existing
     commits and diff before doing only remaining work.
   - For start over, state that local and remote content for the same branch will be overwritten and
     no backup branch is created. Require explicit confirmation, recreate from the recorded default
     commit, and later use a force-with-lease tied to the recorded remote implementation SHA. Never
     use unconditional force.

## Implement And Verify

1. Map every durable requirement, design decision, implementation step, and Verification item to
   concrete code or tests. Inspect surrounding conventions before editing. Stop and recommend an
   `update` when durable meaning must change.
2. Modify only scoped files. Review the diff for unrelated, generated, secret-bearing, or accidental
   changes. Stage explicit paths only and inspect the staged diff.
3. Commit intentionally. Require a clean working tree after the commit and record the full HEAD.
   Verify only committed content attributable to that HEAD.
4. Reload `.breadcrumb/verification.md`. Combine its applicable repository checks with the issue
   Verification section. Inspect each command before execution; require a finite non-interactive
   bound and explicit working directory. Reject elevation, credential access, external deployment,
   watch/server mode, or destructive data operations.
5. Run safe independent checks even after another fails. Record command, working directory, exit
   code, concise redacted evidence, and pending reason as applicable. Classify Overall:
   - `failed` when any applicable check fails or verification guidance is invalid or unsafe;
   - `pending` when an applicable external/manual check or safe command remains unrun;
   - `passed` only when every applicable non-manual check passes and none remains pending.
6. After every command, require HEAD unchanged and inspect worktree changes. Commit legitimate fixes
   and rerun all checks needed for one attributable report. Never hide unexpected generated files.

## Push And Record

1. Push the exact clean HEAD to the exact implementation branch non-interactively. Use fast-forward
   push for new/continued work or the confirmed lease for start over. Do not comment when push fails.
2. Read the remote ref and require it to equal the verified local HEAD.
3. Recheck comment-write capability and search for an existing trusted comment with the same branch
   and commit. Reuse it when present; otherwise render the fixed implementation template and POST
   exactly one comment.
4. Link the branch and immutable commit. Include a concise Summary and one Verification Report with
   Overall plus each check's evidence. Post `failed` and `pending` attempts as well as passed ones.
5. Inspect the issue projection after POST and report branch, verified commit, push state, comment
   URL, Overall, failed/pending checks, and any partial boundary.

## Create Or Reuse A Pull Request

1. Require a valid open issue and current implementation comment. Stop when implementation is
   absent or stale. Check that the comment branch exists remotely at its verified commit.
2. Resolve the current GitHub default branch as base and the implementation branch as head. Load
   the committed merge-base diff and ensure GitHub can form a PR.
3. Query the issue's fully paginated closing PR relationship and exact head/base open PRs:
   - return the existing matching open PR instead of duplicating it;
   - stop on multiple open closing PRs or conflicting head/base matches;
   - return a merged closing PR and create nothing;
   - do not reuse a merely closed, unmerged PR as successful delivery without explicit direction.
4. Read Overall from the latest trusted implementation comment. Use a normal PR by default for
   `passed`. For `failed` or `pending`, ask whether to create a normal or draft PR; the choice does
   not alter verification evidence.
5. Render the fixed pull-request template using the issue title by default, concise Summary and
   Changes from the durable issue, commits, and diff, and the exact final `Closes #<issue-number>`.
   Target the default branch so GitHub creates the closing relationship.
6. Revalidate repository, issue, implementation comment, remote ref, head/base tuple, linked PRs,
   and PR-write capability immediately before POST. Send title, body, head, base, and draft as
   structured JSON exactly once.
7. Verify the returned PR number, URL, head, base, body, draft state, and closing relationship. On
   ambiguity, query the exact head/base tuple once and never repeat POST blindly. Do not roll back a
   successful implementation push when PR publication fails.
