# Task contract: WEB-CAUCUS-CONSTELLATION-001

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Replace the primary three-dimensional caucus chart with a two-dimensional all-issue ideological-distance constellation that clearly depicts empirical groupings and evidence coverage, while retaining the literal three-issue chart as a secondary view.
- Non-goals: Refit caucus membership, change canonical ideology evidence, claim causal effects, or manufacture visual separation unsupported by the fitted issue space.
- Upstream snapshot: Validated caucus explorer and three-issue view at commit `327375e`.
- Read scope: `research/cmo_ideology/democratic_clusters/`; `scripts/analyze_democratic_ideological_clusters.py`; current caucus page builder and tests.
- Write scope: `scripts/build_caucus_analysis_page.py`; `scripts/tests/test_caucus_analysis_page.py`; `artifacts/site/caucuses.html`; `docs/caucuses.html`; `project_docs/coordination/WEB-CAUCUS-CONSTELLATION-001.md`; `project_docs/coordination/active_tasks.csv`.
- Warehouse mode: `read-only`
- Inputs: Validated candidate-cycle cluster assignments and the party-specific issue matrices used to fit them.
- Outputs: Deterministic all-issue constellation coordinates, cluster envelopes and centroids, coverage encoding, interactive view tabs, candidate inspection, and regenerated public page.
- Acceptance checks: Every classified candidate-cycle has deterministic finite coordinates derived only from its party's clustering issue matrix; cluster colors, centroids, and envelopes agree with assignments; point size/opacity disclose evidence coverage; party and era filters update the view; the secondary three-issue view remains functional; desktop and 497px layouts do not overflow; focused tests and independent browser validation pass.
- Handoff recipient: `validation_release`
- Known risks: A two-dimensional projection loses information; cluster envelopes can overlap where empirical structure is weak; candidate-cycle repetition and imputation must remain disclosed.
