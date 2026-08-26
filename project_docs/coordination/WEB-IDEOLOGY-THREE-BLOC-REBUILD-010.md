# Task contract: WEB-IDEOLOGY-THREE-BLOC-REBUILD-010 comprehensive page rebuild

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Replace the inherited two-bloc ideology/caucus presentation with a coherent three-group page whose text, payload, graphics, interactions, and methods all use the current traditionalist-populist, bridge-coalition, and progressive-modern clustering solution.
- Non-goals: Do not refit clusters, alter CMO/CQI, change raw or canonical data, publish `docs/`, or imply that descriptive clusters are formal caucuses or causal treatments.
- Upstream snapshot: Completed `IDEOLOGY-DOWNSTREAM-RERUN-006` and `IDEOLOGY-CAUCUS-RERUN-007` outputs dated 2026-08-24; repaired Ballotpedia, Vote Smart, interest-group, public-position, and legislative evidence already integrated into the current issue mart.
- Read scope: `research/cmo_ideology/absolute_rebuild_`; `research/cmo_ideology/democratic_clusters/`; `data/processed/war/cmo_v5_candidates.csv`; `data/processed/ideology/candidate_position_evidence_v3_all_sources.csv`; current blue/oxblood site components and page tests.
- Write scope: `scripts/build_democratic_transition_page_v2.py`; `scripts/build_democratic_transition_page.py`; `scripts/tests/test_ideology_performance_page.py`; `scripts/tests/test_caucus_analysis_page.py`; `artifacts/site/ideology-performance.html`; `project_docs/coordination/WEB-IDEOLOGY-THREE-BLOC-REBUILD-010.md`; `project_docs/coordination/active_tasks.csv`
- Warehouse mode: `read-only`
- Inputs: Current 311-member cluster panel, three-cluster profiles, CQI v5, federal and presidential overperformance, absolute Shor–McCarty estimates, and source/evidence coverage.
- Outputs: A self-contained local HTML page with three-group summary, within-context contrasts, transition, issue profiles, distributions, cycle trends, issue explorer, representative cases, similarity map, candidate table, continuous-ideology context, and methods.
- Acceptance checks: Builder succeeds; all focused page and clustering tests pass; all Democratic graphics and legends contain three groups; endpoint-only estimates are explicitly labeled; no stale two-group, CMO, undefined-era, 3D, or Candidate Atlas artifacts remain; current values and source counts agree with upstream files.
- Handoff recipient: `validation_release` if publication is requested.
- Known risks: The three-group solution has modest silhouette despite good bootstrap stability; historical evidence is selected toward officeholders; group composition changes across eras; only within-context comparisons should be interpreted as adjusted contrasts.

## Handoff

- Changed files: `scripts/build_democratic_transition_page_v2.py`, `scripts/build_democratic_transition_page.py`, `scripts/tests/test_ideology_performance_page.py`, this contract, and `project_docs/coordination/active_tasks.csv`.
- Generated output: `artifacts/site/ideology-performance.html` (local release candidate only).
- Rebuilt sections: three-group summary; pairwise within-context contrasts; cycle composition; issue profiles; candidate distributions; cycle trends; issue explorer; representative cases; two-dimensional similarity map and candidate table; continuous Shor-McCarty context; evidence coverage and methods.
- Acceptance results: builder completed; 19 focused page, compatibility, and brand tests passed; the single inline script passed `node --check`; headless Chrome rendered desktop and mobile layouts with zero console errors; stale two-bloc, legacy CMO, undefined-era, 3D, Candidate Atlas, and CDN strings were absent.
- Caveats: The page remains descriptive; only pairwise common-context comparisons are adjusted, evidence availability is selected, and the current three-cluster silhouette is modest.
- Downstream action: If publication is requested, hand `artifacts/site/ideology-performance.html` to `validation_release` for independent review before writing `docs/`.
