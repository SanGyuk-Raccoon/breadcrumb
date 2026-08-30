# Work-Issue Planning Operations

Use one issue for one cohesive pull-request outcome. Conversation is temporary source material;
material requirements, decisions, progress, and planning state belong in the issue.

## Open

1. Inspect available repository evidence, then extract Background, Goal, Requirements, Design,
   Verification, and Todo. Distinguish fact, inference, user requirement, and uncertainty.
2. Apply the shared planning quality gate before detailed refinement. Ask one focused highest-impact
   question only when its answer materially changes scope or acceptance. Otherwise record the
   uncertainty as a concrete unchecked Todo with an increasing stable `T<number>` identifier. An
   investigation that only gathers evidence is an `Action`, but when its result will select among
   materially different remedies, also record that downstream choice now as a separate `Decision`
   Todo with its Decision Brief; do not hide the unresolved choice behind the investigation.
3. Add a same-ID Decision Brief for every decision-bearing unresolved Todo using the contract in
   `artifacts.md`. Do not invent alternatives; state when only one option is viable or evidence does
   not support a recommendation.
4. Evaluate one-PR scope before detailed refinement and after every material scope-changing answer.
   Keep coupled migration, compatibility, rollout, and atomic-verification work together. When a
   split is warranted, apply the leaf-proposal and dependency-wave contract in `planning.md`: show
   every boundary and completion condition, reject cycles or contradictions, distinguish
   implementation from delivery order, and ask for explicit approval of the complete creation set
   before creating more than one issue.
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

## Approved Multi-Issue Creation

Treat decomposition as a series of individually verified writes, not a cross-issue transaction:

1. Before mutation, show the exact initial rendered payload for every leaf, the acyclic wave
   sequence, and the narrative fields that will later receive durable GitHub issue links. A leaf
   whose ADR gate requires its assigned number remains `in-progress` in this initial payload. Obtain
   explicit approval for the complete creation set. A partial approval authorizes no write until the
   requested subset is replanned as a predecessor-complete DAG and previewed again.
2. Immediately revalidate all payloads and repository permissions. Create leaves in dependency-wave
   order, using a stable temporary leaf key to correlate returned issue numbers. Verify each strong
   response before continuing. If a response is ambiguous or a write fails, stop without replaying,
   deleting, or attempting later-wave writes; report the confirmed partial result.
3. After every approved leaf has a confirmed number and URL, finish any required per-leaf planning
   gate and render each exact proposed final body. Under `Design`, use a
   `### Dependencies and Delivery Order` subsection to link predecessors, successors, and
   parallelizable peers and record the wave, delivery order, and rollout effect. These links are
   narrative planning data, never Breadcrumb Status fields. Show every exact body replacement and
   obtain a separate approval for the complete PATCH set.
4. Revalidate each newly created leaf's current body immediately before its approved PATCH, apply at
   most one PATCH per leaf, and verify the exact final body and links. Never patch a pre-existing
   dependency or related issue in this transaction; propose that work as a separate selected-issue
   update. If link-patch approval is declined or unavailable, preserve the created issues and report
   the missing durable links as a partial result.
5. Report all created and patched issue URLs, the final wave sequence, and any partial failure. Keep
   only one issue selected for subsequent work and do not begin implementation implicitly.

## Update

1. Require one open issue. Immediately load it with
   `inspect_work_issue.py <number> --comments incremental` unless full history was requested. Fetch
   the direct issue body and match its UTF-8 SHA-256. Preserve unchanged narrative and unrelated
   labels; use at most one body PATCH for an ordinary update.
2. Review ordinary comments in `(created_at, id)` order. Advance `Applied Through` only across a
   contiguous prefix whose items are reflected, explicitly rejected, or recorded irrelevant. Stop
   before the first unresolved/unreviewed item even when a later comment is actionable. Preserve
   each prefix item's ID, URL, timestamps, exact body, and parser-provided `prefix_sha256` for final
   revalidation. Mutually exclusive requests remain unresolved unless public evidence explicitly
   accepts or rejects one. Merely listing both as open Decision options does not reflect either
   request: stop before the earliest item in that conflict, do not patch the body to record it, and
   do not advance a checkpoint across it.
3. Reflect a completed Todo conclusion and source URL in the relevant narrative, preserve its
   Decision Brief, add final Decision/rationale, then check it. Give new or rewritten Todo stable
   unused IDs and required Decision Briefs. Append newly discovered work instead of pretending the
   original list was final.
4. Compare the exact inspected body with the proposed complete body and apply the transitive update
   change-impact matrix in `planning.md`. Record changed inputs, the primary classification,
   affected checks and conclusions, related-issue effect, and implementation/pull-request effect.
   Any predecessor, blocker, parallelization, delivery-order, or rollout input change is a
   `dependency replan` even when product requirements otherwise stay unchanged: recompute the whole
   dependency graph, acyclic waves, distinct delivery order, and rollout claims before any write.
   A Background-only edit is non-material only after its scope, acceptance, assumptions, and
   verification checks remain unchanged. If a current implementation may be invalidated, stop
   before the ordinary PATCH and prepare the confirmed Coordinated Stale Transition below.
5. Re-run the shared planning quality gate against the proposed complete body. Every materially
   affected requirement or design decision must update design, verification, uncertainty, Todo,
   planning evidence, and ADR input as required by the matrix; unresolved findings become new Todo
   rather than hidden prose.
6. Reassess one-PR scope. When independent outcomes emerged, produce the complete leaf proposal,
   validate its dependency waves, and stop before any additional creation or newly-created-leaf
   PATCH unless the user explicitly approves the applicable creation or newly-created-leaf PATCH
   set under Approved Multi-Issue Creation.
7. Keep Status/Todo consistent. A material or dependency replan must repeat `adr.md` before retaining
   or restoring `complete` and persist the current Planning Base, Planned Change Scope, digest-bound
   complete finder result, final disposition, and complete planned ADR drafts or lifecycle edits.
   Show and confirm a normalized full-body replacement before repairing malformed schema 1; never
   overwrite a future schema.
8. Run the shared gate and impact reassessment once more after the ADR result is recorded. Render the
   full final body with `render_work_issue.py`. Immediately before PATCH, repeat the direct body
   SHA-256 and inspected comment-prefix checks against the original snapshot; any body, source
   comment, timestamp, or rolling-digest mismatch stops before a write. Then PATCH the body once.

## Coordinated Stale Transition

For `complete -> in-progress` when implementation already exists:

The public preview and action summary must expose the two body/comment-prefix checks below as
separate mutation boundaries. Do not collapse the pre-first-mutation check and the post-draft,
pre-body-PATCH check into generic revalidation, and state that a verified draft conversion survives
a failure at the second boundary.

1. Show the exact final body, stale comment, and affected open PR; obtain confirmation.
2. Immediately before the first mutation, repeat the direct body SHA-256 and inspected reviewed
   comment-prefix checks against the confirmed snapshot. Stop without a write on any mismatch.
3. Convert a linked open non-draft PR to draft first with `gh pr ready <number> --undo`, then verify.
4. Immediately before the body PATCH, repeat both snapshot checks. On mismatch, preserve and report
   the verified draft conversion as a partial result, then stop without changing the issue body.
5. PATCH the body with a concrete unresolved Todo and `in-progress`.
6. Render and POST one `render_stale_comment.py` result referencing the latest implementation.
7. Inspect the final projection.

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
