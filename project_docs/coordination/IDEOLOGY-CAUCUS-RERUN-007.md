# Task contract: IDEOLOGY-CAUCUS-RERUN-007 caucus reclustering

- Accountable role: `legislative_ideology`
- Owner: `/root`
- Status: `complete`
- Objective: Refit party-specific ideological groupings using the repaired, current absolute issue-position panel and regenerate all cluster diagnostics and performance attachments.
- Non-goals: Do not use electoral performance to assign clusters; do not change CMO/CQI; do not build or publish website files.
- Upstream snapshot: Completed `IDEOLOGY-DOWNSTREAM-RERUN-006` absolute panel dated 2026-08-24 and current CMO v4 structural residual.
- Read scope: `research/cmo_ideology/absolute_rebuild_panel.csv`; `data/processed/war/cmo_v4_candidates.csv`
- Write scope: `scripts/analyze_democratic_ideological_clusters.py`; `research/cmo_ideology/democratic_clusters/`; `project_docs/coordination/IDEOLOGY-CAUCUS-RERUN-007.md`; `project_docs/coordination/active_tasks.csv`
- Warehouse mode: `read-only`
- Inputs: Absolute, temporally eligible issue-position features; candidate-cycle identities and era labels.
- Outputs: Cluster membership, profiles, k-selection diagnostics, sensitivity checks, era composition, persistence, and post-clustering performance summaries.
- Acceptance checks: `python scripts/analyze_democratic_ideological_clusters.py && python -m pytest scripts/tests/test_democratic_ideological_clusters.py -q`; verify cluster labels are unique within party, current CMO check differences are zero, and no undefined eras exist. Page compatibility is a downstream `web_product` gate.
- Handoff recipient: `web_product`.
- Known risks: Low silhouette or unstable imputation sensitivity can imply an ideological continuum rather than discrete caucuses; labels remain descriptive.

## Handoff

- The selected solutions contain three Democratic and three Republican clusters.
- Democratic membership: 33 traditionalist-populist, 59 bridge-coalition, and 39 progressive-modern candidate-cycles across 18 usable axes.
- Democratic silhouette is 0.235 and bootstrap ARI is 0.838; the low silhouette supports presenting the groups as descriptive regions on a continuum.
- Republican membership: 88 social/institutional, 58 business-conservative, and 34 moderate pre-realignment candidate-cycles across 15 axes.
- Cluster labels are now one-to-one with cluster IDs. No undefined eras remain and the CMO v4 attachment check differs only by floating-point noise (< 1e-9).
- Two focused clustering tests passed. The merged page must be revised to display the new bridge coalition before it can pass its web gate.
