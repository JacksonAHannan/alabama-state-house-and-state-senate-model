# Task contract: WEB-IDEOLOGY-LOCAL-RERUN-009 local ideology page rebuild

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Rebuild the local merged ideology/caucus page from repaired hypothesis and three-cluster outputs, including an honest bridge-coalition display and no stale two-cluster assumptions.
- Non-goals: Do not modify or publish `docs/`; do not change analysis results; do not describe descriptive clusters as causal or formal caucus membership.
- Upstream snapshot: Completed `IDEOLOGY-DOWNSTREAM-RERUN-006` and `IDEOLOGY-CAUCUS-RERUN-007` outputs dated 2026-08-24; current CMO v4 and CQI v5.
- Read scope: `research/cmo_ideology/absolute_rebuild_`; `research/cmo_ideology/democratic_clusters/`; `data/processed/war/cmo_v5_candidates.csv`; current site theme and page builders.
- Write scope: `scripts/build_democratic_transition_page.py`; `scripts/tests/test_caucus_analysis_page.py`; `scripts/tests/test_ideology_performance_page.py`; `artifacts/site/ideology-performance.html`; `project_docs/coordination/WEB-IDEOLOGY-LOCAL-RERUN-009.md`; `project_docs/coordination/active_tasks.csv`
- Warehouse mode: `read-only`
- Inputs: Fresh issue estimates, absolute-ideology analysis, cluster membership/profiles/diagnostics, and current CQI.
- Outputs: Local `artifacts/site/ideology-performance.html` and compatibility-tested page payload.
- Acceptance checks: Page builder succeeds; focused ideology/caucus tests pass; payload has three uniquely labeled Democratic clusters, 18 current dimensions, no undefined era, current CQI values, and no stale `candidate_cmo` label in public analytical copy.
- Handoff recipient: `validation_release` if the user later requests live publication.
- Known risks: The public thesis focuses on the traditionalist-versus-progressive endpoint contrast while the empirical fit now includes a bridge coalition; copy and legends must make that distinction explicit.

## Handoff

- Rebuilt the local merged page at `artifacts/site/ideology-performance.html`; `docs/` was not touched.
- The transition, distribution, constellation, legends, and candidate table now display traditionalist-populist, bridge-coalition, and progressive-modern Democrats separately.
- The endpoint headline remains a within-cycle/chamber traditionalist-versus-progressive comparison and explicitly says the bridge group is not folded into either endpoint.
- The payload contains 311 candidate-cycles (131 Democratic), 18 Democratic clustering dimensions, unique cluster labels, current CQI values, and no undefined era or stale `candidate_cmo` field.
- The combined final gate passed: frontier integration 12/12 and 44 focused tests.
- Publication remains unrequested and requires independent validation before any `docs/` write.
