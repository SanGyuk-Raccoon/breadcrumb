# Work-Issue Planning Operations

Use one issue for one cohesive pull-request outcome. Conversation is temporary source material;
material requirements, decisions, progress, and planning state belong in the issue.

## Open

1. Inspect available repository evidence, then extract Background, Goal, Requirements, Design,
   Verification, and Todo. Distinguish fact, inference, user requirement, and uncertainty.
2. Apply the shared planning quality gate before detailed refinement. Ask one focused highest-impact
   question only when its answer materially changes scope or acceptance. Otherwise record the
   uncertainty as a concrete unchecked Todo with an increasing stable `T<number>` identifier.
3. Add a same-ID Decision Brief for every decision-bearing unresolved Todo using the contract in
   `artifacts.md`. Do not invent alternatives; state when only one option is viable or evidence does
   not support a recommendation.
4. Evaluate one-PR scope before detailed refinement and after every scope-changing answer. Split
   only for independently implementable, verifiable, deployable, or reviewable outcomes, never by
   file count or elapsed-time estimate. Show proposed leaf issues and ask before creating more than
   one.
5. Re-run the shared gate after refinement. Choose Status from the recorded evidence: a capture is
   `backlog`; active refinement with unresolved Todo is `in-progress`; `complete` requires every
   quality check, zero unresolved Todo, one cohesive PR outcome, and the ADR planning gate.
6. Render with `render_work_issue.py`. When issue creation was explicitly requested, that authorizes
   one ordinary POST. Otherwise show exact title, body, and label and wait.
7. Immediately before POST, revalidate repository identity, Issues capability, exact `breadcrumb`
   label, title, and rendered body. Send only structured `title`, `body`, and
   `labels: ["breadcrumb"]` once.
8. Verify returned positive number, URL, title, body, and exact label. If a strong number is returned
   but the response is incomplete, GET it once. Never replay a create blindly. Select the confirmed
   issue for this conversation but do not start another workflow without authorization.

For a new plan that cannot complete its ADR gate until a real issue number exists, create one
`in-progress` issue with a concrete planning-gate Todo, then complete it through `update` after the
digest-bound finder succeeds.

## Update

1. Require one open issue. Immediately load it with
   `inspect_work_issue.py <number> --comments incremental` unless full history was requested. Fetch
   the direct issue body and match its UTF-8 SHA-256. Preserve unchanged narrative and unrelated
   labels; use at most one body PATCH for an ordinary update.
2. Review ordinary comments in `(created_at, id)` order. Advance `Applied Through` only across a
   contiguous prefix whose items are reflected, explicitly rejected, or recorded irrelevant. Stop
   before the first unresolved/unreviewed item even when a later comment is actionable. Preserve
   each prefix item's ID, URL, timestamps, exact body, and parser-provided `prefix_sha256` for final
   revalidation.
3. Reflect a completed Todo conclusion and source URL in the relevant narrative, preserve its
   Decision Brief, add final Decision/rationale, then check it. Give new or rewritten Todo stable
   unused IDs and required Decision Briefs. Append newly discovered work instead of pretending the
   original list was final.
4. Re-run the shared planning quality gate against the proposed complete body. Every changed
   requirement or design decision must update affected design, verification, uncertainty, and
   planning evidence; unresolved findings become new Todo rather than hidden prose.
5. Reassess one-PR scope. Recommend a split when independent outcomes emerged, explain boundaries,
   and stop before creating another issue without separate `open` approval.
6. Keep Status/Todo consistent. Before transition to `complete`, apply `adr.md` and persist Planning
   Base, Planned Change Scope, digest-bound complete finder result, final disposition, and complete
   planned ADR drafts or lifecycle edits. Show and confirm a normalized full-body replacement before
   repairing malformed schema 1; never overwrite a future schema.
7. Run the shared gate once more after the ADR result is recorded. Render the full final body with
   `render_work_issue.py` and PATCH it once after revalidation.

## Coordinated Stale Transition

For `complete -> in-progress` when implementation already exists:

1. Show the exact final body, stale comment, and affected open PR; obtain confirmation.
2. Convert a linked open non-draft PR to draft first with `gh pr ready <number> --undo`, then verify.
3. PATCH the body with a concrete unresolved Todo and `in-progress`.
4. Render and POST one `render_stale_comment.py` result referencing the latest implementation.
5. Inspect the final projection.

Stop before body mutation if draft conversion fails. If the body succeeds but stale comment fails,
preserve the body and report partial completion; the projection still infers stale from
`in-progress`.

## Record The Update Checkpoint

After the final body PATCH or a verified no-op and any stale comment:

1. GET the issue and require the exact final body. Compute its UTF-8 SHA-256.
2. Choose the final source in the reviewed contiguous ordinary-comment prefix. Copy its current
   `prefix_sha256`; use `none` with `empty_prefix_sha256` only when no ordinary comment exists.
3. Summarize applied, rejected, and irrelevant inputs without copying unnecessary comment content.
   Render `render_update_comment.py`.
4. Immediately revalidate repository, issue, body hash, each reviewed prefix item's ID, URL,
   timestamps, body, rolling digest, selected source, and comment-write capability. Rerun inspect and
   require the selected current digest.
5. Reuse an existing trusted marker with the same body hash, boundary, and prefix digest. Otherwise
   POST exactly one structured comment and verify positive ID, URL, exact body, target, and trusted
   provenance.

When neither body nor reviewed boundary changes, report a no-op and post no marker. If body PATCH
succeeds but marker creation fails or is uncertain, preserve it, do not retry blindly, and leave the
older checkpoint so a later load repeats rather than skips input.
