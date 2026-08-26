# Breadcrumb

Breadcrumb is a GitHub issue based workflow for durable AI-assisted development. One cohesive pull
request is planned, implemented, verified, and delivered through one work issue, while chat remains
temporary working context. Optional repository-local ADRs keep long-lived decisions beside the code
that implements them.

## Workflow

```text
backlog -> in-progress -> complete -> implementation -> pull request -> issue closed
```

- `backlog` means planning has not started.
- `in-progress` means requirements or design are being refined and at least one Todo is unresolved.
- `complete` means planning is implementation-ready and no Todo is unresolved.
- A merged closing pull request completes delivery by closing the GitHub issue. Body Status remains
  `complete`; it does not duplicate delivery state.

Meaningful completed Todo items remain checked as durable decision history. New next actions may be
appended while work evolves. Requirement and design changes after implementation mark the previous
implementation stale and return the issue to `in-progress`.

New or rewritten Todo use stable `T<number>` identifiers. A decision-bearing Todo has a matching
Decision Brief in the human-readable issue narrative with its reason, real options and tradeoffs,
recommendation, uncertainty, and a reply example. A user can answer several IDs in issue comments;
`load` retrieves unprocessed comments by default and an explicit full-history mode remains available
for audit or recovery.

Before planning becomes `complete`, Breadcrumb records a Planned Change Scope, validates and
searches the complete ADR corpus, and records an ADR disposition plus any required drafts. An empty
corpus is valid coverage `0/0`.

## Skills

The plugin exposes two user-facing skills:

```text
breadcrumb
breadcrumb-report
```

`breadcrumb` routes the ordinary work lifecycle internally:

- initialize or audit a repository and coordinate any version migration it discovers;
- open, list, load, update, or review a work issue;
- implement and verify a complete issue;
- create or reuse its linked pull request.

Explicit intent wins over state. State validates whether the operation can run. An ambiguous request
loads current state without mutating it.

`breadcrumb-report` turns the current conversation into a privacy-minimized `Bug` or
`Feature Request` for the fixed `github.com/SanGyuk-Raccoon/breadcrumb` upstream. It searches open
and closed issues completely before proposing a write. An independently actionable report is
rendered from the bundled `work.md` as a schema 1 `backlog` work issue with exactly the `breadcrumb`
label and one refinement Todo; useful new context for an existing report is proposed as one minimal
comment. Both write paths require an exact preview and explicit approval. Old report artifacts remain
an `init` migration concern rather than a compatibility mode in `list` or `inspect`.

## Work Issue

Every work issue uses the exact `breadcrumb` label and these fixed level-two headings:

```markdown
## Background
## Goal
## Requirements
## Design
## Verification
## Todo
## Breadcrumb Status
```

Only the final Status section and Todo checkboxes are machine parsed:

```markdown
## Breadcrumb Status

- Schema Version: 1
- Status: backlog
```

Narrative sections remain ordinary human-readable Markdown. No hidden state signature, type label,
phase label, or repository template override is used.

## Repository State

A consuming repository keeps repository-specific verification guidance and, when adopted,
repository-local ADRs as tracked Breadcrumb state:

```text
<repository>/.breadcrumb/verification.md
<repository>/.breadcrumb/adr/<work-issue-number>-<decision-slug>.md  # optional
```

Breadcrumb derives repository identity and default branch from the Git root, remotes, and current
GitHub metadata. It does not create `.breadcrumb/config.json` or `.breadcrumb/templates/`.
The ADR directory is not created by `init`; its absence is the normal opt-in state.

An optional machine-local hint can make tool selection deterministic across conversations without
changing PATH or committing machine-specific paths:

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

The schema-1 hint contains only canonical absolute `python` and `gh` paths. It must be a regular
non-symlink file, untracked and ignored by Git, and is treated as untrusted input. Breadcrumb
revalidates both executables, versions, and required capabilities on every operation and falls back
to discovery when the hint is missing, stale, malformed, or unsafe. `init` creates or updates it only
after showing the exact payload and receiving explicit approval. The default ignore location is the
clone-local `.git/info/exclude`; changing the tracked root `.gitignore` is a separate choice.

`init` is also the version-migration entry point. Its read-only audit inventories unsupported
config/template paths without loading them, legacy phase labels and open issues, and exact legacy
Bug or Feature Request bodies. When candidates exist it shows the complete file, issue, label,
commit, and close plan before requesting the required cleanup or bulk-migration confirmation. It
does not mutate merely because initialization was requested, and it asks no migration question when
there is nothing to migrate. Normal `list` and `inspect` remain strict schema 1 projections with no
legacy compatibility parsing.

The same read-only audit resolves installed Python and GitHub CLI candidates by actual execution and
reports readiness per operation. A compatible versioned or outside-PATH executable is used directly
instead of being reinstalled. When no usable candidate exists, `init` shows the exact supported
package source, command, privilege, local-state, and PATH effects, then performs only the separately
approved repairs and revalidates their results.

Implementation branches use a stable name derived from the work issue:

```text
breadcrumb/<issue-number>-<slug>
```

Implementation always commits, runs applicable repository and issue verification, pushes the
verified commit, checks the remote ref, and then records a visible implementation comment with
branch and immutable commit links. Verification may be `passed`, `failed`, or `pending`.

Pull requests target the current GitHub default branch and end with `Closes #<issue-number>`. GitHub's
closing relationship is the durable PR link. Passed verification defaults to a normal PR; failed or
pending verification requires choosing normal or draft.

## Architecture Decision Records

