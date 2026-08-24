# Task contract: WEB-IDEOLOGY-CASE-SELECTION-001 — representative caucus case repair

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Select each bloc's representative case by proximity to that bloc's current v6 candidate-quality-residual median rather than by proximity to its federal-overperformance median.
- Non-goals: Change cluster membership, quality-residual calculations, the upper-decile federal case, or any model output.
- Upstream snapshot: Commit `41ef2ea`; current v6 candidate-quality residual and combined ideology/caucus page.
- Read scope: `data/processed/war/cmo_v6_southern_candidates.csv`; `research/cmo_ideology/democratic_clusters/`; current page builder and tests.
- Write scope: `scripts/build_democratic_transition_page.py`; `scripts/tests/test_ideology_performance_page.py`; `artifacts/site/ideology-performance.html`; `artifacts/blue_oxblood_site/ideology-performance.html`; `docs/ideology-performance.html`; `project_docs/coordination/WEB-IDEOLOGY-CASE-SELECTION-001.md`; `project_docs/coordination/active_tasks.csv`
- Warehouse mode: `read-only`
- Inputs: Current cluster members, current candidate-quality residual, and raw federal/presidential comparisons.
- Outputs: Representative traditionalist and progressive case cards aligned with the quality-residual median and explicit selection labels.
- Acceptance checks: `python scripts/validate_agent_workflow.py`; focused page tests; each representative minimizes absolute distance to its bloc-wide residual median among candidates with complete federal comparison; White is no longer labeled representative of the traditionalist residual median.
- Handoff recipient: `validation_release`
- Known risks: Requiring a federal comparison for a three-metric case card can exclude the mathematically closest candidate; selection must therefore compare eligible candidates to the full bloc median and disclose the criterion.
