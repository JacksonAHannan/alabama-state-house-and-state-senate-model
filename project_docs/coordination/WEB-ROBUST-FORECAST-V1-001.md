# Task contract: WEB-ROBUST-FORECAST-V1-001

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete` — independently validated for publication, build `b5c625a6edb0a7c238fb`.
- Objective: Replace the legacy Basic/Fundamentals+ public forecast with independently validated robust-forecast-v1 headline and scenario views, including full-chamber accounting and current methodology.
- Acceptance checks: The site reads only validated robust-v1 publication inputs; all 105 House and 35 Senate districts appear; modeled contests reconcile to the 48-district research output; fixed single-major-party seats are included in chamber summaries; headline probabilities and correlated simulations use the validated outputs; scenarios are labeled non-headline; methodology and labels contain no legacy normal-six-point or 20/100 CMO claims; map, district selection, tables, downloads, accessibility, and theme tests pass.
- Read scope: `data/processed/forecast_calibration/robust_forecast_v1_*`; validated 2026 roster/incumbency/finance/polling inputs; current forecast builder, dashboard assets, and site tests.
- Write scope: `scripts/build_2026_forecast_dashboard.py`; `dashboard/forecast_dashboard.js`; `scripts/tests/test_forecast_dashboard.py`; `scripts/tests/test_published_site_consistency.py`; `artifacts/site/alabama-2026-legislative-forecast.html`; `docs/index.html`; `docs/methodology.html`; `docs/data/robust_forecast_v1_*`; `project_docs/coordination/WEB-ROBUST-FORECAST-V1-001.md`.
- Upstream inputs: Validated robust forecast build `b5c625a6edb0a7c238fb`; validated 2024 Southern incumbency staging; current 2026 Alabama roster and map files.
- Expected outputs: Release-candidate forecast page, methodology page, and versioned public forecast downloads.
- Warehouse mode: `read-only`
- Handoff recipient: `validation_release`; `docs/` publication is not approved until independent validation passes.
