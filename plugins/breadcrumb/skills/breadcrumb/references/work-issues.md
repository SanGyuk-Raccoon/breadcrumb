# Repository And Work-Issue Operations

Apply the shared rules in `SKILL.md` and the exact contracts in `artifacts.md`.

## Contents

- [Initialize Or Audit](#initialize-or-audit)
- [Open](#open)
- [List](#list)
- [Load](#load)
- [Update](#update)
- [Review](#review)

## Initialize Or Audit

Treat repository setup, re-audit, and version migration as one `init` operation. Discovery is always
read-only; an explicit init request does not approve migration side effects.

### Resolve Readiness

1. Resolve the Git root, selected remote, GitHub repository, and current default branch without a
   Breadcrumb config file. Check Git, GitHub CLI, Python 3.11+, authentication, Issues availability,
   issue/comment/PR write capability needed by the requested workflow, fetch access, and push access
   separately.
2. Require one exact `breadcrumb` label. Create it during an explicitly requested initialization
   when missing. Do not create phase or type labels.
3. Require `.breadcrumb/verification.md` to be a regular in-repository file. If absent, inspect the
   repository's documented commands and CI, draft concise natural-language verification guidance,
   and persist it within the requested init scope. Never copy an unsafe command blindly.
4. Require `verification.md` to be tracked, unmodified, and published on the fetched default branch
   before implementation. Permit issue-only operations while it is missing, but report that
   implementation is not ready.

### Discover Version Migration

1. Inventory `.breadcrumb/config.json`, `.breadcrumb/templates`, and every path contained by that
   directory without reading file bytes, loading template overrides, or following a symlink. Record
   the exact path, kind, containment, tracking, staged/unstaged state, and whether the fetched default
   branch contains each artifact.
2. Fully paginate repository labels and GitHub-open issues. Find issues carrying
   `breadcrumb:backlog`, `breadcrumb:requirement`, or `breadcrumb:design`, and independently find
   issue bodies matching a complete legacy Bug or Feature Request contract from `artifacts.md`.
   Exclude pull requests. A label alone never proves that an ordinary issue is a legacy report.
3. Leave every already-closed issue body untouched. Read a closed issue or merged pull request only
   when needed as evidence that an open migration candidate has already been delivered.
4. Compare the worktree, index, local commits, fetched default branch, and planned verification
   publication. If one unpublished commit contains both supported setup state and legacy files,
   record the exact commit and paths; do not push it before the user chooses cleanup or intentional
   preservation and publication.
5. When no local or GitHub migration candidate exists, ask no migration question and finish the
   ordinary readiness audit.

### Plan And Confirm Migration

1. Group local file cleanup separately from GitHub issue, close/relabel, and label-deletion actions.
   Show the selected repository and every exact path, issue number, current and final title, complete
   final body, current and final label set, close action, affected local commit, and closed-issue
   metadata effect before the first mutation.
2. For one open requirement/design pair, select a canonical work issue only from durable lineage and
   body context, never titles alone. Combine all material Background through Design and Todo context
   into the proposed work body and show how the redundant open issue will be closed or relabeled.
3. Convert an unpaired open legacy phase issue in place only when its meaning is unambiguous. For an
   undelivered legacy Bug, map report type, summary, actual behavior, and reproduction context to
   Background and expected behavior to Goal. For an undelivered Feature Request, map report type,
   problem, and context to Background, desired behavior to Goal, and expected value and constraints
   to Requirements. Preserve all material narrative in a schema 1 work issue, set `Status: backlog`,
   add exactly `- [ ] 보고 내용을 구현 가능한 요구사항, 설계와 검증 계획으로 정제한다.`, and use
   only `breadcrumb` as its final label. When a merged PR already satisfies a report, show that exact
   evidence and proposed close action instead of pretending it remains backlog work.
4. Ask explicitly before removing legacy files, rewriting an unpublished setup commit,
   bulk-migrating issues, or publishing a commit that intentionally retains unsupported files. Ask
   separately before deleting legacy labels. A changed path, issue, body, label, commit, or delivery
   basis invalidates the corresponding approval. Never rewrite a commit reachable from a published
   ref.
5. When the user declines, preserve every declined artifact. Report that the current Breadcrumb
   version ignores it, the effect on readiness, and the exact remaining follow-up.

### Apply Approved Migration

1. Immediately revalidate repository identity, default branch, complete worktree/index state,
   candidate paths without following symlinks, labels, issue bodies/states, linked delivery evidence,
   and every approved payload. Stop before the first write when the basis changed.
2. Remove only approved exact legacy paths. Preserve unrelated and overlapping user changes; stage
   only approved paths, inspect the staged path set and diff, and use a scoped commit when repository
   state must be published. Never infer history rewriting, staging of unrelated files, or a push.
3. Apply each approved issue body/label/close mutation once with structured JSON and explicit
   owner/repository. Verify each successful issue number and final state before continuing. Never
   create a replacement issue when an in-place conversion was approved.
4. Requery until no GitHub-open legacy phase or report issue remains. Only then may a separately
   approved deletion remove the three legacy labels; explain that deletion removes label metadata
   from historical closed issues without changing their bodies.
5. Stop on failure or uncertainty. Preserve successful earlier operations, do not retry or roll them
   back blindly, and report completed, failed or uncertain, and unattempted steps separately.

### Report Readiness

Report readiness by operation rather than one global boolean: issue reads, issue writes,
implementation fetch/push, verification, and PR writes. Include preserved or unpublished legacy
state only where it affects that operation.

## Open

1. Treat conversation as source material until publication. Extract Background, Goal,
   Requirements, Design, Verification, and Todo. Ask one focused question only when the answer would
   materially change scope or acceptance. Save unresolved decisions as concrete unchecked Todo.
2. Evaluate one-pull-request scope before detailed refinement and after scope-changing answers.
   Split only for independently implementable, verifiable, deployable, or reviewable outcomes; do
   not split by file count, line count, or elapsed-time estimates. Show proposed leaf issues and ask
   before creating more than one.
3. Choose initial Status from actual readiness: `backlog` when merely captured and not started,
   `in-progress` when refinement is active with unresolved Todo, or `complete` when the body is
   implementation-ready with none unresolved. Permit direct `backlog -> complete` when planning is
   completed before publication.
4. Render the fixed `work.md`, concise title, and exact `breadcrumb` label. When the user explicitly
   requested issue creation, that request authorizes the ordinary single POST. Otherwise show the
   complete proposal and wait for approval.
5. Revalidate repository identity, Issues capability, label presence, rendered body, and title
   immediately before POST. Send title, exact body, and `labels: ["breadcrumb"]` as structured JSON.
   Confirm the returned issue number, URL, title, body, and label. On uncertainty, GET that returned
   number once and never replay the POST blindly.
6. Select the confirmed issue for the current conversation. Do not automatically implement it.

## List

1. Run `breadcrumb.py list`, adding a requested Status filter or `--include-closed` only when asked.
2. Use only returned projection fields. Do not load full bodies, comments, diffs, commits, or
   verification reports for an overview.
3. Group compact output by `in-progress`, `complete`, then `backlog`, and identify invalid items
   separately. Show issue number/title, GitHub state, Todo counts, implementation state/branch, and
   PR number/state/draft when present.
4. Perform no side effects and do not enrich projection state from conversation or local guesses.

## Load

1. Run `breadcrumb.py inspect <number>`, then fetch the complete issue body and only the comments or
   linked metadata needed to explain durable context. Conversation may identify the target but may
   not replace durable issue meaning.
2. Summarize identity, GitHub state, Status, Background, Goal, Requirements, Design, Verification,
   resolved and unresolved Todo, implementation current/stale state, branch, and linked PR.
3. Name malformed or conflicting metadata and resulting uncertainty. Offer only operations allowed
   by the current projection. Do not perform one automatically.

## Update

1. Require one open issue. Load its latest body and projection immediately before editing. Preserve
   all unchanged sections and unrelated labels. Use one body PATCH for an ordinary update.
2. Reflect each completed Todo conclusion in the relevant narrative section before checking it.
   Append newly discovered next actions instead of pretending the original list was final.
3. Reassess one-pull-request scope. Recommend a split when independent outcomes emerged, explain
   each boundary, and stop before creating another issue unless the user separately approves an
   `open` operation.
4. Keep Status and Todo consistent. A routine body update requested explicitly needs no second
   approval. Show and confirm a complete normalized replacement before repairing malformed schema
   1 content. Stop without editing an unsupported future schema.
5. For `complete -> in-progress` with an existing implementation, perform one coordinated update:
   - show the final body, stale comment, and affected open PR;
   - obtain confirmation;
   - convert a linked open non-draft PR to draft first and verify it;
   - PATCH the body with a concrete unresolved Todo and `in-progress`;
   - POST the fixed stale comment referencing the latest implementation;
   - inspect the final projection.
6. Stop before body mutation if draft conversion fails. If the body update succeeds but stale
   comment creation fails, report partial completion; the parser must still infer stale from
   `in-progress`.

## Review

1. Choose issue-planning or implementation review from explicit intent. Ask one target question only
   when genuinely ambiguous.
2. Keep the operation read-only. For planning, review Background through Verification for clarity,
   cohesion, observable behavior, technical sufficiency, risks, and unresolved decisions. For
   implementation, review the actual diff and affected call paths against the durable issue.
3. Lead with actionable findings ordered by severity. Cite issue headings, paths/lines, commits, or
   diff locations. Distinguish fact, inference, unanswered question, and residual risk.
4. Recommend `update` or implementation follow-up when appropriate, but persist nothing.
