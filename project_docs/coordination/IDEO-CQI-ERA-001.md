# Task contract: IDEO-CQI-ERA-001 estimate CQI association by era

- Accountable role: `legislative_ideology`
- Owner: `/root`
- Status: `complete`
- Objective: Estimate the Democratic absolute-conservatism association with the validated Candidate Quality Index by era using the existing era specification and publish the reproducible analysis rows.
- Non-goals: Do not refit CQI, alter candidate ideology, clusters, Direct CMO, raw ticket comparisons, or the warehouse.
- Upstream snapshot: Commit `adc2bfb`, `data/processed/war/cmo_v5_candidates.csv`, and the current absolute-ideology panel inputs.
- Read scope: `scripts/analyze_absolute_ideology_rebuild.py`; `tests/test_absolute_ideology_rebuild.py`; `data/processed/war/cmo_v5_candidates.csv`; current absolute-ideology inputs.
- Write scope: `scripts/analyze_absolute_ideology_rebuild.py`; `tests/test_absolute_ideology_rebuild.py`; `research/cmo_ideology/absolute_rebuild_panel.csv`; `research/cmo_ideology/absolute_rebuild_estimates.csv`; `project_docs/model/ABSOLUTE_IDEOLOGY_REBUILD.md`; `project_docs/coordination/IDEO-CQI-ERA-001.md`; `project_docs/coordination/active_tasks.csv`.
- Warehouse mode: `read-only`
- Inputs: Absolute Shor–McCarty score, CQI keyed by canonical candidate ID, incumbency, nonwhite share, white-college share, chamber, person ID, and existing era definitions.
- Outputs: `candidate_quality_index` in the analysis panel and one party-by-era CQI slope row per estimable/underpowered cell.
- Acceptance checks: `python scripts/analyze_absolute_ideology_rebuild.py`; `python -m pytest tests/test_absolute_ideology_rebuild.py -q`; Democratic CQI slopes reproduce near +9.04 before 2008 and +7.80 in 2008–2014; post-2016 remains underpowered at n=5; all CQI values join one-to-one to the v5 source.
- Handoff recipient: `web_product`
- Known risks: CQI is retrospective; Shor–McCarty coverage is officeholder-selected; post-2016 Democratic coverage is five rows; 2008–2014 uncertainty includes zero narrowly.

## Handoff

- Generated CQI-era slopes: +9.0357 before 2008, +7.8008 in 2008–2014, and underpowered with five observations after 2016.
- Tests: `11 passed` in `tests/test_absolute_ideology_rebuild.py`.
- Changed files and outputs: analysis builder, focused test, panel, estimates, and analysis report named in the write scope.
- Caveat: the 2008–2014 interval is -0.40 to +16.00 (`p=0.068`); the point estimate is positive but not conventionally significant.
- Downstream action: rebuild the public era cards from `candidate_quality_index` and obtain independent release validation.
