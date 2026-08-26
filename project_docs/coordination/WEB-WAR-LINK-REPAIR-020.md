# Task contract: WEB-WAR-LINK-REPAIR-020

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`

## Handoff

- Renamed the forecast-page link in source and generated output to `Historical WAR model`.
- Rebuilt and themed the public candidate, methodology, navigation, and forecast pages.
- Workflow validation and all 19 focused/publication tests pass.
- The repaired candidate is ready for independent focused revalidation.
- Objective: Repair the sole blocking public naming inconsistency by renaming the forecast link to the historical candidate page from CMO to WAR.
- Acceptance checks: Source and generated forecast page say `Historical WAR model`; no public link identifies the WAR route as the CMO model; focused site tests pass.
- Read scope: Blocked audit `WEB_WAR_PAGE_VALIDATION.md`, current forecast builder, and current public pages.
- Write scope: `scripts/build_2026_forecast_dashboard.py`; `docs/index.html`; `artifacts/site/alabama-2026-legislative-forecast.html`; `artifacts/blue_oxblood_site/index.html`; `project_docs/coordination/WEB-WAR-LINK-REPAIR-020.md`; `project_docs/coordination/active_tasks.csv`.
- Upstream inputs: Blocked `VALIDATE-WEB-WAR-PAGE-019` audit and completed WAR release candidate.
- Expected outputs: Repaired local release candidate ready for focused revalidation.
- Warehouse mode: `read-only`
- Handoff recipient: `validation_release`.
