# Task contract: IDEOLOGY-DOWNSTREAM-RERUN-006 downstream hypothesis rebuild

- Accountable role: `legislative_ideology`
- Owner: `/root`
- Status: `complete`
- Objective: Rebuild the current issue-position hypothesis analyses and absolute-position panel from the repaired roll-call, identity, and candidate-evidence layer.
- Non-goals: Do not change canonical warehouse tables, raw evidence, CMO construction, the headline forecast, or public `docs/` output.
- Upstream snapshot: Completed `IDEOLOGY-POSTREPAIR-COVERAGE-005` outputs dated 2026-08-24, current validated CMO v4/v5 outcomes, and current federal/presidential baselines.
- Read scope: `data/processed/ideology/`; `data/processed/legislative/`; `data/processed/elections/canonical_cmo_candidates_with_ideology_v3.csv`; `data/processed/elections/historical_federal_district_baselines.csv`; `data/processed/war/cmo_v4_candidates.csv`; `data/processed/war/cmo_v5_candidates.csv`; `data/processed/war/preliminary_cmo_races.csv`; `research/cmo_ideology/symmetric_incumbency_panel.csv`
- Write scope: `research/cmo_ideology/absolute_rebuild_`; `data/processed/elections/validation/issue_stance_`; `data/processed/elections/validation/headline_ideology_`; `data/processed/ideology/ideological_bundle_`; `data/processed/ideology/ideology_headline_`; `data/processed/ideology/ideology_issue_`; `data/processed/ideology/ideology_thesis_`; `project_docs/model/ABSOLUTE_IDEOLOGY_REBUILD.md`; `project_docs/model/ISSUE_STANCE_DURABLE_OVERPERFORMANCE.md`; `project_docs/model/ISSUE_STANCE_TOURNAMENT.md`; `project_docs/model/HEADLINE_IDEOLOGY_TOURNAMENT.md`; `project_docs/model/IDEOLOGICAL_BUNDLE_PERFORMANCE.md`; `project_docs/coordination/IDEOLOGY-DOWNSTREAM-RERUN-006.md`; `project_docs/coordination/active_tasks.csv`
- Warehouse mode: `read-only`
- Inputs: Repaired candidate ideology v3 evidence and identities through 2026; CMO v4 structural residual; CMO v5 Candidate Quality Index; historical statewide, federal, and prior-presidential performance.
- Outputs: Fresh issue-analysis panels, estimates, coverage tables, hypothesis verdicts, bundle summaries, and model reports. The existing Shor-McCarty and symmetric-incumbency work remains a separate review workstream because it does not consume the repaired roll-call feature mart.
- Acceptance checks: Run all named builders successfully; run focused ideology-analysis tests; verify output IDs are unique where required, no undefined eras exist, and all generated file mtimes postdate the repaired evidence mart.
- Handoff recipient: `legislative_ideology` for clustering, then `forecast_model` and `web_product`.
- Known risks: Historical ideology evidence is selected toward officeholders; repeated candidates require person-clustered uncertainty; some legacy scripts may still reference superseded CMO fields and must not silently overwrite current interpretations.

## Handoff

- Rebuilt `absolute_rebuild_*`, issue-stability, headline-dimension, bundle, and thesis outputs from the repaired 2026-08-24 evidence mart.
- Acceptance suite: 35 focused tests passed.
- Integrity checks: 1,018-row absolute panel with unique candidate-cycle IDs; no `undefined` era; every named output is newer than the repaired integrated ideology input.
- The current issue tournament reports total-association signals separately from pooled-only results. These are historical explanatory findings and are not automatically eligible forecast predictors.
- Next: recluster caucuses from the rebuilt absolute panel, then produce a separately audited prospective-ideology feature export.
