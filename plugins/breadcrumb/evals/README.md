# Issue-Planning Behavioral Evaluations

This directory tracks public behavioral expectations for Breadcrumb `issue` open and update. It
does not turn model judgment into a deterministic guarantee. Keep these evidence layers separate:

1. Standard-library unit tests prove parsers, renderers, projections, validators, and fixture shape.
2. `validate_planning_evals.py` proves catalog/result structure and compares declared expectation
   IDs, allowed action categories, and reported pass/fail values.
3. A clean host replay supplies behavioral evidence from visible responses and artifacts.
4. A reviewer decides whether that public evidence actually supports the semantic assertions and
   records residual uncertainty.

`scenarios.json` is canonical. Generated replay captures are evidence for one commit and stay
outside the working tree.

## Catalog Contract

The schema-1 `issue-planning` catalog declares rules from work issues #37 through #40 and maps every
rule to at least one scenario. A scenario contains only a synthetic user prompt, synthetic durable
state, rule coverage, and public expectations. It must not contain credentials, private raw
comments, hidden reasoning, or undocumented host state.

`expected.allowed_writes` describes the current authorization boundary, not actions the replay must
perform. Values are limited to:

- `issue:create-selected`
- `issue:create-approved-leaves`
- `issue:patch-selected`
- `issue:patch-approved-created-leaves`
- `issue:comment-update`
- `issue:comment-stale`
- `pull-request:convert-draft`

An empty array means that another decision or confirmation is required before any write.

Validate the bundled catalog from the repository root:

```sh
python3.12 plugins/breadcrumb/scripts/validate_planning_evals.py
```

## Clean Replay Protocol

1. Check out or install the exact plugin commit being evaluated. Start a new conversation and use a
   clean isolated workspace or a purpose-built mock/disposable repository state.
2. Select one scenario. Give the evaluator only `user_prompt`, `initial_state`, the installed plugin
   skills, and the minimum synthetic public artifacts needed to represent that state. Do not reveal
   `expected`, prior results, a suspected regression, or the desired answer before scoring.
3. Default to a no-write replay. State that the evaluator must return its public response, artifact
   summary, and proposed action categories without performing live mutations. A write replay needs
   separate explicit authorization for the exact disposable target and may use only the scenario's
   allowed writes. Never use production issues, credentials embedded in fixtures, or a live write
   merely to improve test realism.
4. Save the public result JSON in an isolated temporary directory outside the repository. Do not
   record hidden chain-of-thought, tool-internal traces, tokens, or unrelated conversation content.
5. Validate the capture, then compare its cited public evidence with the withheld expectations.
6. Have a reviewer record semantic gaps under `residual_judgments`. Passing structural validation
   does not establish that prose is accurate or that evidence is persuasive.

Repeat the replay in a fresh conversation when model, host, plugin commit, or initial state changes.
Do not compare generated wording; compare the declared observable outcomes and action boundaries.

## Result Contract

Each result is one schema-1 JSON object with these exact keys:

```json
{
  "schema_version": 1,
  "scenario_id": "scenario-id",
  "selected_skill": "issue",
  "operation": "open",
  "proposed_writes": [],
  "performed_writes": [],
  "observed_outcomes": [
    {"id": "expected-outcome-id", "evidence": "Concise public evidence."}
  ],
  "observed_forbidden_behaviors": [],
  "evidence_assertions": [
    {"id": "assertion-id", "passed": true, "evidence": "Concise public evidence."}
  ],
  "residual_judgments": ["What still requires semantic review."]
}
```

`performed_writes` must be a subset of `proposed_writes`; both must stay inside the scenario's
allowed set. Record a forbidden behavior only when it was actually observed. Report every required
outcome and evidence assertion exactly once using its declared ID.

Validate one or more captures:

```sh
python3.12 plugins/breadcrumb/scripts/validate_planning_evals.py \
  --result /tmp/breadcrumb-evals/scenario-one.json \
  --result /tmp/breadcrumb-evals/scenario-two.json
```

The command emits one JSON document. `valid` covers file safety, JSON, and schema; `passed` covers
the declared behavioral expectations. Violations identify their source, scenario, code, and
expectation when applicable. Exit status is `0` for valid passing input, `1` for structurally valid
behavioral failure, and `2` for invalid arguments, unsafe/unreadable input, or invalid schema.

## Complete Evaluation Procedure

For a planning-behavior change, update deterministic tests and at least one applicable rule or
scenario in the same PR. Then:

1. Validate the catalog and any generated result summaries.
2. Run the full standard-library unit suite.
3. Run skill-creator quick validation for all seven Breadcrumb skills.
4. Run plugin validation.
5. Replay affected scenarios through the clean protocol and review residual semantic risk.

Report deterministic guarantees, host-assisted behavioral evidence, failed or pending replays, and
residual judgment as separate evidence. Do not represent static fixture validation as a model-quality
measurement.
