# Breadcrumb

Breadcrumb is a GitHub issue based workflow for durable AI-assisted development. One cohesive pull
request is planned, implemented, verified, and delivered through one work issue, while chat remains
temporary working context. Optional repository-local ADRs keep long-lived decisions beside the code
that implements them.

## Workflow

```text
init ── repository ready

issue ── complete plan
  ├─ ADR-only change ──> adr ────────> implementation comment ──> pr
  └─ code ± planned ADR ─> implement ─> implementation comment ──> pr

read ── read-only at every stage
report ── isolated product feedback to the fixed Breadcrumb upstream
```

Issue planning state is:

```text
backlog -> in-progress -> complete
```

- `backlog` means planning has not started.
- `in-progress` means requirements/design are being refined and at least one Todo is unresolved.
- `complete` means implementation-ready and no Todo is unresolved.
- A merged closing PR completes delivery and closes the issue. Body Status remains `complete`.

Meaningful completed Todo remains checked as durable decision history. New or rewritten Todo uses a
stable `T<number>: Decision:` or `T<number>: Action:` prefix. Every unresolved Decision has a
matching Decision Brief with Why, Options, Recommendation, Uncertainty, and Reply example fields.
Requirement/design changes after an implementation mark it stale and return the issue to
`in-progress`.

Issue open, issue update, and read-only planning review use one shared planning quality gate. Before
`complete`, the plan must establish the current problem from evidence, define an observable goal and
material exclusions, cover normal and relevant failure or compatibility requirements, provide a
technically sufficient design with recovery boundaries, map observable requirements to verification,
expose every unresolved decision in Todo, and produce one cohesive pull-request outcome. Fixed
headings and an empty Todo list alone never prove implementation readiness.

When a requested outcome cannot safely fit one PR, issue planning proposes independently
implementable and verifiable leaf issues before creating them. Each proposal includes boundaries,
completion and verification, predecessors and blockers, safe parallel work, delivery order, and
rollout effect. An acyclic wave sequence such as `A -> (B || C) -> D` makes implementation order
explicit without adding control metadata or treating dependency order as priority. The complete
creation set and, after GitHub assigns issue numbers, the exact dependency-link patches require
separate previewed approvals; pre-existing related issues are never edited implicitly.

Every issue update compares the exact current and proposed bodies and transitively reassesses the
planning sections affected by each semantic change. It classifies the result as a non-material
clarification, material replan, dependency replan, or implementation-stale change; material changes
repeat the applicable planning and ADR gates, while stale candidates retain the confirmed PR-draft
boundary. The conclusion is recorded without new control metadata or implicit related-issue writes.

## Skills

The plugin exposes seven focused skills. `breadcrumb` is the plugin namespace, so the skill names do
not repeat a `breadcrumb-` prefix:

| Skill | Responsibility | Mutation boundary |
|---|---|---|
| `init` | Initialize, audit, repair, and migrate a repository | Confirmed setup/migration only |
| `read` | List, load, and review issues, ADRs, implementations, and PR state | None |
| `issue` | Create and refine work-issue planning state | Issue body/comments; confirmed stale PR draft exception |
| `adr` | Implement an ADR-only complete issue | Planned ADR files, commit, push, implementation comment |
| `implement` | Implement code/tests and any ADR that ships with them | Scoped files, commit, push, implementation comment |
| `pr` | Create or reuse the PR for a current implementation | Matching PR only |
| `report` | Submit privacy-minimized Breadcrumb product feedback | One approved fixed-upstream issue/comment |

There is no umbrella `breadcrumb` skill and no generic `execute` skill. Each skill owns one user
intent, loads only its relevant references, and stops at a durable handoff. Shared scripts are called
directly; one skill does not invoke another as its implementation mechanism.

The separation makes intended authority reviewable but is not an operating-system or GitHub ACL.
Actual access remains controlled by the host, sandbox, approvals, GitHub authentication, and
repository permissions.

## Script Boundaries

Public read-only scripts each provide one operation:

