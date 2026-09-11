# Task contract: VALIDATE-CMO-ALABAMA-SOUTHERN-PRIOR-V6-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete` — PASS as a historical research decomposition and valid negative promotion result. Alabama is excluded from all 2,350 prior-training rows; Direct CMO and decomposition identities, symmetry, penalty selection, metrics, named cases, hashes, determinism, and 5/5 tests reconcile. The model fails the 2018–2022 gate and remains rejected for direct 2026 use.
- Objective: Independently validate the Alabama CMO v6 Southern-prior research candidate and its non-promotion finding for 2026.
- Non-goals: No code, model, warehouse, website, or publication changes.
- Upstream snapshot: `CMO-ALABAMA-SOUTHERN-PRIOR-V6-001` review candidate.
- Read scope: V6 implementation/tests/outputs/method note; v5 reference outputs; validated Southern panel/tournament/manifests.
- Write scope: `project_docs/audits/CMO_ALABAMA_SOUTHERN_PRIOR_V6_VALIDATION.md`; `project_docs/coordination/VALIDATE-CMO-ALABAMA-SOUTHERN-PRIOR-V6-001.md`.
- Warehouse mode: `read-only`
- Inputs: Review-candidate files and immutable/versioned upstream model artifacts.
- Outputs: PASS/FAIL audit with exact evidence and blocking findings.
- Acceptance checks: Temporary deterministic rebuild; prove Alabama exclusion and 2,350 training rows; verify Direct CMO invariance, finite decomposition identities, candidate symmetry, selected quality penalty, cycle metrics, all-era improvement and 2018–22 failure, named cases, hashes, and focused tests.
- Handoff recipient: `/root`, then `forecast_model` for a regime-aware tournament only after PASS.
- Known risks: The model is expected to fail the modern-era promotion gate; validation must distinguish a valid negative finding from an implementation failure.
