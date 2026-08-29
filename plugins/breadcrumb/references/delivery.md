# Shared ADR And Code Delivery

Both `adr` and `implement` produce the same durable handoff: a clean verified commit on the issue
branch, pushed to the remote, followed by one trusted implementation comment. They do not create a
pull request.

## Load Durable Authority

1. Require one open issue with exactly `breadcrumb`, supported schema 1, Status `complete`, and no
   unresolved Todo. Load complete Background through Verification. Repository evidence and this
   durable issue are implementation authority; chat adds no product behavior.
2. Require `.breadcrumb/verification.md` to be a regular tracked file identical to HEAD and the
   fetched default-branch copy. Stop with `init` guidance when missing, modified, unpublished,
   unsafe, or stale.
3. Load all comments and select the latest trusted valid implementation or stale comment. Reuse its
   branch when present. Otherwise derive a lowercase ASCII slug and use
   `breadcrumb/<issue-number>-<slug>` permanently.
4. Load Planning Base, Planned Change Scope, search digest, disposition, proposed ADR files, and
   lifecycle edits. Before touching ADR paths, require the pre-existing corpus to match the planning
   snapshot.

## Resolve The Branch

1. Inspect tracked and untracked work before switching. Stop rather than stash, discard, or absorb
   unrelated changes.
2. Fetch the selected remote and current default branch. Record the exact remote-tracking commit and
   inspect exact local and remote implementation refs.
3. If neither implementation ref exists, create the branch from that fetched default commit without
   another question.
4. If either exists, ask once for `continue` or `start over` unless already supplied.
   - Continue: check out the branch, establish upstream safely, inspect commits/diff, and do only
     remaining work.
   - Start over: state that local and remote content for the same branch will be overwritten without
     a backup; require confirmation, recreate from the recorded default commit, and later use
     force-with-lease tied to the recorded remote SHA. Never force unconditionally.

## Prepare One Commit

Modify only scoped paths. Review the complete diff for unrelated, generated, secret-bearing, or
accidental changes. Stage explicit paths only and inspect the staged path set and diff. Commit
intentionally, require a clean worktree, record full HEAD, and verify only committed content
attributable to that HEAD.

## Verify

1. Reload `.breadcrumb/verification.md`. Combine applicable repository checks with issue
   Verification. Inspect each command before execution and require an explicit working directory,
   non-interactive mode, and finite bound. Reject elevation, credential access, deployment,
   watch/server mode, and destructive data operations.
2. Run safe independent checks even after another fails. Record command, directory, exit code,
   concise redacted evidence, and pending reason.
3. Classify Overall:
   - `failed` when an applicable check fails or guidance is invalid/unsafe;
   - `pending` when an applicable external/manual check or safe command remains unrun;
   - `passed` only when every applicable non-manual check passes and none remains pending.
4. After every command require HEAD unchanged and inspect worktree changes. Commit legitimate fixes
   and rerun all checks needed for one attributable report. Never hide generated files.

## Push And Record

1. Push the exact clean HEAD non-interactively to the exact implementation branch. Use
   fast-forward push for new/continued work or the confirmed lease for start over. Do not comment
   when push fails.
2. Read the remote ref and require it to equal verified local HEAD.
3. Recheck issue comment-write capability and search for a trusted implementation comment with the
   same branch and commit. Reuse it if present.
4. Otherwise render `render_implementation_comment.py` with concise Summary and one Verification
   Report containing Overall and each check's evidence. Record failed/pending attempts as well as
   passed work. POST exactly one comment and verify ID, URL, exact body, target, and provenance.
5. Inspect the final issue projection and report branch, verified commit, remote equality, comment
   URL, Overall, failed/pending checks, and any partial boundary.
