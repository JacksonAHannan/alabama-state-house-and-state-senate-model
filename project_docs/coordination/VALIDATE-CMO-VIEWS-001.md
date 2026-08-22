# Task contract: VALIDATE-CMO-VIEWS-001 CMO explorer release validation

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently verify the three CMO map measures, default state, detail hierarchy, responsiveness, and publication consistency.
- Non-goals: Change model data, page implementation, or public outputs.
- Upstream snapshot: `WEB-CMO-VIEWS-001` release candidate.
- Read scope: `scripts/build_war_story_page.py`; `docs/cmo.html`; `artifacts/site/alabama-legislative-cmo.html`; relevant tests.
- Write scope: `project_docs/audits/CMO_VIEWS_VALIDATION.md`; `project_docs/coordination/VALIDATE-CMO-VIEWS-001.md`; `project_docs/coordination/active_tasks.csv`.
- Warehouse mode: `read-only`
- Inputs: Rebuilt CMO page and approved CMO v4 payload.
- Outputs: Independent pass/fail validation report.
- Acceptance checks: Exactly three visible map controls; absolute CMO default; governor and previous-presidential raw views functional; legislator name and CMO precede both wikiboxes; desktop and narrow layouts readable; focused tests pass.
- Handoff recipient: `web_product`
- Known risks: Generated HTML transformations may differ from builder source; visual ordering may fail at narrow widths.
