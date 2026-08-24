# Task contract: WEB-IDEOLOGY-CQI-CORRECTION-001 correct ideology-page CQI

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Replace the post-2016-invalid Southern structural residual in the merged ideology/caucus page with the validated cycle-centered, partial-pooled Candidate Quality Index used by the CMO model.
- Non-goals: Do not refit CMO, alter ideology classifications or clusters, change raw federal/presidential comparisons, or publish warehouse changes.
- Upstream snapshot: `data/processed/war/cmo_v5_candidates.csv` and current repaired Democratic cluster membership at commit `f4272df`.
- Read scope: `data/processed/war/cmo_v5_candidates.csv`; `research/cmo_ideology/democratic_clusters/`; `scripts/build_democratic_transition_page.py`; `scripts/tests/test_ideology_performance_page.py`; current site builders and generated pages.
- Write scope: `scripts/build_democratic_transition_page.py`; `scripts/tests/test_ideology_performance_page.py`; `artifacts/site/ideology-performance.html`; `artifacts/blue_oxblood_site/ideology-performance.html`; `docs/ideology-performance.html`; `docs/index.html`; `project_docs/coordination/WEB-IDEOLOGY-CQI-CORRECTION-001.md`; `project_docs/coordination/active_tasks.csv`.
- Warehouse mode: `read-only`
- Inputs: Validated `candidate_quality_index` keyed by `canonical_candidate_id`, current cluster assignments, and existing raw federal/presidential outcomes.
- Outputs: A rebuilt ideology page whose quality views, summaries, cases, details, and table consistently report CQI; the normal site rebuild also advances the forecast staleness display to the current date without changing its model payload.
- Acceptance checks: `python scripts/validate_agent_workflow.py`; `python scripts/build_blue_oxblood_site.py`; `python -m pytest scripts/tests/test_ideology_performance_page.py scripts/tests/test_published_site_consistency.py scripts/tests/test_site_brand.py -q`; post-2016 Democratic bloc check shows traditionalist mean CQI positive and progressive mean near zero; no public ideology-page label calls the Southern residual CQI.
- Handoff recipient: `validation_release`
- Known risks: CQI is retrospective and partially pooled; the post-2016 traditionalist sample has four candidate-cycles; the Shor-McCarty post-2016 Democratic regression remains underpowered and must remain labeled not estimated.

## Handoff

- Independent validation: `PASS` in `project_docs/audits/IDEOLOGY_CQI_CORRECTION_VALIDATION.md`.
- Changed source: `scripts/build_democratic_transition_page.py` and its focused page tests.
- Generated output: staged, themed, and published ideology pages; the normal full-site rebuild advanced the forecast freshness counter by one day.
- Caveats: Modern traditionalist CQI has four candidate-cycles; the separate modern Shor–McCarty estimate remains underpowered and is not estimated.
- Downstream action: Safe to commit and publish.