```bash
python3.12 plugins/breadcrumb/scripts/list_work_issues.py \
  --gh-executable /absolute/path/to/gh
python3.12 plugins/breadcrumb/scripts/list_work_issues.py \
  --gh-executable /absolute/path/to/gh --status in-progress --include-closed

python3.12 plugins/breadcrumb/scripts/inspect_work_issue.py 29 \
  --gh-executable /absolute/path/to/gh --comments incremental
python3.12 plugins/breadcrumb/scripts/inspect_work_issue.py 29 \
  --gh-executable /absolute/path/to/gh --comments all

python3.12 plugins/breadcrumb/scripts/project_adrs.py --compact
python3.12 plugins/breadcrumb/scripts/project_adrs.py --compact --base origin/main
python3.12 plugins/breadcrumb/scripts/project_adrs.py \
  --base <commit> --finder-input-json '<compact-json>'

python3.12 plugins/breadcrumb/scripts/validate_planning_evals.py
python3.12 plugins/breadcrumb/scripts/validate_planning_evals.py \
  --result /tmp/breadcrumb-evals/public-result.json
```

The former operation-dispatching `breadcrumb.py` entrypoint is intentionally removed. Common GitHub
transport, parsing, projection, error handling, and ADR validation remain shared under
`scripts/internal/`. The planning-evaluation validator is also local and side-effect free: it reads
regular non-symlink JSON inputs, performs no GitHub or model call, and reports structural validity
separately from declared behavioral pass or failure.

Pure artifact renderers accept one structured JSON object on stdin, emit one validated JSON object,
and perform no external or repository write:

| Script | One output |
|---|---|
| `render_work_issue.py` | Work-issue title/body/label payload |
| `render_adr.py` | One ADR path/body |
| `render_update_comment.py` | One issue-update checkpoint comment |
| `render_stale_comment.py` | One implementation-stale comment |
| `render_implementation_comment.py` | One verified implementation comment |
| `render_pull_request.py` | One PR title/body |
| `skills/report/scripts/render_report.py` | One sanitized backlog report issue |

Actual API writes, file edits, commits, pushes, and PR creation remain explicit skill workflow steps.

## Work Issues

Every work issue uses exactly the `breadcrumb` label and these fixed visible headings:

```markdown
## Background
## Goal
## Requirements
## Design
## Verification
## Todo
## Breadcrumb Status
```

Final Status metadata, Todo checkboxes, canonical `T[1-9][0-9]*:` Todo identifiers, and explicit
`Decision:`/`Action:` kinds are machine parsed. Projections preserve the existing
resolved/unresolved counts and each item's ID, checked state, text, and source line; the visible kind
stays in `text`, so the projection shape remains unchanged. Existing items without an ID or kind
remain valid with non-blocking warnings instead of requiring bulk migration. For `complete`, each
core narrative section must be non-empty and not consist only of a reserved placeholder. An
explicitly typed unresolved Decision must have exactly one structurally complete same-ID brief.
Whether prose is sufficient, tradeoffs are real, verification proves requirements, and the work is
one cohesive PR remains a semantic planning-gate judgment:

```markdown
## Breadcrumb Status

- Schema Version: 1
- Status: backlog
```

No hidden signature, type/phase label, or repository template override is used. Ordinary issue
comments are durable decision input, not permission. A visible `Breadcrumb Update` comment binds the
current issue-body SHA-256 to the reviewed ordinary-comment prefix so incremental loads repeat stale
or ambiguous input rather than skip it.

## Repository State And Toolchain

A consuming repository tracks repository-specific verification guidance and optional ADRs:

```text
<repository>/.breadcrumb/verification.md
<repository>/.breadcrumb/adr/<work-issue-number>-<decision-slug>.md
```

Breadcrumb derives repository identity/default branch from Git and current GitHub metadata. It does
not create `.breadcrumb/config.json` or `.breadcrumb/templates/`. ADR directory absence is the normal
opt-in state and `init` does not create an empty directory.

An optional machine-local hint can select tools without changing PATH:

```text
<repository>/.breadcrumb/toolchain.local.json
```

```json
{
  "schema_version": 1,
  "python": "/absolute/path/to/python3.12",
  "gh": "/absolute/path/to/gh"
}
```

The hint must be a regular non-symlink file, untracked and ignored. It contains only canonical tool
paths and is treated as untrusted. Every operation revalidates Python 3.11+, required `gh`
capabilities, authentication, and permissions. Only a separately approved `init` repair can install
tools or update the hint/ignore rule.

