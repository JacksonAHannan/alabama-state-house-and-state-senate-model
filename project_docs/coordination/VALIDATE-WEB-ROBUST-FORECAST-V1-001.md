# Task contract: VALIDATE-WEB-ROBUST-FORECAST-V1-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently validate the robust-v1 forecast website release candidate.
- Acceptance checks: Clean rebuild; payload identifies validated build `b5c625a6edb0a7c238fb`; 48 modeled contests and all 140 districts reconcile; fixed seats and headline correlated chamber distributions reconcile; every scenario margin/probability matches its source; methodology contains no legacy Basic/Fundamentals+, normal-six-point, or obsolete sample claims; public downloads match source hashes; forecast interactions, accessibility tests, and Blue/Oxblood theme remain functional; no upstream code reads `docs/`.
- Read scope: Forecast builder/assets/tests, validated robust-v1 inputs, generated artifacts and `docs/` release candidate.
- Write scope: `project_docs/audits/ROBUST_FORECAST_V1_WEB_VALIDATION.md`; `project_docs/coordination/VALIDATE-WEB-ROBUST-FORECAST-V1-001.md`.
- Upstream inputs: `WEB-ROBUST-FORECAST-V1-001` release candidate and validated model build `b5c625a6edb0a7c238fb`.
- Expected outputs: PASS/FAIL release audit with exact reconciliation and test results.
- Warehouse mode: `read-only`
