# Task contract: WEB-IDEO-CQI-ERA-001 publish CQI era chart

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Replace the mislabeled raw-federal era cards with the newly estimated CQI-era slopes and make the chart text unambiguous.
- Non-goals: Do not alter the CQI estimates, Shor–McCarty inputs, clusters, other outcome selectors, CMO, forecast data, or warehouse state.
- Upstream snapshot: `IDEO-CQI-ERA-001` review candidate.
- Read scope: `research/cmo_ideology/absolute_rebuild_estimates.csv`; `scripts/build_ideology_thesis_page.py`; `scripts/build_democratic_transition_page.py`; current site build and page tests.
- Write scope: `scripts/build_ideology_thesis_page.py`; `scripts/build_democratic_transition_page.py`; `scripts/tests/test_ideology_performance_page.py`; `artifacts/site/ideology-performance.html`; `artifacts/blue_oxblood_site/ideology-performance.html`; `docs/ideology-performance.html`; `docs/index.html`; `project_docs/coordination/WEB-IDEO-CQI-ERA-001.md`; `project_docs/coordination/active_tasks.csv`.
- Warehouse mode: `read-only`
- Inputs: CQI era rows from the reviewed analysis output and the current merged ideology/caucus page.
- Outputs: Public era cards labeled CQI showing +9.0, +7.8, and Not estimated, with matching intervals and sample sizes.
- Acceptance checks: `python scripts/build_blue_oxblood_site.py`; `python -m pytest scripts/tests/test_ideology_performance_page.py scripts/tests/test_published_site_consistency.py scripts/tests/test_site_brand.py -q`; no era card is sourced from `candidate_federal_overperformance`; staged and published HTML contain the +7.8 CQI estimate and do not contain the former -2.5 card.
- Handoff recipient: `validation_release`
- Known risks: Generated single-line HTML; CQI is retrospective; the 2008–2014 interval crosses zero narrowly; post-2016 remains underpowered.

## Handoff

- Public era cards now use `candidate_quality_index` and render +9.0, +7.8, and Not estimated.
- The former raw-federal -2.5 row is absent from the public payload.
- Tests: combined analysis and publication suite passed 36 checks.
- Downstream action: independent validation of the analysis reconstruction, page labels, and rendered cards.
