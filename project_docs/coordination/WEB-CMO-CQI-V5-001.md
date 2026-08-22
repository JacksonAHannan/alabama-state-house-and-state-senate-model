# Task contract: WEB-CMO-CQI-V5-001

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Replace the public CMO v4 explorer and methodology with the validated v5 dual-estimand product, clearly separating observed ticket overperformance from partially pooled candidate quality.
- Non-goals: Change canonical election returns, candidate identities, the 2026 forecast, ideology classifications, or candidate-quality estimation.
- Upstream snapshot: Validated `CMO-CQI-V5-001` release candidate.
- Read scope: `data/processed/war/cmo_v5_*.csv`; `data/processed/elections/canonical_cmo_features.csv`; existing map, race-name, office-baseline, site-theme, and CMO page builders.
- Write scope: `scripts/build_war_story_page.py`; `scripts/tests/test_cmo_story_historical_cycles.py`; `scripts/tests/test_published_site_consistency.py`; `artifacts/site/alabama-legislative-cmo.html`; `artifacts/site/alabama-legislative-war-legacy.html`; `docs/cmo.html`; `docs/cmo-methodology.html`; `docs/data/cmo_v5_*.csv`; `docs/data/cmo_methodology_v5.md`; `project_docs/coordination/WEB-CMO-CQI-V5-001.md`; `project_docs/coordination/active_tasks.csv`.
- Warehouse mode: `read-only`
- Inputs: Approved v5 race/candidate/effect/tournament/diagnostic/provenance outputs and existing geographic/context presentation inputs.
- Outputs: Rebuilt CMO explorer, methodology page, publication exports, and focused tests.
- Acceptance checks: The default CMO map and ranking use direct candidate-oriented CMO; Candidate Quality is separately labeled with interval, status, reliability, appearances, and time-safe pre-election estimate; raw governor and prior-presidential views remain available; no v4 structural-residual claims or v4 publication links remain; Mike Curtis displays positive direct CMO and uncertain CQI; arithmetic and publication-copy tests pass; blue/oxblood visual and accessibility checks pass.
- Handoff recipient: `validation_release`
- Known risks: Sparse repeat-candidate evidence, fallback baseline comparability, unresolved historical identities, and large candidate-quality intervals must remain visible rather than suppressed.
