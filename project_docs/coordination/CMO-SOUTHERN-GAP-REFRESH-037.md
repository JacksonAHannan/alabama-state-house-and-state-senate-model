# Task contract: CMO-SOUTHERN-GAP-REFRESH-037

- Accountable role: `cmo_model`
- Owner: `/root`
- Status: `complete`
- Objective: Refresh the post-2016 Southern retraining matrix after the validated MEDSL acquisition so downloaded sources are distinguished from remaining acquisition gaps.
- Non-goals: Do not normalize election observations, publish warehouse tables, retrain models, or alter `docs/`.
- Upstream snapshot: Completed `SOURCE-MEDSL-SOUTHERN-GAPS-036` manifest and immutable ZIPs plus the existing Southern WAR panel.
- Read scope: `data/raw/historical_statewide_elections/medsl_github/`; `data/processed/war/southern_war_panel_v1/`; existing demographic and finance coverage products.
- Write scope: `scripts/audit_southern_post2016_retraining_gaps.py`; `data/processed/source_audits/southern_post2016_legislative_gap_matrix.csv`; `data/processed/source_audits/southern_post2016_legislative_gap_summary.csv`; `project_docs/audits/SOUTHERN_POST2016_RETRAINING_GAPS.md`; `project_docs/coordination/CMO-SOUTHERN-GAP-REFRESH-037.md`; `project_docs/coordination/active_tasks.csv`.
- Warehouse mode: `read-only`.
- Inputs: Validated MEDSL manifest with KY/MO/OK/SC 2022 and AR/KY/OK/SC/TN 2024 bundles.
- Outputs: Updated 96-row gap matrix, state summary, and prioritized normalization/acquisition queues.
- Acceptance checks: `python scripts/validate_agent_workflow.py`; `python scripts/audit_southern_post2016_retraining_gaps.py`; all nine acquired state-years route to validated local MEDSL files; remaining new-election-data queue contains only genuinely unfilled state-years; matrix keys and totals reconcile.
- Handoff recipient: `cmo_model` normalization task.
- Known risks: Downloaded bundles are not yet equivalent to model-ready district aggregates; readiness remains unchanged until normalization and validation complete.

## Handoff

- Changed files: `scripts/audit_southern_post2016_retraining_gaps.py`; refreshed detailed and summary CSVs under `data/processed/source_audits/`; `project_docs/audits/SOUTHERN_POST2016_RETRAINING_GAPS.md`; this task contract and its ledger row.
- Generated result: All nine acquired MEDSL state-years now route to validated local bundles, covering 17 scheduled cycle-chamber rows. The normalization queue increased from 20 to 37 rows, while the election-data acquisition queue fell from 25 to eight.
- Checks run: workflow validation passed; the audit rebuilt 96 unique scheduled rows; all 17 state-cycle-chamber rows tied to the nine-file MEDSL manifest resolve to existing files; the remaining election acquisition queue contains only LA 2019 and VA 2017/2019/2021/2023.
- Caveats: Core readiness remains 44 of 96 until downloaded files are normalized and their district aggregates validated.
- Downstream action: Normalize MEDSL files, validate aggregate vote totals and district assignment, then rebuild the Southern WAR panel.
