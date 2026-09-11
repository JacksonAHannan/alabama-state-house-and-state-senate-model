# Task contract: CMO-SOUTHERN-HISTORICAL-TOURNAMENT-001

- Accountable role: `cmo_model`
- Owner: `/root`
- Status: `complete`
- Objective: Tournament historical Southern downballot-lag and symmetric-incumbency specifications and produce out-of-state candidate-quality residuals from the validated strict sample.
- Non-goals: No replacement of Alabama CMO, no production forecast changes, no canonical warehouse writes, and no website publication.
- Upstream snapshot: Independently validated `SOUTHERN-HISTORICAL-PANEL-001`, build ID `e249019058aa1177bca1`.
- Read scope: `data/processed/forecast_calibration/historical_southern_heda_panel.csv`; its manifest and validation v3; relevant CMO methodology documentation.
- Write scope: `scripts/run_historical_southern_cmo_tournament.py`; `scripts/tests/test_historical_southern_cmo_tournament.py`; `data/processed/war/historical_southern_cmo_*.csv`; `data/processed/war/historical_southern_cmo_manifest.json`; `project_docs/model/HISTORICAL_SOUTHERN_CMO_TOURNAMENT.md`; `project_docs/coordination/CMO-SOUTHERN-HISTORICAL-TOURNAMENT-001.md`
- Warehouse mode: `read-only`
- Inputs: Strict model-eligible HEDA/Klarner historical comparison panel, 2002–2012.
- Outputs: Forward-year and leave-state-out predictions and metrics, model ranking, sensitivity metrics, candidate-oriented out-of-state residuals, and deterministic run manifest.
- Acceptance checks: Strict sample only; no train/test state overlap in leave-state-out folds; no future years in forward folds; candidate residual sign is symmetric by party; baseline-only comparator is retained; all output keys and manifest hashes reconcile; focused tests pass.
- Handoff recipient: `validation_release`, then `cmo_model` for interpretation.
- Known risks: Coverage begins in 2002 rather than 1994; context sources differ by cycle; leave-state-out predictions cannot learn held-out state effects; descriptive residuals are not causal candidate effects.
