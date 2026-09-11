# Task contract: VALIDATE-CMO-SOUTHERN-EXTENDED-V2-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete` — PASS for experimental calibration. The deterministic rebuild reproduces 2,402 inputs, 32,067 predictions, 4,804 symmetric candidate rows, all 19 Tennessee contests/38 party rows, isolated folds, exact ranking/effects, current hashes, and 6/6 focused/generic tests.
- Objective: Independently validate the historical Southern CMO tournament rerun on the Tennessee-extended panel.
- Non-goals: No implementation, model-rule, warehouse, website, or production forecast changes.
- Upstream snapshot: `CMO-SOUTHERN-EXTENDED-V2-TOURNAMENT-001` review candidate and validated 2,402-row input panel.
- Read scope: Tournament implementation/tests, v2 input panel/manifest, current outputs/manifest/method note, and prior validated tournament outputs for comparison.
- Write scope: `project_docs/audits/CMO_SOUTHERN_EXTENDED_V2_VALIDATION.md`; `project_docs/coordination/VALIDATE-CMO-SOUTHERN-EXTENDED-V2-001.md`.
- Warehouse mode: `read-only`
- Inputs: Review-candidate tournament artifacts and independently validated panel.
- Outputs: PASS/FAIL audit with exact metrics and blocking findings.
- Acceptance checks: Temporary rebuild; verify fold isolation and unchanged selection rule; independently reproduce ranking, RMSEs, selected effects, row counts, Tennessee residual inclusion, party symmetry, unique keys, hashes, determinism, and focused/generic tests.
- Handoff recipient: `/root`.
- Known risks: Minor metric shifts can be real because Tennessee is a new state-cycle; model selection must not be inferred solely from prior-run expectations.
