# Task contract: FORECAST-SOUTHERN-COMBINED-PANEL-001

- Accountable role: `forecast_model`
- Owner: `/root`
- Status: `complete`
- Objective: Extend the validated historical Southern comparison panel with strictly gated OpenElections cycles while preserving HEDA observations for existing eligible keys.
- Non-goals: No canonical warehouse, production forecast, Alabama CMO, or website changes.
- Upstream snapshot: Validated HEDA panel and validated OpenElections staging build `db15d56e...`.
- Read scope: Historical HEDA panel/manifest; OpenElections staging/manifest; Klarner archive; staging validation reports.
- Write scope: `scripts/build_combined_historical_southern_panel.py`; `scripts/tests/test_combined_historical_southern_panel.py`; `data/processed/forecast_calibration/historical_southern_combined_*.csv`; `data/processed/forecast_calibration/historical_southern_combined_manifest.json`; `project_docs/methodology/HISTORICAL_SOUTHERN_COMBINED_PANEL.md`; `project_docs/coordination/FORECAST-SOUTHERN-COMBINED-PANEL-001.md`
- Warehouse mode: `read-only`
- Inputs: Strict HEDA rows plus OpenElections precinct legislative/context observations.
- Outputs: OpenElections district baselines, allocation coverage audit, strict/permissive eligibility, and a deduplicated combined panel.
- Acceptance checks: HEDA retains precedence on overlapping eligible keys; OE context allocation conserves joined votes; strict OE rows obey cycle/district/status/coverage gates; combined keys are unique; no partial/unreviewed row becomes strict eligible; focused tests pass.
- Handoff recipient: `validation_release`, then `cmo_model` tournament.
- Known risks: Precinct joins can miss context; Georgia 2014 is unofficial; AR2008 and SC2006 are context-only; explicitly reviewed districts remain excluded.
