# Task contract: WEB-CAUCUS-REMOVE-3D-001

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Remove the three-dimensional three-issue caucus visualization and retain the all-issue constellation as the sole spatial view.
- Non-goals: Change clustering, constellation coordinates, ideological evidence, or CMO.
- Upstream snapshot: Validated constellation release at commit `4858cbe`.
- Read scope: Current caucus page builder, generated page, and focused tests.
- Write scope: `scripts/build_caucus_analysis_page.py`; `scripts/tests/test_caucus_analysis_page.py`; `artifacts/site/caucuses.html`; `docs/caucuses.html`; `project_docs/coordination/WEB-CAUCUS-REMOVE-3D-001.md`; `project_docs/coordination/active_tasks.csv`.
- Warehouse mode: `read-only`
- Inputs: Current validated caucus page.
- Outputs: Simplified constellation-only caucus page and tests.
- Acceptance checks: No 3D markup, controls, event handlers, styles, or explanatory copy remain; constellation interactions and party/era updates still work; focused tests and independent browser validation pass.
- Handoff recipient: `validation_release`
- Known risks: Removal must not break shared candidate selection or tooltip behavior.
