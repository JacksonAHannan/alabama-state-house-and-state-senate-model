# Task contract: WEB-CMO-V3-001

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Publish CMO v3 and rebuilt ideology results with no obsolete context-CMO labels or payload fields.
- Acceptance checks: CMO page reconciles Morrow to +0.51; downloads are v3; methodology defines direct CMO; ideology payload reconciles to v3; focused site tests pass.
- Read scope: Validated CMO v3 and rebuilt ideology outputs; existing site builders.
- Write scope: `scripts/build_war_story_page.py`; `scripts/tests/test_cmo_story_historical_cycles.py`; `scripts/tests/test_published_site_consistency.py`; `docs/cmo.html`; `docs/cmo-methodology.html`; `docs/ideology-performance.html`; `docs/data/cmo_v3_*`; `artifacts/site/`; this contract; its ledger row.
- Upstream inputs: `CMO-DIRECT-ESTIMAND-001`; `IDEO-CMO-V3-001` review candidates.
- Expected outputs: Rebuilt CMO, methodology, and ideology public pages and v3 downloads.
- Warehouse mode: read-only.
- Handoff recipient: `validation_release`.
