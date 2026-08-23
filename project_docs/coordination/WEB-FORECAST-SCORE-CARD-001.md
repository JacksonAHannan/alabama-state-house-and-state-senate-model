# Task contract: WEB-FORECAST-SCORE-CARD-001 — compact forecast accuracy card

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Remove the empty two-card space beside the single published 2022 holdout MAE metric and publish the corrected responsive layout.
- Acceptance checks: The score container has one column at desktop and mobile widths; no empty metric slots, horizontal overflow, or forecast interaction regressions; focused tests and site build pass; independent release validation approves the rendered page.
- Read scope: `dashboard/forecast_dashboard.css`; `scripts/build_2026_forecast_dashboard.py`; current forecast page and web tests.
- Write scope: `dashboard/forecast_dashboard.css`; `docs/index.html`; `docs/methodology.html`; `project_docs/coordination/WEB-FORECAST-SCORE-CARD-001.md`.
- Upstream inputs: Published headline forecast build `e178fb3f50c98c9c312b` at commit `2a8e416`.
- Expected outputs: A compact one-card accuracy display and rebuilt public forecast page.
- Warehouse access: read-only.
- Handoff recipient: `validation_release`.

## Handoff

- Rebuilt the forecast and methodology pages with a one-track, 150px accuracy container at every breakpoint.
- Focused web tests passed 27/27.
- Independent browser validation `VALIDATE-FORECAST-SCORE-CARD-001` returned PASS at 1280px, 497px, and 390px.
