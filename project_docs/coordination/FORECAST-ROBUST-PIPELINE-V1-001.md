# Task contract: FORECAST-ROBUST-PIPELINE-V1-001

- Accountable role: `forecast_model`
- Owner: `/root`
- Status: `complete` — independently validated as research candidate, build `b5c625a6edb0a7c238fb`.
- Objective: Implement forecast steps 2–10 as one leakage-safe modern Southern research pipeline and produce a 2026 headline candidate plus explicit scenarios.
- Non-goals: No canonical warehouse, docs website, or live publication changes.
- Upstream inputs: Validated 1,188-race 2018–2024 Southern panel; validated 323-race 2024 incumbency staging; current 2026 poll/demographic baseline, roster, candidate history, and Alabama finance scenarios.
- Read scope: Referenced model/staging artifacts and current forecast utilities/inputs.
- Write scope: `scripts/run_robust_forecast_pipeline.py`; `scripts/tests/test_robust_forecast_pipeline.py`; `data/processed/forecast_calibration/robust_forecast_v1_*`; `data/processed/war/robust_forecast_v1_*`; `project_docs/model/ROBUST_FORECAST_V1.md`; `project_docs/coordination/FORECAST-ROBUST-PIPELINE-V1-001.md`.
- Warehouse mode: `read-only`
- Outputs: Modern panel with pre-election features; forward predictions and tournament; probability-family validation; shared-error decomposition; subgroup calibration; finance-coverage gate; 2026 headline/scenarios and simulations; deterministic manifest.
- Acceptance checks: Strict earlier-cycle training and feature construction; 2024 unresolved incumbency stays missing; demographic/incumbency/prior-quality stages are nested; finance is promoted only with comparable cross-state cutoff coverage; selected margin model follows fixed guardrails; probability uses out-of-sample margins; shared components reconcile total error; subgroup audits include state/chamber/margin/incumbency/demographic type; scenarios never replace headline selection; keys/hashes/tests pass.
- Handoff recipient: `validation_release`, then a separate web-product task if approved.
- Known risks: Only four modern states and three validation cycles; incomplete 2024 incumbency; no comparable multi-state finance mart; candidate identities are source-local rather than canonical.
