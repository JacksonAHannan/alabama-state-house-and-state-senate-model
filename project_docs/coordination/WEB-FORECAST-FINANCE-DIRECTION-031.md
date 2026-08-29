# Task contract: WEB-FORECAST-FINANCE-DIRECTION-031 forecast finance presentation repair

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Rebuild the local forecast dashboard and methodology candidate from the repaired direct relative-fundraising headline without stale residualized-finance language or values.
- Non-goals: Model refitting, candidate-finance matching, warehouse writes, or publication to `docs/` before independent validation.
- Upstream snapshot: `FORECAST-FINANCE-DIRECTION-030` release candidate build `8cad753f1720c2a1b107`.
- Read scope: `data/processed/forecast_calibration/post2016_headline_v1_*`; `data/processed/forecast_calibration/post2016_polling_cmo_*`; current dashboard assets and tests; `docs/` as comparison only.
- Write scope: `scripts/build_2026_forecast_dashboard.py`; `artifacts/site/alabama-2026-legislative-forecast.html`; `artifacts/site/forecast-methodology.html`; `project_docs/coordination/WEB-FORECAST-FINANCE-DIRECTION-031.md`.
- Warehouse mode: `read-only`
- Inputs: Repaired headline scenario, manifest, historical metrics, bootstrap comparison, current maps/assets.
- Outputs: Local forecast and methodology release-candidate HTML files with a publication-disabled build mode.
- Acceptance checks: `python scripts/validate_agent_workflow.py`; `python scripts/build_2026_forecast_dashboard.py --artifact-only`; embedded payload build ID equals the repaired manifest; SD-7 displays the reconciled totals and a Republican-favoring finance step; page methodology names direct observed relative fundraising; dashboard tests pass against the staged artifact where applicable.
- Handoff recipient: `validation_release`
- Known risks: Existing dashboard builder historically writes directly to `docs/`; the new artifact-only gate must not change the normal publication path.
