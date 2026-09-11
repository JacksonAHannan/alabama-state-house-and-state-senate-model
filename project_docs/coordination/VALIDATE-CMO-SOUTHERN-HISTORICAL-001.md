# Task contract: VALIDATE-CMO-SOUTHERN-HISTORICAL-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently validate the historical Southern CMO tournament, model selection, fold isolation, and candidate residual construction.
- Non-goals: No implementation, canonical warehouse, Alabama CMO, forecast, or website changes.
- Upstream snapshot: `CMO-SOUTHERN-HISTORICAL-TOURNAMENT-001` review candidate against validated panel build `e249019058aa1177bca1`.
- Read scope: Tournament pipeline/tests/outputs/manifest, validated historical panel, and model note.
- Write scope: `project_docs/audits/CMO_SOUTHERN_HISTORICAL_VALIDATION.md`; `project_docs/coordination/VALIDATE-CMO-SOUTHERN-HISTORICAL-001.md`
- Warehouse mode: `read-only`
- Inputs: Strict 1,805-race panel and tournament release candidate.
- Outputs: Pass/fail report for experimental analytical use.
- Acceptance checks: Rebuild deterministically; verify strict-only sample; forward folds contain no future observations; LOSO folds contain no held-out state in training; recompute metrics and selection; verify symmetric party residuals, unique keys, effects, and manifest hashes; focused tests pass.
- Handoff recipient: `cmo_model`
- Known risks: Model selection uses only six cycles; state-specific errors remain large; residuals are descriptive rather than causal.
