# Repository And Work-Issue Operations

Apply the shared rules in `SKILL.md` and the exact contracts in `artifacts.md`.

## Contents

- [Initialize Or Audit](#initialize-or-audit)
- [Open](#open)
- [List](#list)
- [Load](#load)
- [Update](#update)
- [Review](#review)
- [Migrate Legacy Open Issues](#migrate-legacy-open-issues)

## Initialize Or Audit

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
5. Remove neither legacy config/templates nor labels during an ordinary audit. Handle those only in
   the confirmed migration flow below.
6. Report readiness by operation rather than one global boolean: issue reads, issue writes,
   implementation fetch/push, verification, and PR writes.

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

## Migrate Legacy Open Issues

Run migration only when explicitly requested and confirmed as a bulk operation.

1. Fully list issues carrying `breadcrumb:backlog`, `breadcrumb:requirement`, or
   `breadcrumb:design`. Select only GitHub-open issues. Leave every closed issue untouched.
2. When one open requirement and one open design form a valid pair, choose one canonical work issue,
   combine all material Background through Design and Todo context, apply the new body and
   `breadcrumb` label, and close or relabel the redundant open issue only as shown in the approved
   migration plan. Never infer a pair from titles alone.
3. Convert an unpaired open legacy issue in place when its meaning is unambiguous. Show every final
   title, body, label set, and close action before the first mutation. Stop and report partial
   progress on uncertainty; never retry creates or patches blindly.
4. Requery until no open legacy issue remains. Ask separately before deleting the three legacy
   labels. Deleting labels must not modify closed issue bodies; GitHub will only remove the deleted
   label metadata from historical issues.
