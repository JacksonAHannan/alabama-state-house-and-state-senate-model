# Task contract: WEB-IDEOLOGY-HEADLINE-CONTEXT-001

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Replace the ideology page's era-confounded pooled bloc means with a coherent within-cycle-and-chamber comparison across CQI, federal-baseline overperformance, and previous-presidential overperformance.
- Non-goals: No changes to candidate cluster assignments, issue scores, CMO/CQI arithmetic, warehouse tables, raw evidence, or forecast outputs.
- Upstream snapshot: `master` commit `081ef85`; current `democratic_candidate_cluster_membership.csv` and `cmo_v5_candidates.csv` publication inputs.
- Read scope: `research/cmo_ideology/democratic_clusters/`; `data/processed/war/cmo_v5_candidates.csv`; current ideology page and tests.
- Write scope: `scripts/build_democratic_transition_page.py`; `scripts/tests/test_ideology_performance_page.py`; `artifacts/site/ideology-performance.html`; `docs/ideology-performance.html`; `project_docs/coordination/WEB-IDEOLOGY-HEADLINE-CONTEXT-001.md`; `project_docs/coordination/active_tasks.csv`.
- Warehouse mode: `read-only`
- Inputs: Current cluster membership, candidate-cycle performance measures, and current CQI values.
- Outputs: A cycle/chamber fixed-effect bloc-difference payload and a public forest-plot presentation with explicit support and uncertainty labels.
- Acceptance checks: headline uses only cycle/chamber strata containing both Democratic blocs; values are deterministic; clustered uncertainty is finite; no pooled group means are presented as adjusted bloc effects; `python -m pytest scripts/tests/test_ideology_performance_page.py -q`; full public site rebuild; workflow validation.
- Handoff recipient: `validation_release`
- Known risks: Sparse within-cycle overlap, repeated candidate identities, and confusing adjusted contrasts with causal effects. The page must label the result as descriptive and preserve raw candidate observations elsewhere.

## Completion handoff

- Replaced pooled, era-confounded group means with traditionalist-minus-progressive fixed-effect contrasts identified only within cycle/chamber cells containing both blocs.
- Added person-clustered uncertainty, support counts, explicit direction labels, and responsive forest-plot presentation.
- Rebuilt staged and public ideology pages without changing cluster assignments, underlying CMO/CQI values, raw candidate observations, or other site payloads.
- Focused public tests passed; independent arithmetic, accessibility, and exact 1440/390 browser validation passed. See `project_docs/audits/WEB_IDEOLOGY_HEADLINE_CONTEXT_VALIDATION.md`.
