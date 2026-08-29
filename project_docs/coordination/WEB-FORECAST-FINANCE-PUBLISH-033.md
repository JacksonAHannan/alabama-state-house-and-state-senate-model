# Task contract: WEB-FORECAST-FINANCE-PUBLISH-033 publish validated finance-direction repair

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Refresh the repository's publication outputs from the independently approved direct relative-fundraising forecast build.
- Non-goals: Further model, finance, warehouse, or unrelated site changes; remote Git publication.
- Upstream snapshot: Approved `VALIDATE-FORECAST-FINANCE-DIRECTION-032` build `8cad753f1720c2a1b107`.
- Read scope: Approved forecast/model outputs and local web release candidate; existing `docs/` publication tree.
- Write scope: `docs/`; `project_docs/coordination/WEB-FORECAST-FINANCE-PUBLISH-033.md`.
- Warehouse mode: `read-only`
- Inputs: Validated staged forecast and methodology, headline CSVs/manifest, current site data exports.
- Outputs: Refreshed `docs/index.html`, `docs/methodology.html`, and forecast data downloads.
- Acceptance checks: `python scripts/build_2026_forecast_dashboard.py`; focused forecast tests; published-site consistency tests; published build ID equals `8cad753f1720c2a1b107`; published SD-7 fundraising effect is Republican-favoring and receipts match the reconciled source.
- Handoff recipient: `orchestrator`
- Known risks: The repository has unrelated dirty work; publication must modify only forecast-owned `docs/` files and copied forecast data.
