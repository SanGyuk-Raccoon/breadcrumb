# ADR: Use operation-scoped skills and scripts

- Schema Version: 1
- Status: accepted
- Work Issue: #29
- Supersedes: none
- Superseded By: none

## Summary

Keep Breadcrumb as the plugin namespace while exposing operation-scoped skills and single-purpose public scripts.

## Context

The umbrella `breadcrumb` skill mixes initialization, read-only inspection, issue mutation, ADR changes, code implementation, pull-request publication, and review. Its public projection script also selects unrelated operations through subcommands. These boundaries make trigger descriptions, relevant context, write authority, and failure recovery harder to review independently. Repeating `breadcrumb` in both the plugin namespace and skill name adds no useful distinction.

## Affected Areas

- Components: Breadcrumb plugin skills, read-only projections, artifact renderers
- Paths: plugins/breadcrumb/skills/**, plugins/breadcrumb/references/**, plugins/breadcrumb/scripts/**, plugins/breadcrumb/.codex-plugin/plugin.json, README.md
- Resources: GitHub work issues, repository-local ADR corpus, Git branches and pull requests
- Behaviors: skill selection, planning updates, ADR-only and code implementation handoff, pull-request publication, product feedback reporting

## Decision

Expose seven skills named `init`, `read`, `issue`, `adr`, `implement`, `pr`, and `report` inside the `breadcrumb` plugin. Do not expose an umbrella `breadcrumb` skill or a generic `execute` skill. Each skill owns one user intent and declares its mutation boundary; shared rules remain common references that each skill loads only when needed.

Split public projections into list, inspect, and ADR entrypoints, and split artifact rendering by output type. A public script performs one operation and has no write side effects. Shared argument validation, parsing, projection, and rendering primitives remain reusable internal modules.

Treat a verified implementation comment as the durable handoff from `adr` or `implement` to `pr`. The `adr` skill owns ADR-only repository changes, while `implement` owns code and any planned ADR that must ship with that code. The `pr` skill consumes the recorded branch and commit without modifying code or pushing another commit.

## Consequences

Skill selection loads less irrelevant context and exposes write authority and recovery boundaries more clearly. Shared internal modules and fixed artifact schemas prevent duplicated implementation even though public entrypoints are separate. The skill split documents intended authority but does not itself create an operating-system or GitHub ACL.

The user-facing skill names and public CLI entrypoints change, so the plugin minor version and documentation must identify the new surface. More skill and renderer files must remain consistent with common contracts and validation.

## Review Triggers

Review this decision if the host no longer namespaces plugin skills, if independent skills repeatedly need the same mutation authority, if the implementation-comment handoff changes, or if a single-purpose public script cannot preserve the fixed artifact contracts without unsafe duplication.
