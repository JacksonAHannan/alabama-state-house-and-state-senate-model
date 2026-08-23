# Task contract: FORECAST-CURRENT-METHOD-001 — reconcile the current forecast method

- Accountable role: `forecast_model`
- Owner: `/root`
- Status: `complete`
- Objective: Make the robust-v1 forecast pipeline reproducible and ensure every public scenario uses a current, accurately labeled methodology.
- Non-goals: Do not promote v6 CMO into the headline forecast, refit election observations, or add finance without comparable cross-state coverage.
- Upstream snapshot: Robust forecast build `b5c625a6edb0a7c238fb` and validated CMO v6 historical decomposition.
- Read scope: `data/processed/forecast_calibration/robust_forecast_v1_*`; `data/processed/war/cmo_v6_southern_*`; `project_docs/model/ROBUST_FORECAST_V1.md`; current prospective forecast inputs listed in the manifest.
- Write scope: `scripts/run_robust_forecast_pipeline.py`; `data/processed/forecast_calibration/robust_forecast_v1_*`; `project_docs/model/ROBUST_FORECAST_V1.md`; `project_docs/methodology/FORECAST_METHODOLOGY.md`; `project_docs/coordination/FORECAST-CURRENT-METHOD-001.md`.
- Warehouse mode: `read-only`
- Inputs: Current 2026 poll-adjusted baseline, certified roster, modern Southern panel, v6 historical decomposition, and probability-calibration inputs.
- Outputs: Reproducible robust forecast run, current scenario labels/definitions, manifest, and one canonical forecast methodology document.
- Acceptance checks: Headline margins and selected probability family remain reproducible; no scenario is mislabeled as current CMO; manifest hashes all controlling code and data; forecast tests pass.
- Handoff recipient: `web_product`
- Known risks: Updating a comparison scenario can change only that scenario; it must not silently alter the validated headline.
