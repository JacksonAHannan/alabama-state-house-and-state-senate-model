# Task contract: CMO-SOUTHERN-EXTENDED-TOURNAMENT-001

- Accountable role: `cmo_model`
- Owner: `/root`
- Status: `complete`
- Objective: Rerun the prespecified historical Southern CMO tournament on the validated 2,383-row panel containing Arkansas 1994-1998 and compare results with the validated 2,273-row run.
- Non-goals: No canonical warehouse, production forecast, Alabama CMO, or website changes.
- Upstream snapshot: Validated extended historical Southern panel build `ec3eca6a58834c1365d3`.
- Read scope: Extended panel/manifest; unchanged tournament code; validated combined-panel tournament outputs.
- Write scope: `scripts/tests/test_extended_historical_southern_cmo.py`; `data/processed/war/extended_historical_southern/`; `project_docs/model/EXTENDED_HISTORICAL_SOUTHERN_CMO_TOURNAMENT.md`; `project_docs/coordination/CMO-SOUTHERN-EXTENDED-TOURNAMENT-001.md`
- Warehouse mode: `read-only`
- Inputs: 2,383 strict race observations and prespecified seven-model tournament.
- Outputs: Metrics, folds, ranking, candidate residuals, effects, deterministic manifest, comparison note, and focused tests.
- Acceptance checks: All input rows receive symmetric unique LOSO candidate residuals; temporal folds use prior years only; selection follows the declared guardrail; output hashes/counts reconcile; comparison to the 2,273-row run is explicit; focused tests pass.
- Handoff recipient: `validation_release`
- Known risks: Only one state contributes pre-2000 rows; Arkansas context footprint is incomplete; state-aware transportability remains uncertain.
