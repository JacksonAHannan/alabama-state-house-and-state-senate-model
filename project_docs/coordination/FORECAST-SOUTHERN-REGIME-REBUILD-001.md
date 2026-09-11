# Task contract: FORECAST-SOUTHERN-REGIME-REBUILD-001

- Accountable role: `forecast_model`
- Owner: `/root`
- Status: `complete`
- Objective: Build a regime-aware Southern expected-margin tournament using both the validated 1994–2016 panel and the existing 1,188-race 2018–2024 panel, then produce non-public 2026 Basic and Fundamentals+ research margins.
- Non-goals: No canonical warehouse, probability promotion, website, docs publication, or live forecast changes.
- Upstream snapshot: Validated historical Southern panel; staged recent Southern probability panel; current 2026 poll-adjusted prospective features.
- Read scope: Historical/recent Southern panels and manifests; current 2026 baseline/features/incumbency; existing forecast tournament utilities.
- Write scope: `scripts/run_southern_regime_forecast_rebuild.py`; `scripts/tests/test_southern_regime_forecast_rebuild.py`; `data/processed/war/forecast_regime_v1_*`; `project_docs/model/SOUTHERN_REGIME_FORECAST_REBUILD.md`; `project_docs/coordination/FORECAST-SOUTHERN-REGIME-REBUILD-001.md`.
- Warehouse mode: `read-only`
- Inputs: 2,402 historical Southern races, 1,188 recent Southern races, and the current 2026 national-environment baseline.
- Outputs: Normalized modeling panel, leakage-safe forward predictions/metrics/ranking, selected expected-gap model, 2026 Basic/Fundamentals+ research margins, and deterministic manifest.
- Acceptance checks: Source eras remain explicit; no missing value becomes zero; each forward fold trains strictly earlier years; recent-only models use no pre-2018 rows; selection is based only on prespecified 2020/2022/2024 metrics and guardrails; 2026 margins reconcile to baseline plus 20%/100% selected adjustment; keys are unique; tests pass.
- Handoff recipient: `validation_release`, then probability recalibration only after PASS.
- Known risks: The 2018 break cannot be predicted from pre-2018 data; source baseline definitions differ; recent panel covers four states and even-year cycles only.
