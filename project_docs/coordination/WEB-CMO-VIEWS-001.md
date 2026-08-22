# Task contract: WEB-CMO-VIEWS-001 CMO explorer measures and detail hierarchy

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Limit the CMO map to the three requested measures and place the selected legislator's name and CMO above the race/context wikiboxes.
- Non-goals: Recalculate CMO, change model inputs, or alter other public pages.
- Upstream snapshot: Current approved CMO v4 publication on `master`.
- Read scope: `scripts/build_war_story_page.py`; `data/processed/war/cmo_v4_candidates.csv`; existing CMO site tests.
- Write scope: `scripts/build_war_story_page.py`; `scripts/tests/test_cmo_story_historical_cycles.py`; `docs/cmo.html`; `artifacts/site/alabama-legislative-cmo.html`; `artifacts/site/alabama-legislative-war-legacy.html`; `project_docs/coordination/WEB-CMO-VIEWS-001.md`; `project_docs/coordination/active_tasks.csv`.
- Warehouse mode: `read-only`
- Inputs: Approved CMO v4 candidate and district payloads.
- Outputs: Rebuilt CMO page with three map measures and revised detail hierarchy.
- Acceptance checks: `python scripts/build_war_story_page.py`; `python scripts/build_blue_oxblood_site.py`; `python -m pytest scripts/tests/test_cmo_story_historical_cycles.py scripts/tests/test_published_site_consistency.py scripts/tests/test_site_brand.py -q`; independent publication validation.
- Handoff recipient: `validation_release`
- Known risks: Generated-page copy transforms and responsive detail ordering could preserve stale controls or labels.
