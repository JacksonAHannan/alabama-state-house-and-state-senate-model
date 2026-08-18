# AGENTS.md

These instructions apply to the entire repository.

## Mission

Build a reproducible, auditable Alabama state-legislative research system
that remains compatible with the other Southern state model repositories.
Accuracy, provenance, and honest uncertainty take priority over coverage or a
visually complete forecast.

## Required reading

Before changing pipelines, schemas, or model behavior, read:

1. `project_docs/ARCHITECTURE.md`
2. `project_docs/DATA_CONTRACTS.md`
3. `project_docs/STATE_ADAPTER_GUIDE.md`
4. any domain-specific methodology or audit document touched by the change

## Non-negotiable rules

- Treat `data/raw/` as immutable. Never silently modify or replace a source.
- Record source URL, retrieval time, hash, license/terms, geographic vintage,
  election cycle, and authoritative scope in a manifest.
- Keep provider-specific parsing in adapters. Downstream tables must use the
  shared canonical field names and keys.
- Never convert missing values to zero without an explicit source contract.
- Never substitute one redistricting plan, election cycle, chamber, office, or
  geographic vintage for another.
- Preserve conflicting source observations and reconciliation evidence.
- Human adjudications require evidence, rationale, reviewer status, and a
  stable identifier; do not hide them in code conditionals.
- Every reusable join must declare and test its expected cardinality.
- Generated files in `docs/`, `artifacts/`, and `data/processed/` must identify
  the code version, configuration, and model/data run that produced them.
- Do not commit credentials, tokens, proprietary data, or restricted source
  files. Check source terms before committing raw material.
- Do not describe a scaffold, placeholder, or unvalidated output as a model.

## Development workflow

1. Identify the layer and owner of the change.
2. Add or update the source/field contract before implementation.
3. Write the smallest state adapter that emits canonical records.
4. Add fixture-based tests, uniqueness checks, and reconciliation totals.
5. Run targeted tests, then the full suite.
6. Update lineage, data catalog, methodology, and validation notes.
7. Publish only from a validated, versioned run.

Prefer deterministic scripts over notebooks for production pipelines. Keep
notebooks exploratory and move accepted logic into tested modules.

## Validation expectations

At minimum, test schema, primary-key uniqueness, join cardinality, chamber and
district coverage, vote-total reconciliation, party normalization, geographic
vintage, and temporal leakage. Forecast changes also require time-forward
validation, calibration, and uncertainty diagnostics.

If evidence is incomplete, stop at a review queue or an explicit `unknown`.
Never manufacture certainty to make a pipeline pass.

