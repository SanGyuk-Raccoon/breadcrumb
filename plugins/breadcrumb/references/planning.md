# Shared Work-Issue Planning Quality Gate

Apply this semantic gate whenever `issue` opens or updates a plan and whenever `read` reviews one.
It complements the deterministic artifact parser and the ADR completion gate; it does not replace
either one. A structurally valid body is not necessarily implementation-ready.

## Build The Plan From Evidence

1. Inspect the available repository behavior, affected paths, tests, verification guidance, and
   relevant durable decisions before finalizing the plan. Distinguish observed fact, inference,
   user requirement, and unresolved uncertainty.
2. Draft Background, Goal, Requirements, Design, Verification, and Todo from that evidence. Do not
   restate a requested solution as proof of the current problem or invent repository behavior.
3. Run the quality checks below. When one answer materially changes scope or acceptance, ask one
   focused highest-impact question. Otherwise turn the uncertainty into a concrete unchecked
   `T<number>: Decision:` Todo with the required Decision Brief. Use `T<number>: Action:` for a
   procedural planning step whose execution, rather than its answer, closes the item.
4. Re-run the gate after every material answer, comment conclusion, scope change, or design change.
   Keep the issue `in-progress` until every blocking finding is resolved and recorded durably.

## Quality Checks

### Background

- State the current problem, who or what it affects, and the evidence that establishes it.
- Separate confirmed behavior from inference and name material unknowns.
- Explain why the change is needed without assuming the proposed implementation is correct.

### Goal And Scope

- Describe an observable outcome rather than an activity or file edit.
- State material included and excluded behavior so completion does not silently expand scope.
- Keep the goal compatible with one cohesive pull-request outcome.

### Requirements

- Make requirements complete, testable, and non-conflicting.
- Cover normal behavior and every relevant failure, compatibility, security, recovery, and
  externally visible invariant; mark a category not applicable only when the reason is evident.
- Preserve user constraints and existing durable decisions. Do not silently turn a recommendation
  into a requirement.

### Design

- Name the affected components, paths or useful path scopes, interfaces, resources, and state
  transitions with enough detail that implementation does not need to invent material behavior.
- Define failure handling, recovery boundaries, and migration or rollback behavior when applicable.
- Identify dependencies and explain why the selected design satisfies the requirements and existing
  ADR constraints.

### Verification

- Map every observable requirement and material design boundary to evidence that can prove it.
- Include applicable positive, negative, failure, compatibility, and regression checks.
- Name manual or external evidence honestly; an unavailable applicable check keeps verification or
  implementation pending rather than being treated as passed.
- Prefer observable behavior and attributable commands over generic statements such as "run tests."

### Todo And Decisions

- Put every unresolved decision that can change scope, acceptance, design, verification, or ADR
  disposition in Todo; do not hide it in narrative prose.
- Give every new or rewritten Todo the explicit `Decision:` or `Action:` kind after its stable ID.
  Preserve legacy and completed wording unless its meaning genuinely changes.
- Give every decision-bearing unresolved Todo a same-ID Decision Brief with real options,
  tradeoffs, recommendation, uncertainty, and a reply example.
- Preserve resolved decisions, rationale, and provenance. Do not erase meaningful planning history.

### One Pull-Request Outcome And Decomposition

- Reassess one-PR scope before detailed refinement and after every material goal, requirement,
  design, verification, or rollout change.
- Require one result that can be implemented, verified, reviewed, and delivered coherently in one
  pull request. Keep schema and consumer changes, migrations and compatibility code, or other work
  together when separate delivery would break safety, rollback, or atomic verification.
- Recommend a split only when every leaf is independently implementable and verifiable. Use an
  independent deployment or review boundary as additional evidence for the split, never as a reason
  to separate work that would become unsafe or unverifiable. File count and elapsed-time estimates
  are not split criteria.
- Before any multi-issue write, show each proposed leaf with all of these fields:
  - `Title`: concise issue title.
  - `Outcome`: independently observable result.
  - `Scope` and `Out of Scope`: explicit delivery boundary.
  - `Completion Conditions` and `Verification`: what must hold and how it will be proven.
  - `Predecessors` and `Blockers`: required earlier outcomes and external impediments; use `none`
    explicitly when absent.
  - `Parallelizable With`: leaves that can safely proceed concurrently, or `none`.
  - `Delivery Order` and `Rollout Effect`: merge/deployment position and user or system effect.
- Draw predecessor edges from earlier to later leaves and assign dependency waves by repeatedly
  selecting leaves whose predecessors are all in earlier waves. Leaves in one wave may proceed in
  parallel only when they have no dependency edge or unsafe shared implementation or verification
  boundary. A delivery-only migration, compatibility, or rollout sequence does not separate the
  implementation wave; record it under `Delivery Order` instead.
- Use a predecessor edge only when the successor cannot be implemented or verified before the
  earlier outcome exists. Record a merge- or deployment-only constraint under `Delivery Order`
  instead; add an edge only when that constraint also blocks implementation or verification.
- Show the wave sequence in compact notation such as `A -> (B || C) -> D` and explain any merge or
  deployment order that differs from implementation order. Dependency order does not imply product
  priority.
