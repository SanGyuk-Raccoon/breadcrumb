# ADR: Represent work-issue delivery order as dependency waves

- Schema Version: 1
- Status: accepted
- Work Issue: #38
- Supersedes: none
- Superseded By: none

## Summary

Represent an approved multi-issue plan as independently verifiable leaf issues plus an acyclic sequence of dependency waves.

## Context

Breadcrumb defines one cohesive pull-request outcome per work issue and already asks before creating more than one issue. A split proposal currently lacks a durable contract for predecessor relationships, parallel work, and merge or rollout order. New control metadata would expand the fixed work-issue schema and duplicate the issue skill's planning responsibility.

## Affected Areas

- Components: Breadcrumb issue planning
- Paths: plugins/breadcrumb/references/planning.md, plugins/breadcrumb/references/issue.md, plugins/breadcrumb/skills/issue/**
- Resources: GitHub work issues
- Behaviors: scope decomposition, dependency ordering, delivery sequencing

## Decision

When one requested outcome must be split, the issue skill proposes independently implementable and verifiable leaf issues and records their predecessor relationships as an acyclic sequence of human-readable dependency waves in the issue narrative. Each leaf states its outcome, included and excluded scope, verification, blockers, parallelization, and delivery order. Creating multiple issues still requires explicit approval, and the workflow does not add control metadata or silently patch related issues.

## Consequences

Users receive an executable delivery sequence in addition to PR-sized issue boundaries. Planning can distinguish implementation order from merge or rollout order and can identify safe parallel work. Dependency validity remains an agent-level planning responsibility rather than a new machine control schema, so behavioral scenarios must cover cycles, coupled work, and authorization boundaries.

## Review Triggers

Review this decision if GitHub provides a durable dependency primitive that Breadcrumb can validate without broadening mutation authority, if dependency waves require machine-enforced control state, or if one-issue-per-PR delivery is replaced.
