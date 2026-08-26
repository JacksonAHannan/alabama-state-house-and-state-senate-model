# Task contract: FINANCE-2026-ZERO-AUDIT-001 — Audit 2026 zero finance classifications

- Accountable role: `people_finance`
- Owner: `/root`
- Status: `complete`
- Objective: Reconcile every 2026 candidate currently classified as having no cycle activity against the August 14 official state committee summaries, FCPA committee identities, and transaction evidence; preserve genuine zeros and recover all deterministic matches.
- Non-goals: Change raw finance files, alter historical-cycle finance, retrain the forecast, or publish `docs/`.
- Upstream snapshot: Official Alabama state House and Senate finance CSVs downloaded 2026-08-14; current 2026 final roster, FCPA committee inventory, committee summaries, and transaction matches.
- Read scope: `data/raw/finance/alabama/State * Fundraising 2026 Cycle.csv`; `data/processed/war/2026_final_candidate_roster.csv`; `data/processed/war/fcpa_candidate_committee_*.csv`; `data/processed/war/fcpa_candidate_cycle_finance.csv`; `data/processed/war/candidate_finance_matches.csv`; existing finance scripts and tests.
- Write scope: `scripts/reconcile_2026_candidate_finance.py`; `scripts/tests/test_2026_candidate_finance_reconciliation.py`; `data/manual/finance/2026_candidate_finance_aliases.csv`; `data/processed/finance/2026_candidate_finance_reconciled.csv`; `data/processed/finance/2026_candidate_finance_match_audit.csv`; `project_docs/audits/2026_ZERO_FINANCE_RECONCILIATION.md`; `project_docs/coordination/FINANCE-2026-ZERO-AUDIT-001.md`; `project_docs/coordination/active_tasks.csv`
- Warehouse mode: `staging proposal`
- Inputs: Certified 2026 D/R roster; official state committee-summary exports through 2026-08-14; FCPA PCC search inventory; FCPA financial summaries; transaction-level expenditure matches.
- Outputs: One roster-complete reconciled finance staging table, a row-level audit of previously zero/missing candidates, explicit aliases for any non-deterministic legal-name variants, and a reproducible audit report.
- Acceptance checks: `python scripts/reconcile_2026_candidate_finance.py`; `python -m pytest scripts/tests/test_2026_candidate_finance_reconciliation.py -q`; exactly one reconciled row per 2026 D/R roster candidate; no duplicate state source assignment; every positive official summary matched or explicitly reviewed; no missing amount converted to zero without an observed state record.
- Handoff recipient: `forecast_model`
- Known risks: Legal names and nicknames; duplicate dissolved/active committee rows; distinction between cash fundraising, other receipts, in-kind contributions, and expenditures; fixed 2026-08-14 forecast cutoff.
