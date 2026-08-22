# Task contract: IDEO-CAUCUS-RECLUSTER-001 Current-CMO caucus clustering

- Accountable role: `legislative_ideology`
- Owner: `/root`
- Status: `complete`
- Objective: Refit empirical ideological groupings against the rebuilt ideology evidence and CMO v4, selecting cluster counts from separation, stability, size, era robustness, and missingness diagnostics.
- Non-goals: Change CMO scores, canonical warehouse tables, manual ideological adjudications, or public pages.
- Upstream snapshot: `data/processed/war/cmo_v4_candidates.csv` and the August 21 rebuilt absolute-ideology panel.
- Read scope: `research/cmo_ideology/absolute_rebuild_*.csv`; `data/processed/war/cmo_v4_candidates.csv`; `data/processed/ideology/candidate_issue_valence_v3_adjudicated.csv`; prior clustering code and outputs.
- Write scope: `scripts/analyze_democratic_ideological_clusters.py`; `research/cmo_ideology/democratic_clusters/`; `scripts/tests/test_democratic_ideological_clusters.py`; `project_docs/coordination/IDEO-CAUCUS-RECLUSTER-001.md`; `project_docs/coordination/active_tasks.csv`.
- Warehouse mode: `read-only`
- Inputs: Temporally eligible issue positions, absolute ideology measures, party/cycle metadata, and CMO v4 candidate outcomes.
- Outputs: Cluster assignments, profiles, model-selection diagnostics, stability/era/performance summaries, and an interpretation report.
- Acceptance checks: Analysis completes deterministically; clustering features exclude electoral outcomes; all assignments have a party-consistent label; selected solutions meet documented minimum-size rules; output CMO values match CMO v4; `python -m pytest scripts/tests/test_democratic_ideological_clusters.py -q` passes.
- Handoff recipient: `validation_release`
- Known risks: Sparse and nonrandom issue coverage, repeated candidates, label switching, era drift, and continuum structure may make discrete caucuses weak or unstable.
