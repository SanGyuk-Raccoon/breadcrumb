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

### One Pull-Request Outcome

- Require one result that can be implemented, verified, reviewed, and delivered coherently in one
  pull request.
- Recommend a split only for independently implementable, verifiable, deployable, or reviewable
  outcomes. File count and elapsed-time estimates are not split criteria.
- Keep changes together when separate delivery would break compatibility, migration safety,
  rollback, or atomic verification. Obtain approval before creating more than one issue.

## Readiness Conclusion

- `backlog`: durable capture only; planning has not started.
- `in-progress`: refinement is active and at least one concrete Todo remains unresolved.
- `complete`: every quality check passes, no unresolved decision is hidden outside Todo, Todo has no
  unresolved item, the outcome is one cohesive PR, and the complete ADR planning gate has passed.

Record failures as actionable Todo or review findings. Never select `complete` merely because the
headings exist, the prose is long, or the Todo list is empty.
