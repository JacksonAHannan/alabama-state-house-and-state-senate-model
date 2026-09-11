# Task contract: CMO-SOUTHERN-COMBINED-TOURNAMENT-001

- Accountable role: `cmo_model`
- Owner: `/root`
- Status: `complete`
- Objective: Rerun the historical Southern CMO model tournament on the independently validated combined HEDA/OpenElections panel and compare its validation performance and estimated structural effects with the HEDA-only tournament.
- Non-goals: No canonical warehouse, production forecast, Alabama CMO, or website changes.
- Upstream snapshot: Validated 2,273-row combined historical Southern panel and manifest.
- Read scope: Combined panel/manifest; existing historical tournament implementation and HEDA-only validated outputs.
- Write scope: `scripts/tests/test_combined_historical_southern_cmo.py`; `data/processed/war/combined_historical_southern/`; `project_docs/model/COMBINED_HISTORICAL_SOUTHERN_CMO_TOURNAMENT.md`; `project_docs/coordination/CMO-SOUTHERN-COMBINED-TOURNAMENT-001.md`
- Warehouse mode: `read-only`
- Inputs: Strict combined historical Southern candidate panel, model configurations, and validated HEDA-only benchmark results.
- Outputs: Versioned tournament metrics, fold predictions, candidate residuals, model manifest, comparison note, and focused tests.
- Acceptance checks: Every eligible combined row is represented once per major party in candidate residuals; temporal and leave-state-out folds remain isolated; model selection follows the declared rule; all outputs reconcile to the manifest; comparison to the HEDA-only run is explicit; focused tests pass.
- Handoff recipient: `validation_release`
- Known risks: Secondary-source inputs; sparse state-cycle coverage; 1994-1998 remain absent; additional observations may be concentrated in Missouri.