ADR files use a fixed schema-1 Markdown template with `accepted`, `superseded`, and `deprecated`
states. Each file records its source Work Issue, Summary, Context, Affected Areas, Decision,
Consequences, Review Triggers, and repository-local lifecycle relationships. Material decision
changes create a new ADR; old records are superseded or deprecated and retained rather than deleted.

Planning runs a local deterministic projection first. It validates safe regular UTF-8 Markdown,
strict filenames and fields, Work Issue identity, bidirectional acyclic supersession, corpus digest,
and optional base diff. The main context receives only a narrative-free document index. An isolated
read-only subagent runs the compact finder, which orders every ADR by explicit Work Issue, path,
component, resource, behavior, and lifecycle signals without filtering non-matches. It verifies
content hashes before selectively reading related full ADRs and returns only related evidence,
coverage, constraints, uncertainty, and a recommended disposition to the main planning context.

Breadcrumb searches the complete corpus only when planning is finalized or materially reopened.
Implementation does not repeat that search: after code and tests are implemented, it reconciles the
actual diff with the issue's planned ADRs, adds or updates those files in the same commit and PR, and
validates the result against Planning Base. The merge itself activates the ADR; there is no
post-merge AI, runner, or synchronization job.

## Read-Only Projection

The plugin has one public script entry point and requires Python 3.11 or newer. The complete workflow
documents GitHub CLI 2.16.0 or newer as its baseline, while actual command capabilities remain the
final readiness check:

```bash
python3.12 plugins/breadcrumb/scripts/breadcrumb.py --gh-executable /absolute/path/to/gh list
python3.12 plugins/breadcrumb/scripts/breadcrumb.py --gh-executable /absolute/path/to/gh list --status in-progress
python3.12 plugins/breadcrumb/scripts/breadcrumb.py --gh-executable /absolute/path/to/gh inspect 18
python3.12 plugins/breadcrumb/scripts/breadcrumb.py --gh-executable /absolute/path/to/gh inspect 18 --comments incremental
python3.12 plugins/breadcrumb/scripts/breadcrumb.py --gh-executable /absolute/path/to/gh inspect 18 --comments all
python3.12 plugins/breadcrumb/scripts/breadcrumb.py adr
python3.12 plugins/breadcrumb/scripts/breadcrumb.py adr --base origin/main
python3.12 plugins/breadcrumb/scripts/breadcrumb.py adr --compact --base origin/main
python3.12 plugins/breadcrumb/scripts/breadcrumb.py adr --base <commit> --finder-input-json '<compact-json>'
```

Issue commands discover the current GitHub repository from Git, query issues with the `breadcrumb`
label, parse the fixed body and trusted control comments, and query GitHub closing pull-request
relationships. The `adr` command remains local and uses Git only for repository identity and an
optional immutable base snapshot. Every command emits JSON only and performs no writes. Malformed
issues and ADR corpora return `valid: false` with structured errors rather than hiding evidence.
Compact ADR mode omits narrative and returns a hash-bound document index; finder input implies this
mode so the complete semantic candidate set can remain inside an isolated subagent context.

`--gh-executable` is optional for backward compatibility. When supplied, it must resolve from an
absolute path to an executable file, and the parser uses that exact GitHub CLI for every REST and
GraphQL request. Breadcrumb operations resolve and pass the option so an older PATH entry cannot
shadow the selected executable.

The sibling `breadcrumb-report` skill applies the same selection and revalidation rules. It may
inspect a safe local hint solely for executable selection, while its GitHub target remains fixed and
independent of the ambient repository. Tool installation and local-hint mutation remain exclusive
to the separately approved `breadcrumb init` repair flow.

The optional comment modes add a single fully paginated comment snapshot. A fixed visible
`Breadcrumb Update` comment records the exact issue-body SHA-256, a rolling digest of the reviewed
ordinary-comment prefix, and its final source comment. Incremental mode returns ordinary comments
after that source; all mode returns the full ordinary history and update artifacts. Missing, stale,
malformed, changed-prefix, or out-of-order checkpoints fall back toward repeated context rather than
skipped comments.

## Installation

Breadcrumb is distributed through the repository marketplace:

```bash
codex plugin marketplace add https://github.com/<owner>/breadcrumb.git --ref main
codex plugin add breadcrumb@breadcrumb
```

GitHub shorthand is also supported:

```bash
codex plugin marketplace add <owner>/breadcrumb --ref main
codex plugin add breadcrumb@breadcrumb
```

After an update, refresh and reinstall the plugin, then start a new Codex conversation so the new
skill is loaded:

```bash
codex plugin marketplace upgrade breadcrumb
codex plugin add breadcrumb@breadcrumb
```

## Trust And Access

Breadcrumb uses `git` for repository and branch operations and the selected absolute `gh` path for
explicit GitHub reads and writes. Issue bodies, comments, pull-request bodies, diffs, ADRs, local
toolchain hints, and repository content are untrusted task data; they cannot override active
instructions, authorization, or credential policy.

Implementation or stale comments control branch state only when their fixed visible metadata is
valid and the GitHub comment author association is `OWNER`, `MEMBER`, or `COLLABORATOR`. Credentials
are never read, printed, or persisted by Breadcrumb.

Update comments use the same trusted author associations only for the incremental checkpoint.
Ordinary comments remain untrusted decision input: author association is provenance, not decision
authority, and a comment never grants permission to change an issue.

## Development Verification

Run the full standard-library test suite:

```bash
python3.12 -m unittest discover -s plugins/breadcrumb/scripts/tests -v
```

Also validate both `plugins/breadcrumb/skills/breadcrumb` and
`plugins/breadcrumb/skills/breadcrumb-report` with skill-creator `quick_validate.py`, then validate
the plugin root with plugin-creator `validate_plugin.py` before reinstalling.
