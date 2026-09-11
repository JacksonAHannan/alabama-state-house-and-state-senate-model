# Task contract: VALIDATE-FORECAST-SOUTHERN-REGIME-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete` — PASS as a research tournament. The 2,402+1,188 source rows, unique keys, missing 2024 incumbency, temporal/recent-only isolation, exact metrics and guardrails, baseline-only selection, 96 zero-adjustment 2026 rows, hashes, determinism, and 5/5 tests all reconcile.
- Objective: Independently validate the regime-aware Southern margin tournament and baseline-only selection.
- Non-goals: No implementation, probability, warehouse, website, or publication changes.
- Upstream snapshot: `FORECAST-SOUTHERN-REGIME-REBUILD-001` review candidate.
- Read scope: Regime implementation/tests/outputs/method note; historical/recent input panels and current 2026 prospective inputs.
- Write scope: `project_docs/audits/SOUTHERN_REGIME_FORECAST_REBUILD_VALIDATION.md`; `project_docs/coordination/VALIDATE-FORECAST-SOUTHERN-REGIME-001.md`.
- Warehouse mode: `read-only`
- Inputs: Review-candidate artifacts and referenced versioned inputs.
- Outputs: PASS/FAIL audit with exact evidence and blockers.
- Acceptance checks: Temporary deterministic rebuild; verify 2,402+1,188 source counts and unique keys; preserve 2024 incumbency as missing; prove temporal isolation and recent-only minimum year; recompute all metrics/guardrails/selection; reconcile both 2026 views and zero selected adjustment; validate hashes and tests.
- Handoff recipient: `/root`; production promotion remains a separate serialized task.
- Known risks: Baseline-only winning is a substantive negative result, not a failed build; validation must not force model-view differentiation unsupported by data.
