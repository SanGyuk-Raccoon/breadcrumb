# ADR: Reassess downstream planning impact before issue updates

- Schema Version: 1
- Status: accepted
- Work Issue: #40
- Supersedes: none
- Superseded By: none

## Summary

Before patching a work issue, classify the proposed change and transitively reassess every affected downstream planning state.

## Context

Issue updates currently preserve comment provenance and use a single body PATCH, but they do not require a systematic comparison from changed upstream planning sections to every dependent section. A local edit can therefore leave verification, dependency order, ADR scope, or implementation readiness stale. The issue operation owns planning changes, while repository ADRs, implementation branches, and pull requests retain separate mutation boundaries.

## Affected Areas

- Components: Breadcrumb issue update planning
- Paths: plugins/breadcrumb/references/planning.md, plugins/breadcrumb/references/issue.md, plugins/breadcrumb/skills/issue/**
- Resources: GitHub work issues, issue comments, implementation comments, linked pull requests
- Behaviors: change-impact classification, downstream reassessment, dependency replanning, implementation staleness, update checkpointing

## Decision

Before an ordinary issue-body PATCH, the issue update workflow compares the exact verified current body with one proposed final body and computes the transitive downstream impact through a normative matrix. It assigns one primary classification in this precedence: implementation-stale change when a current implementation may no longer satisfy materially changed planning; dependency replan when dependency edges, waves, or delivery order change; material replan for another semantic Goal, Requirements, Design, Verification, Todo, Planned Change Scope, or ADR change; otherwise non-material clarification. The classification itself does not mutate implementation or PR state. Material changes repeat applicable planning and ADR gates, dependency changes recompute the complete acyclic wave narrative without silently patching related issues, and stale candidates use the existing confirmed stale transition. Record the conclusion and affected sections in issue narrative or the update checkpoint, then retain one final body PATCH and one checkpoint transaction without new control metadata.

## Consequences

Updates become more deliberate and can require additional replanning before a write, but downstream requirements, verification, dependency order, ADR evidence, and implementation state remain coherent. The matrix guides agent reasoning rather than creating a second machine schema, so behavioral forward-tests remain necessary. Existing confirmation, concurrency, partial-result, implementation-comment, and pull-request boundaries remain unchanged.

## Review Triggers

Review this decision if impact classification becomes machine control metadata, deterministic tooling can safely derive semantic downstream effects, issue updates move to another operation, or recurring update classes are not represented by the matrix.
