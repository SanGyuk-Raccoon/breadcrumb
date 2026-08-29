---
name: init
description: "Initialize, audit, repair, or migrate Breadcrumb support in a GitHub repository. Use for repository readiness, toolchain recovery, setup publication, or legacy Breadcrumb migration; do not use for ordinary issue planning or implementation."
---

# Initialize Breadcrumb

Prepare one repository for the Breadcrumb workflow. Discovery is read-only; initialization does not
implicitly approve tool installation, machine-local configuration, legacy cleanup, or issue
migration.

Read [common.md](../../references/common.md), then
[init.md](../../references/init.md). Read [artifacts.md](../../references/artifacts.md) when
validating or migrating an artifact, and [adr.md](../../references/adr.md) when the ADR directory is
present.

Report readiness separately for issue reads, issue writes, implementation fetch/push, stale-PR
conversion, verification, and PR writes. Perform only the setup or migration changes explicitly
authorized by the user. Do not open or update an ordinary work issue, modify product code, or create
a delivery PR from this skill.
