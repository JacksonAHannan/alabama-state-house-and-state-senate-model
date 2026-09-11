# Task contract: VALIDATE-FORECAST-ROBUST-V1-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete` — PASS as a research candidate. Build `b5c625a6edb0a7c238fb` passes leakage, common-population, metrics, probability, error, finance, scenario, 50,000-draw, lineage, deterministic rebuild, and 11/11 focused-test checks; production/web integration remains separate.
- Objective: Independently validate robust forecast v1 and every implemented stage from forward margins through scenarios.
- Non-goals: No code, model, warehouse, website, or publication changes.
- Upstream snapshot: `FORECAST-ROBUST-PIPELINE-V1-001` review candidate and validated incumbency staging.
- Read scope: Robust implementation/tests/outputs/model note and all referenced upstream artifacts.
- Write scope: `project_docs/audits/ROBUST_FORECAST_V1_VALIDATION.md`; `project_docs/coordination/VALIDATE-FORECAST-ROBUST-V1-001.md`.
- Warehouse mode: `read-only`
- Inputs: Review-candidate artifacts, recent panel, incumbency staging, poll errors, 2026 prospective inputs, and scenario source.
- Outputs: PASS/FAIL audit with exact evidence and blockers.
- Acceptance checks: Temporary deterministic rebuild; verify candidate identity and prior-cycle leakage rules; common-fold counts; exact metrics/guardrails/baseline selection; probability family calculations; shared-error decomposition; subgroup coverage; finance noneligibility; 48-district/50,000-draw simulation and seat normalization; scenario/headline separation; hashes and tests.
- Handoff recipient: `/root`; production/web integration is a separate serialized task.
- Known risks: Probability family selection uses only three modern forward cycles; finance and geographic region are coverage gaps; simulations cover modeled contested seats rather than complete chambers.