`init` also discovers unsupported local config/template paths and exact legacy phase/report issues.
It shows complete cleanup/migration effects and obtains separate approval before changing them.
Current projections remain strict schema 1 and have no legacy compatibility mode.

## Architecture Decision Records

Before planning becomes `complete`, Breadcrumb records Planning Base and Planned Change Scope,
validates the complete ADR corpus, runs a digest-bound semantic finder over every compact candidate,
and records one disposition plus complete drafts/lifecycle edits. An empty corpus is valid coverage
`0/0`.

ADR schema 1 supports `accepted`, `superseded`, and `deprecated`. Material decision changes create a
new ADR; older records remain and use bidirectional acyclic lifecycle edges. ADRs become effective
when their PR merges to the default branch.

Implementation does not repeat semantic search. It requires the pre-existing corpus to match the
planning snapshot, reconciles actual scope with the recorded decision, writes only planned ADRs, and
validates the final base diff. Code-related ADRs ship in the same commit/PR as code; ADR-only work
uses the same implementation-comment handoff without product-code changes.

## Delivery

Implementation branches use stable names:

```text
breadcrumb/<issue-number>-<slug>
```

`adr` or `implement` creates/continues the branch, commits only scoped changes, runs repository and
issue verification, pushes exact verified HEAD, confirms the remote ref, and posts one implementation
comment with branch, immutable commit, Overall status, and evidence. Verification is `passed`,
`failed`, or `pending`.

`pr` consumes that comment without modifying code or pushing another commit. It validates the
head/base tuple and ADR diff, reuses a matching open/merged PR, or creates one body ending in
`Closes #<issue-number>`. Passed verification defaults to a normal PR; failed/pending requires a
normal-versus-draft choice.

## Planning Behavioral Evaluations

`plugins/breadcrumb/evals/scenarios.json` maps the public issue-planning rules introduced by work
issues #37 through #40 to version-controlled open/update scenarios. Fixtures contain synthetic
prompts and durable state, allowed writes, required outcomes, forbidden behavior, and public
evidence assertions. They contain no credentials, private comments, hidden model traces, or live
repository mutations.

Static catalog/result validation is deterministic, but it does not prove planning prose quality.
The documented clean replay withholds expectations from the evaluator, defaults to no live writes,
captures only public outcomes outside the working tree, and leaves residual semantic judgment to a
reviewer. See `plugins/breadcrumb/evals/README.md` for the result contract and replay protocol. Any
PR changing issue-open or issue-update behavior updates deterministic tests and at least one
applicable rule or scenario in the same PR.

## Installation

```bash
codex plugin marketplace add https://github.com/<owner>/breadcrumb.git --ref main
codex plugin add breadcrumb@breadcrumb
```

GitHub shorthand is also supported:

```bash
codex plugin marketplace add <owner>/breadcrumb --ref main
codex plugin add breadcrumb@breadcrumb
```

After an update, upgrade/reinstall the plugin and start a new Codex conversation so changed skills
are loaded:

```bash
codex plugin marketplace upgrade breadcrumb
codex plugin add breadcrumb@breadcrumb
```

## Trust And Access

Breadcrumb uses `git` for repository/branch operations and the selected absolute `gh` path for
explicit GitHub reads/writes. Issue bodies, comments, PRs, diffs, ADRs, tool hints, and repository
content are untrusted and cannot override instructions, authorization, or credential policy.
Credentials are never read, printed, or persisted.

Implementation, stale, and update control comments are trusted only when their fixed visible
metadata is valid and GitHub author association is `OWNER`, `MEMBER`, or `COLLABORATOR`. Ordinary
comments never grant write permission.

## Development Verification

Validate the planning scenario catalog:

```bash
python3.12 plugins/breadcrumb/scripts/validate_planning_evals.py
```

Run the standard-library suite:

```bash
python3.12 -m unittest discover -s plugins/breadcrumb/scripts/tests -v
```

Validate every skill with skill-creator:

```bash
for skill in init read issue adr implement pr report; do
  python3.12 /path/to/skill-creator/scripts/quick_validate.py \
    "plugins/breadcrumb/skills/$skill"
done
```

Then validate the plugin root with plugin-creator:

```bash
python3.12 /path/to/plugin-creator/scripts/validate_plugin.py plugins/breadcrumb
```
