# Task contract: CMO-SOUTHERN-EXTENDED-V2-TOURNAMENT-001

- Accountable role: `cmo_model`
- Owner: `/root`
- Status: `complete`
- Objective: Rerun the unchanged historical Southern CMO tournament on the independently validated 2,402-row Tennessee-extended panel.
- Non-goals: No canonical warehouse, production forecast, Alabama CMO, or website changes.
- Upstream snapshot: Validated `historical_southern_extended_v2_panel.csv`, 2,402 unique contests.
- Read scope: V2 panel and manifest; tournament script; prior 2,383-row tournament outputs and audit.
- Write scope: `scripts/tests/test_extended_v2_historical_southern_cmo.py`; `data/processed/war/extended_v2_historical_southern/`; `project_docs/model/EXTENDED_V2_HISTORICAL_SOUTHERN_CMO_TOURNAMENT.md`; `project_docs/coordination/CMO-SOUTHERN-EXTENDED-V2-TOURNAMENT-001.md`.
- Warehouse mode: `read-only`
- Inputs: Validated 2,402-row panel and the existing prespecified seven-model tournament implementation.
- Outputs: Fold predictions, rankings, effects, candidate residuals, manifest, focused tests, and comparison with the prior run.
- Acceptance checks: Input count is 2,402; candidate residuals are symmetric and cover 4,804 party observations; one model is selected under the unchanged rule; fold isolation and keys remain valid; manifest counts/hashes reconcile; focused tests pass.
- Handoff recipient: `validation_release`.
- Known risks: Only 19 Tennessee contests are newly admitted; model selection may be sensitive to a small number of new state-cycle observations.
