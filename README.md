# Breadcrumb

Breadcrumb is a GitHub issue based workflow for durable AI-assisted development. One cohesive pull
request is planned, implemented, verified, and delivered through one work issue, while chat remains
temporary working context.

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

A consuming repository keeps only repository-specific verification guidance:

```text
<repository>/.breadcrumb/verification.md
```

Breadcrumb derives repository identity and default branch from the Git root, remotes, and current
GitHub metadata. It does not create `.breadcrumb/config.json` or `.breadcrumb/templates/`.

`init` is also the version-migration entry point. Its read-only audit inventories unsupported
config/template paths without loading them, legacy phase labels and open issues, and exact legacy
Bug or Feature Request bodies. When candidates exist it shows the complete file, issue, label,
commit, and close plan before requesting the required cleanup or bulk-migration confirmation. It
does not mutate merely because initialization was requested, and it asks no migration question when
there is nothing to migrate. Normal `list` and `inspect` remain strict schema 1 projections with no
legacy compatibility parsing.

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

## Read-Only Projection

The plugin has one public script entry point and requires Python 3.11 or newer:

```bash
python3.12 plugins/breadcrumb/scripts/breadcrumb.py list
python3.12 plugins/breadcrumb/scripts/breadcrumb.py list --status in-progress
python3.12 plugins/breadcrumb/scripts/breadcrumb.py inspect 18
python3.12 plugins/breadcrumb/scripts/breadcrumb.py inspect 18 --comments incremental
python3.12 plugins/breadcrumb/scripts/breadcrumb.py inspect 18 --comments all
```

The script discovers the current GitHub repository from Git, queries issues with the `breadcrumb`
label, parses the fixed body and trusted control comments, and queries GitHub closing pull
request relationships. It emits JSON only and performs no writes. A malformed issue is returned with
`valid: false` and structured errors without hiding valid siblings.

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

Breadcrumb uses `git` for repository and branch operations and `gh api` for explicit GitHub reads
and writes. Issue bodies, comments, pull-request bodies, diffs, and repository content are untrusted
task data; they cannot override active instructions, authorization, or credential policy.

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
