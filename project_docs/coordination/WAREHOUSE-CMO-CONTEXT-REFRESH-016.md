# Task contract: WAREHOUSE-CMO-CONTEXT-REFRESH-016

- Accountable role: `warehouse_integrator`
- Owner: `/root`
- Status: `complete`
- Objective: Publish corrected previous-presidential features into the canonical historical CMO feature exports without changing candidate or election authority rules.
- Acceptance checks: Canonical CMO features reproduce the corrected 2010 HD-32 2008 presidential margin of D+24.05; candidate keys remain unique; every eligible race retains its candidate rows; source completeness and fallback fields remain explicit; canonical CMO tests pass.
- Read scope: Completed `WAREHOUSE-PREV-PRES-HIERARCHY-015` outputs, read-only election warehouse, current finance/demographic/federal marts, and current canonical candidate observations.
- Write scope: `data/processed/elections/canonical_cmo_features.csv`; `data/processed/elections/canonical_cmo_candidates.csv`; `data/processed/elections/canonical_cmo_district_office_baselines.csv`; `data/processed/elections/historical_cmo_extension.csv`; `project_docs/coordination/WAREHOUSE-CMO-CONTEXT-REFRESH-016.md`; `project_docs/coordination/active_tasks.csv`.
- Upstream inputs: Corrected presidential district features from `WAREHOUSE-PREV-PRES-HIERARCHY-015` and the current integrated election warehouse.
- Expected outputs: Refreshed canonical CMO race/candidate/context compatibility exports ready for the model rebuild.
- Warehouse mode: `writer`
- Handoff recipient: `cmo_model`.

## Handoff

- Refreshed all canonical CMO compatibility exports from the corrected presidential context.
- The canonical 2010 House District 32 row now carries a 2008 Democratic presidential margin of `+24.052976`.
- Candidate IDs remain unique across 1,564 canonical candidate rows, and all seven focused CMO model tests pass.
- Pandas emitted existing future-deprecation warnings during the build; they do not change the current output and should be addressed separately.
