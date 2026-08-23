# Task contract: WEB-IDEOLOGY-QUALITY-LABEL-001 — ideology outcome terminology repair

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Replace the stale CMO outcome on the combined ideology/caucus page with the current v6 candidate-quality residual and make every analytical label and explanation match the field actually displayed.
- Non-goals: Refit the v6 CMO model, change ideology or caucus assignments, change federal/presidential comparison formulas, or publish warehouse tables.
- Upstream snapshot: Commit `c1f9fe4`; `data/processed/war/cmo_v6_southern_candidates.csv`; current Democratic cluster membership and ideology analysis outputs.
- Read scope: `data/processed/war/cmo_v6_southern_candidates.csv`; `research/cmo_ideology/`; `scripts/build_caucus_analysis_page.py`; current public page and methodology.
- Write scope: `scripts/build_democratic_transition_page.py`; `scripts/tests/test_ideology_performance_page.py`; `artifacts/site/ideology-performance.html`; `artifacts/blue_oxblood_site/ideology-performance.html`; `docs/ideology-performance.html`; `project_docs/coordination/WEB-IDEOLOGY-QUALITY-LABEL-001.md`; `project_docs/coordination/active_tasks.csv`
- Warehouse mode: `read-only`
- Inputs: Current v6 candidate output keyed by `canonical_candidate_id`; issue-only cluster assignments; current federal and presidential candidate-oriented comparisons.
- Outputs: Rebuilt combined ideology/caucus page with current candidate-quality residual values, recalculated bloc summaries, precise labels, and regression tests preventing CMO/residual conflation.
- Acceptance checks: `python scripts/validate_agent_workflow.py`; `python scripts/build_blue_oxblood_site.py`; `python -m pytest scripts/tests/test_ideology_performance_page.py scripts/tests/test_published_site_consistency.py scripts/tests/test_site_brand.py -q`; all cluster members join exactly once to v6 candidate rows; no analytical control, card, tooltip, or table labels the residual as CMO.
- Handoff recipient: `validation_release`
- Known risks: The candidate-quality residual is a race-level candidate-versus-opponent quantity, not Direct CMO or the career-pooled quality index; navigation references to the separate CMO product must remain distinguishable from analytical outcome labels.
