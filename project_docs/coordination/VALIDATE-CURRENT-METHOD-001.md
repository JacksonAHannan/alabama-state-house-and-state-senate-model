# Task contract: VALIDATE-CURRENT-METHOD-001 — independent release validation

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Verdict: `PASS`
- Handoff: Release candidate approved for orchestrator publication/release handling.
- Objective: Independently validate the reconciled CMO v6 decomposition, robust forecast, public labels, provenance, and live-release candidate.
- Non-goals: Do not implement model or UI changes and do not approve failed mandatory gates by caveat.
- Upstream snapshot: CMO-V6-PROMOTION-001, FORECAST-CURRENT-METHOD-001, and WEB-CURRENT-METHOD-001 review candidates.
- Read scope: `scripts/rebuild_cmo_southern_prior_v6.py`; `scripts/run_robust_forecast_pipeline.py`; `data/processed/war/cmo_v5_*`; `data/processed/war/cmo_v6_southern_*`; `data/processed/forecast_calibration/robust_forecast_v1_*`; `scripts/build_war_story_page.py`; `scripts/build_2026_forecast_dashboard.py`; `docs/`; relevant tests and methodology documents.
- Write scope: `project_docs/audits/CURRENT_METHOD_RELEASE_VALIDATION.md`; `project_docs/coordination/VALIDATE-CURRENT-METHOD-001.md`.
- Warehouse mode: `read-only`
- Inputs: Complete publication candidate and its versioned upstream artifacts.
- Outputs: Independent pass/fail report with model invariants, provenance checks, page/runtime checks, and caveats.
- Acceptance checks: Rebuilds are deterministic; Direct CMO invariant holds; forecast headline and probabilities reconcile; current-method labels are accurate; focused and publication tests pass; responsive browser smoke test passes.
- Handoff recipient: `orchestrator`
- Known risks: Unrelated dirty worktree files must not be mistaken for release inputs.
