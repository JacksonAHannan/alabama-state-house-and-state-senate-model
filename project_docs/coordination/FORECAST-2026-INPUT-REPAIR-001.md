# Task contract: FORECAST-2026-INPUT-REPAIR-001

- Accountable role: `forecast_model`
- Owner: `/root`
- Status: `complete`
- Objective: Rebuild the post-2016 polling-CMO forecast from corrected 2025-plus-2026 finance totals and resolved-name incumbency, then verify the SD-7 decomposition and race-level invariants.
- Non-goals: Change probability calibration, model specification, public website files, historical CMO, or raw inputs.
- Upstream snapshot: `INPUT-2026-FINANCE-INCUMBENCY-REPAIR-001` review candidate dated 2026-08-24.
- Read scope: `data/processed/finance/2026_candidate_finance_reconciled.csv`; `data/processed/war/2026_candidate_incumbency.csv`; current post-2016 polling, historical finance, roster, and calibration inputs.
- Write scope: `scripts/tests/test_post2016_polling_cmo_forecast.py`; `data/processed/forecast_calibration/post2016_polling_cmo_`; `data/processed/forecast_calibration/post2016_headline_v1_`; `project_docs/model/POST2016_POLLING_CMO_EXPERIMENT.md`; `project_docs/model/POST2016_HEADLINE_FORECAST_V1.md`; `project_docs/audits/2026_FORECAST_INPUT_REPAIR.md`; `project_docs/coordination/FORECAST-2026-INPUT-REPAIR-001.md`; `project_docs/coordination/active_tasks.csv`
- Warehouse mode: `read-only`
- Inputs: Corrected candidate finance and incumbency staging outputs plus the current approved post-2016 forecast specification.
- Outputs: Rebuilt experiment and headline forecast artifacts, focused regression tests, and an SD-7 before/after audit.
- Acceptance checks: Sam Givhan is modeled as the Republican incumbent with $370,509.84 raised; Jared Sluss is a nonincumbent with $19,146.16 raised; SD-7 remains Republican-favored; every modeled race is unique; finance/incumbency/forecast tests pass.
- Handoff recipient: `validation_release`
- Known risks: Finance is an August 14 in-progress snapshot; three nominees remain explicitly unobserved; public artifacts remain stale until a separate validated web publication task.
