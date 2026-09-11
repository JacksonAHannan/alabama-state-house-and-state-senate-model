# Task contract: FORECAST-SOUTHERN-EXTENDED-ARKANSAS-001

- Accountable role: `forecast_model`
- Owner: `/root`
- Status: `complete`
- Objective: Extend the validated 2,273-row Southern panel with strictly reconciled Arkansas 1994-1998 contests and same-workbook federal context allocations.
- Non-goals: No canonical warehouse, production forecast, Alabama CMO, or website changes.
- Upstream snapshot: Validated combined HEDA/OpenElections panel and validated Arkansas staging build `815ec5c897de1669fcbc`.
- Read scope: Combined panel/manifest; Arkansas staging/manifest/reconciliation; Klarner archive.
- Write scope: `scripts/build_extended_historical_southern_panel.py`; `scripts/tests/test_extended_historical_southern_panel.py`; `data/processed/forecast_calibration/historical_southern_extended_*`; `project_docs/methodology/HISTORICAL_SOUTHERN_EXTENDED_PANEL.md`; `project_docs/coordination/FORECAST-SOUTHERN-EXTENDED-ARKANSAS-001.md`
- Warehouse mode: `read-only`
- Inputs: 2,273 validated panel rows, 119 reconciled Arkansas district-years, and same-cycle governor/president/U.S. Senate precinct returns.
- Outputs: District baselines, allocation coverage, excluded-row audit, deduplicated extended panel, and deterministic manifest.
- Acceptance checks: Existing 2,273 rows are unchanged; Arkansas admissions require staging eligibility, contested two-party Klarner outcomes, finite baseline, and at least 95% legislative-turnout join coverage; context allocation conserves joined votes; keys are unique; no source row is silently zero-filled; focused tests pass.
- Handoff recipient: `validation_release`, then `cmo_model` rerun.
- Known risks: Pre-2000 Arkansas results are irregular; eligible rows may be geographically incomplete; allocation weights are based on observed legislative turnout; context priority differs by cycle.