- Reject the proposal before publication when a leaf depends on itself, a cycle exists, a claimed
  parallel pair has a dependency edge, a predecessor appears in a later wave, or scope boundaries
  contradict completion or rollout conditions. Name the conflicting leaves and the edge or boundary
  that must change.
- Show the exact initial issue payloads, complete dependency graph, and planned follow-up link fields,
  then obtain explicit approval for the complete creation set. A partial approval authorizes no
  write until the approved subset is replanned as a predecessor-complete DAG and previewed again.
  After GitHub assigns numbers, show and separately approve the exact dependency-link body patches.
  Neither approval authorizes edits to pre-existing or otherwise related issues.

## Update Change-Impact Reassessment

For every ordinary issue update, compare the exact inspected current body with one proposed final
body before rendering or writing it. Compare semantic planning content, not only text or checkbox
differences, and evaluate every changed row below. A mandatory reassessment can conclude that the
dependent content remains correct; it does not require a cosmetic rewrite.

| Changed planning input | Mandatory downstream reassessment |
|---|---|
| Background | Scope, acceptance, design assumptions, and verification. Classify it as non-material only when all four remain unchanged; otherwise continue with every affected row below. |
| Goal | Included and excluded scope, one-PR cohesion, decomposition, requirements, design, verification, Todo, Planned Change Scope, ADR input/disposition, dependency waves, delivery order, and rollout effect. |
| Requirements | Design and its normal, failure, compatibility, security, recovery, migration, and rollback behavior; verification coverage; Todo; one-PR scope; Planned Change Scope; and ADR input/disposition. |
| Design | Requirement consistency, interfaces and state transitions, failure/recovery and migration/rollback behavior, verification coverage, Todo, Planned Change Scope, and ADR input/disposition. |
| Verification | Coverage of every observable requirement and design boundary, applicable negative/failure/compatibility evidence, unresolved Todo, and readiness. |
| Todo or a recorded decision | The narrative section that owns the conclusion, rationale and provenance, plus every downstream row affected by the decision's meaning, ADR disposition, and readiness. |
| Planned Change Scope, ADR input, disposition, or draft | Actual components, paths, resources, behaviors and long-lived decisions; one-PR cohesion; verification; and the complete ADR planning gate. |
| Dependencies, waves, or Delivery Order | Every leaf boundary, predecessor, blocker, parallel claim, delivery constraint, and rollout effect; recompute the complete acyclic wave sequence and identify affected related issues. |

Follow reassessment transitively: when a mandatory check changes another planning input, evaluate
that row too, repeating until no newly affected input remains. Then choose one primary classification
using this precedence while still recording all affected rows:

1. `implementation-stale change`: a current implementation exists and may no longer satisfy the
   materially changed plan. Treat every material post-implementation change as a stale candidate;
   classify it lower only when current implementation evidence proves it remains unaffected and the
   conclusion records why.
2. `dependency replan`: dependency edges, waves, Delivery Order, or rollout sequencing changed and
   the implementation is not stale.
3. `material replan`: another semantic Goal, Requirements, Design, Verification, Todo, Planned
   Change Scope, ADR input, disposition, or draft changed.
4. `non-material clarification`: wording or Background context changed without changing scope,
   acceptance, assumptions, downstream planning, or implementation validity.

For a material or dependency replan, rerun the applicable quality, one-PR/decomposition, and
complete ADR planning gates before retaining or restoring `complete`. For an implementation-stale
change, stop the ordinary update before mutation and use the confirmed coordinated stale transition;
classification alone never changes implementation or pull-request state. Record ADR impact and an
unresolved Todo in the stale `in-progress` plan, then repeat the complete ADR gate before a later
return to `complete`. A dependency replan recomputes the whole graph but never silently patches
related issues: show each exact proposed follow-up and require its own authorized selected-issue
update.

Record the comparison body SHA-256, changed inputs, primary classification, affected checks and
their conclusions, related-issue effect, implementation/pull-request effect, and repeated ADR result
when applicable. Put the concise record in the issue narrative or update checkpoint without adding
control metadata or copying raw comments. Preserve the existing contiguous comment prefix, single
body PATCH, concurrency revalidation, and partial-result boundaries.

## Behavioral Regression Coverage

When a pull request changes issue-open or issue-update planning behavior, update deterministic tests
and at least one applicable rule or scenario in `plugins/breadcrumb/evals/scenarios.json` in the same
pull request. Validate the complete catalog with `validate_planning_evals.py` and replay affected
scenarios through `plugins/breadcrumb/evals/README.md` when the change relies on semantic agent
judgment.

Keep deterministic guarantees, host-assisted replay evidence, and residual reviewer judgment
separate. Scenario expectations cover public outputs and action boundaries only; they do not make
generated wording canonical, expose hidden reasoning, authorize live writes, or replace the shared
planning and ADR gates.

## Readiness Conclusion

- `backlog`: durable capture only; planning has not started.
- `in-progress`: refinement is active and at least one concrete Todo remains unresolved.
- `complete`: every quality check passes, no unresolved decision is hidden outside Todo, Todo has no
  unresolved item, the outcome is one cohesive PR, and the complete ADR planning gate has passed.

Record failures as actionable Todo or review findings. Never select `complete` merely because the
headings exist, the prose is long, or the Todo list is empty.
