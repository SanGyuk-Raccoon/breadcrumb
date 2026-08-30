# ADR: Use repository-owned public-outcome scenarios for planning skills

- Schema Version: 1
- Status: accepted
- Work Issue: #41
- Supersedes: none
- Superseded By: none

## Summary

Evaluate issue-planning skills with version-controlled scenarios and assertions over public outcomes rather than hidden model traces or live repository writes.

## Context

Deterministic unit tests validate Breadcrumb artifacts and transport boundaries but cannot show that a planning skill chooses the intended status, decomposition, authorization, or stale-transition behavior for realistic prompts. Host internals and model traces are not stable public contracts, and a live GitHub evaluation would add credentials and mutation risk.

## Affected Areas

- Components: Breadcrumb planning evaluation
- Paths: plugins/breadcrumb/evals/**, plugins/breadcrumb/scripts/validate_planning_evals.py, plugins/breadcrumb/scripts/internal/evals.py, plugins/breadcrumb/scripts/tests/**, plugins/breadcrumb/skills/issue/SKILL.md, plugins/breadcrumb/references/planning.md, plugins/breadcrumb/references/issue.md, README.md
- Resources: planning scenario fixtures, public outcome summaries
- Behaviors: issue-open regression evaluation, issue-update regression evaluation, stable operation selection, authorization checks, no-write evaluation, critical dependency and stale-transition boundaries

## Decision

Keep declarative prompts, initial durable state, rule coverage, allowed mutations, required public outcomes, forbidden behavior, and evidence assertions as canonical version-controlled evaluation fixtures. Keep replay-proven high-risk operation-selection and no-write boundaries visible in the issue skill entry point as well as in the routed references. Give a replaying evaluator only the prompt, initial state, installed skills, and minimum public artifacts; withhold expected outcomes until scoring. Validate fixture and public-result shape with a side-effect-free standard-library entrypoint that reports structural validity separately from behavioral pass or failure. Replay scenarios only through a documented clean host procedure that defaults to no live writes and does not depend on credentials, hidden reasoning traces, or an OpenAI API. Treat actual replay captures as generated evidence, not as long-term decision authority or canonical fixtures.

## Consequences

Planning behavior gains reproducible regression coverage while deterministic tests remain distinct from model-assisted evidence and residual semantic judgment. Results can compare visible artifacts and actions across versions without coupling the repository to one model or host implementation. Replay still requires an explicit supported host procedure and human review of semantic evidence; structural validation cannot prove prose quality.

## Review Triggers

Review this decision if Codex provides a stable first-party skill evaluation protocol with public action traces, if replay can be safely isolated with deterministic model behavior, or if tracked generated captures become necessary for release governance.
