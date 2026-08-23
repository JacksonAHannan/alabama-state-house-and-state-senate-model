# Task contract: WEB-CURRENT-METHOD-001 — publish reconciled CMO and forecast methods

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Handoff: Independently validated under `VALIDATE-CURRENT-METHOD-001`; approved for publication.
- Objective: Rebuild the CMO and forecast pages from the approved current artifacts, remove stale labels and documentation, and prepare a coherent publication candidate.
- Non-goals: Do not modify model estimates in the presentation layer or read upstream inputs from `docs/`.
- Upstream snapshot: Approved CMO-V6-PROMOTION-001 and FORECAST-CURRENT-METHOD-001 outputs.
- Read scope: `data/processed/war/cmo_v6_southern_*`; `data/processed/forecast_calibration/robust_forecast_v1_*`; current site builders and theme assets.
- Write scope: `scripts/build_war_story_page.py`; `scripts/build_2026_forecast_dashboard.py`; `scripts/build_blue_oxblood_site.py`; `artifacts/site/`; `docs/`; `project_docs/coordination/WEB-CURRENT-METHOD-001.md`.
- Warehouse mode: `read-only`
- Inputs: Versioned model outputs and canonical methodology documents only.
- Outputs: Rebuilt CMO, forecast, methodology pages, compact publication exports, and compatibility links.
- Acceptance checks: Site tests pass; Direct CMO matches v5/v6; v6 decomposition is labeled historical; forecast headline remains robust-v1; no legacy 80/20 or ambiguous historical-CMO text remains; pages render without runtime or contrast failures.
- Handoff recipient: `validation_release`
- Known risks: `docs/` is serialized publication output and must be regenerated only after both model tasks complete.
