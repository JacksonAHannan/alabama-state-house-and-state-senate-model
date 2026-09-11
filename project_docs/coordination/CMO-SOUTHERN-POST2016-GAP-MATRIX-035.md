# Task contract: CMO-SOUTHERN-POST2016-GAP-MATRIX-035

- Accountable role: `cmo_model`
- Owner: `/root`
- Status: `complete`
- Objective: Audit every scheduled post-2016 state legislative general election in the 14-state Southern research universe and produce a state-cycle-chamber matrix of the data still required for comprehensive WAR and forecast retraining.
- Non-goals: Do not alter raw evidence, canonical warehouse tables, the existing Southern WAR panel, forecast outputs, ideology products, or `docs/`; do not infer missing observations as zero.
- Upstream snapshot: Current repository sources and processed products as of 2026-08-30, including `southern_war_panel_v1`, source-acquisition audits, MEDSL ballot files, Southern ACS staging, Alabama finance products, and read-only Texas products.
- Read scope: `data/raw/`; `data/manual/`; `data/processed/`; `research/`; `project_docs/`; existing source/model scripts; read-only `C:/Users/User/Documents/GitHub/texas-state-house-and-state-senate-model/`.
- Write scope: `scripts/audit_southern_post2016_retraining_gaps.py`; `data/processed/source_audits/southern_post2016_legislative_gap_matrix.csv`; `data/processed/source_audits/southern_post2016_legislative_gap_summary.csv`; `project_docs/audits/SOUTHERN_POST2016_RETRAINING_GAPS.md`; `project_docs/coordination/CMO-SOUTHERN-POST2016-GAP-MATRIX-035.md`; `project_docs/coordination/active_tasks.csv`.
- Warehouse mode: `read-only`.
- Inputs: Scheduled general-election calendar for AL, AR, FL, GA, KY, LA, MS, MO, NC, OK, SC, TN, TX, and VA; current Southern WAR coverage; local raw-source inventory; incumbency review outputs; harmonized demographic and finance coverage.
- Outputs: One row per state-cycle-chamber with controlled statuses for outcomes, observed baseline, incumbency, demographics, finance, core WAR readiness, and full forecast readiness; plus an aggregated gap summary and a prioritized audit report.
- Acceptance checks: `python scripts/validate_agent_workflow.py`; `python scripts/audit_southern_post2016_retraining_gaps.py`; matrix has exactly one row for every scheduled state-cycle-chamber; keys are unique; no missing observation is coded as zero; all status fields use declared controlled vocabularies; summary totals reconcile to the matrix.
- Handoff recipient: `validation_release` before this audit is used to authorize model retraining.
- Known risks: Several local ZIPs have not yet been normalized, 2024 MEDSL files often contain only legislative ballots, and finance comparability outside Alabama and Texas is not established.

## Handoff

- Changed files: `scripts/audit_southern_post2016_retraining_gaps.py`; the detailed and summary CSVs under `data/processed/source_audits/`; `project_docs/audits/SOUTHERN_POST2016_RETRAINING_GAPS.md`; this task contract and its ledger row.
- Generated result: 96 scheduled state-cycle-chamber rows; 44 are strictly core-WAR ready, five are partially ready, 16 are research-only, and 31 are not ready. The current panel contains 3,797 contested races, of which 2,155 are strictly WAR-ready. Twenty non-ready rows have local election bundles that can immediately improve ticket context or outcomes.
- Checks run: workflow validation passed; matrix keys are unique; all 14 states and exactly 96 scheduled rows are present; controlled statuses and nonnegative audit counts passed script assertions; two consecutive builds produced the same matrix SHA-256 `0DDD4F23383AB2EC7B13B293D1EAE3B42D53F111B94236BD4AC97135898C9D02`.
- Caveats: No source was promoted into the warehouse. Current 2024 outcome rows are often a contested-only universe. Exact numbers of contests absent from the current panel remain unknown rather than being imputed as zero. Cross-state finance is not comparable yet.
- Downstream action: Normalize the already-downloaded complete bundles first, then independently validate the audit before using it to authorize retraining.
