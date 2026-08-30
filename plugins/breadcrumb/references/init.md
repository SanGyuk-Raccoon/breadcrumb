# Initialize, Audit, Repair, Or Migrate

Treat setup, re-audit, toolchain recovery, and version migration as one `init` intent. Discovery is
always read-only. An explicit initialization request does not approve system, machine-local, legacy
cleanup, or bulk GitHub mutations.

## Audit Toolchain And Repository Readiness

1. Apply the shared resolver. Inspect the exact local-hint path, kind, symlink state, containment,
   tracking, and ignore status before reading it. Classify Python and `gh` candidates as usable,
   outside PATH or shadowed, missing, deficient, or unsafe. Distinguish authentication and
   authorization failures from installation failures.
2. Use a compatible candidate directly, including an outside-PATH versioned executable. Report
   issue API readiness separately from `gh pr ready --undo` support.
3. Resolve the selected remote, canonical GitHub repository, current default branch, Issues support,
   issue/comment/PR write access, fetch access, and push access separately.
4. Require exactly one `breadcrumb` label. Create it only within an explicitly requested ordinary
   initialization when missing. Do not create type or phase labels.
5. Require `.breadcrumb/verification.md` to be a regular tracked file. If absent, inspect documented
   commands and CI, draft concise safe natural-language guidance, and persist it within the requested
   initialization. Never copy an unsafe command blindly.
6. Require verification guidance to be unmodified and published on the fetched default branch
   before implementation. Issue-only work may remain available while it is missing.
7. When `.breadcrumb/adr` exists, run `project_adrs.py --compact` and report digest, count, and
   schema, safety, lifecycle, or base-diff errors. Absence is ready and must remain absent.

## Plan And Apply Toolchain Repair

When no usable tool exists or selected paths cannot be recovered reliably, show an exact plan for
each deficiency: discovered path/version, missing capability, install or upgrade command, package
source, target condition, privilege, and effects on package repositories, PATH, shell profiles,
local hint, or Git exclude state.

Ask separately before each system/package action and before local-hint/ignore mutation. Use only a
supported package manager and official or already trusted source. Never improvise `curl | sh`,
replace the system Python command, or guess an unsupported-platform command.

For the local hint, show the complete schema-1 JSON and exact ignore change. Default to
`.git/info/exclude` with `/.breadcrumb/toolchain.local.json`; a tracked root `.gitignore` change is a
separate repository mutation. Revalidate all bases immediately before applying an approved repair.

After repair, execute the canonical installed paths, recheck capabilities/authentication, and only
then atomically write a safe regular untracked hint containing the two paths. Verify exact bytes,
file identity, `git check-ignore`, and absence from `git ls-files`. Preserve earlier successful
repairs if a later repair fails.

## Discover Legacy State

1. Inventory `.breadcrumb/config.json`, `.breadcrumb/templates`, and every unsupported contained
   path without reading bytes or following symlinks. Exclude supported `verification.md`, the ADR
   subtree handled by its projection, and a valid ignored local hint. Record kind, containment,
   tracking, staged/unstaged state, and publication on the fetched default branch.
2. Treat invalid ADR state as supported-but-broken diagnosis, not cleanup. Treat tracked or
   published `toolchain.local.json` as unsupported and never load it.
3. Fully paginate repository labels and open issues. Find legacy phase labels independently from
   exact legacy report bodies defined in `artifacts.md`. Exclude pull requests. Leave closed issue
   bodies unchanged; read closed delivery only when it proves an open candidate was delivered.
4. Compare worktree, index, local commits, fetched default branch, and planned verification
   publication. Do not publish a mixed unpublished commit containing supported setup and legacy
   files before the user chooses cleanup or intentional preservation.

When no candidate exists, ask no migration question and finish the readiness audit.

## Plan And Apply Migration

Group local cleanup separately from issue conversion/closure/relabeling and label deletion. Show the
exact repository, paths, issue numbers, titles, complete final bodies, final labels, close actions,
affected commits, and historical label effects before asking.

Choose a canonical issue from durable lineage and body context, never title alone. Combine material
requirement/design context from a paired phase issue. Convert an unpaired, unambiguous phase issue
in place. Convert an undelivered exact legacy report into schema-1 `backlog` with only `breadcrumb`
and this Todo:

```text
- [ ] T1: 보고 내용을 구현 가능한 요구사항, 설계와 검증 계획으로 정제한다.
```

When a merged PR already delivered it, propose closure using that evidence. Ask separately before
file removal, unpublished commit rewrite, bulk migration, intentional publication of unsupported
files, and legacy-label deletion. Never rewrite a published commit.

Immediately revalidate every path and issue before mutation. Remove or stage only approved exact
paths. Send structured API mutations once, verify each returned issue and final state, then requery
until no open legacy phase/report issue remains. Delete legacy labels only under separate approval
and only after open migration candidates are gone. Stop on failure or uncertainty without blind
retry or compensating rollback.

## Report Readiness

Report selected canonical tools, actual versions, checked capabilities, repair/migration outcomes,
and readiness by operation: issue reads, issue writes, implementation fetch/push, stale conversion,
verification, and PR writes. This report is ephemeral and is never stored in the local hint or issue.
