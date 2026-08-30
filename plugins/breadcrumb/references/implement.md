# Code Implementation

Map every durable requirement, design decision, implementation step, and Verification item to code
or tests. Inspect surrounding conventions before editing.

Implement product code and tests before planned ADR files. Reconcile actual components, paths,
resources, behaviors, and decisions with the recorded ADR plan. Permit only non-material wording or
affected-path corrections in planned ADR content. Stop before ADR mutation and return to `issue`
when a new decision, material drift, or pre-existing corpus change appears.

Render and write exactly the planned ADR create/supersede/deprecate changes. Keep code, tests, and
ADRs in the same implementation commit and PR. Run the base ADR projection after changes and require
a valid graph/diff containing no unplanned ADR path or lifecycle change.

Do not patch the issue body, reinterpret ordinary comments as implementation authority, publish a
PR, or add behavior that exists only in chat.
