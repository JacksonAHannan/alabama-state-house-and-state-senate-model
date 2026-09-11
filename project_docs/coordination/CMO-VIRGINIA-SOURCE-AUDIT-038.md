# Task contract: CMO-VIRGINIA-SOURCE-AUDIT-038

- Accountable role: `cmo_model`
- Owner: `/root`
- Status: `complete`
- Objective: Verify newly supplied Virginia precinct results for 2017-2025 and refresh the post-2016 gap matrix so unavailable same-cycle ticket races are distinguished from missing data.
- Non-goals: Do not alter raw files, normalize observations into the warehouse, choose an off-year baseline methodology, retrain models, or modify `docs/`.
- Upstream snapshot: Newly supplied Virginia files under `data/raw/southern_sos_elections/VA/` and the completed Southern gap audit.
- Read scope: `data/raw/southern_sos_elections/VA/`; current Southern WAR panel and source audit products.
- Write scope: `scripts/audit_southern_post2016_retraining_gaps.py`; `data/processed/source_audits/southern_post2016_legislative_gap_matrix.csv`; `data/processed/source_audits/southern_post2016_legislative_gap_summary.csv`; `project_docs/audits/SOUTHERN_POST2016_RETRAINING_GAPS.md`; `project_docs/coordination/CMO-VIRGINIA-SOURCE-AUDIT-038.md`; `project_docs/coordination/active_tasks.csv`.
- Warehouse mode: `read-only`.
- Inputs: VEST/RDH ZIPs for 2017, 2019 House, 2019 Senate, and 2021; Virginia election CSVs for 2023 and 2025.
- Outputs: Corrected source routing and acquisition queue, including an explicit `not_applicable_no_same_cycle_ticket` status for Virginia 2019 and 2023.
- Acceptance checks: `python scripts/validate_agent_workflow.py`; `python scripts/audit_southern_post2016_retraining_gaps.py`; all Virginia source files open; 2023 contains 100 House and 40 Senate districts; 2025 contains 100 House districts and governor; no Virginia row remains incorrectly classified as requiring acquisition when its required result exists locally or no such ticket election existed.
- Handoff recipient: `cmo_model` for Virginia normalization and off-year baseline policy.
- Known risks: VEST redistributed absentee/provisional votes; 2019 and 2023 require an explicit off-year baseline policy before strict WAR eligibility can be determined.

## Handoff

- Changed files: `scripts/audit_southern_post2016_retraining_gaps.py`; refreshed detailed and summary CSVs under `data/processed/source_audits/`; `project_docs/audits/SOUTHERN_POST2016_RETRAINING_GAPS.md`; this task contract and its ledger row.
- Generated result: Virginia 2017 and 2021 are routed to local gubernatorial-context ZIPs; 2019 is routed to separate House/Senate precinct-result ZIPs; 2023 is routed to the official-style precinct CSV containing all 100 House and 40 Senate districts. Virginia 2019 and 2023 now carry `not_applicable_no_same_cycle_ticket` instead of a false acquisition gap. The remaining Southern election acquisition queue is only Louisiana 2019 House and Senate.
- Checks run: all four ZIPs opened and exposed expected fields; 2023 CSV contained 66,269 general-election rows across 2,675 locality-precinct keys, 100 House districts and 40 Senate districts; 2025 CSV contained 100 House districts plus governor, lieutenant governor and attorney general; the 96-row gap audit and workflow validation passed.
- Caveats: VEST redistributed absentee/provisional votes. Virginia 2019 and 2023 remain outside strict WAR until an off-year baseline policy is chosen and validated. Virginia 2025 is documented but remains outside the current through-2024 audit universe.
- Downstream action: Normalize Virginia 2017/2019/2021/2023, build 2023 incumbency, and test off-year baseline alternatives; optionally add 2025 as a newer validation cycle.
