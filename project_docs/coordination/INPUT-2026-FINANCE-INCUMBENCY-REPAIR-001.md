# Task contract: INPUT-2026-FINANCE-INCUMBENCY-REPAIR-001

- Accountable role: `people_finance`
- Owner: `/root`
- Status: `complete`
- Objective: Rebuild 2026 candidate finance as a consistent 2025-plus-2026 cycle total and rebuild incumbency from resolved 2022 winner identities plus post-2022 annotations.
- Non-goals: Change historical model coefficients, probability calibration, public pages, or raw source files.
- Upstream snapshot: Official FCPA 2025 annual summaries; official state 2026 summaries downloaded 2026-08-14; certified 2026 roster; canonical 2022 winners and reviewed identity crosswalk.
- Read scope: `data/raw/finance/alabama/`; `data/processed/elections/canonical_cmo_candidates.csv`; `data/processed/ideology/candidate_legislator_identity_crosswalk.csv`; `data/processed/war/2026_*roster*`; existing FCPA, finance, and incumbency inputs.
- Write scope: `scripts/build_fcpa_candidate_committee_finance.py`; `scripts/reconcile_2026_candidate_finance.py`; `scripts/build_2026_incumbency.py`; `scripts/tests/test_2026_candidate_finance_reconciliation.py`; `scripts/tests/test_2026_incumbency.py`; `data/processed/war/fcpa_candidate_committee_`; `data/processed/war/fcpa_candidate_cycle_finance.csv`; `data/processed/war/2026_candidate_incumbency.csv`; `data/processed/war/2026_incumbency_review.csv`; `data/processed/war/2026_race_incumbency.csv`; `data/processed/finance/2026_candidate_finance_`; `project_docs/audits/2026_FINANCE_INCUMBENCY_REPAIR.md`; `project_docs/coordination/INPUT-2026-FINANCE-INCUMBENCY-REPAIR-001.md`; `project_docs/coordination/active_tasks.csv`
- Warehouse mode: `staging proposal`
- Inputs: Frozen 2025 committee-year summaries, August 14 2026 state summary, final D/R/I roster, resolved 2022 candidate identities, manual incumbency overrides.
- Outputs: Roster-complete committee inventory, non-overlapping 2025 and 2026 finance components, full-cycle totals, corrected incumbent flags, and review audits.
- Acceptance checks: Finance totals equal 2025 FCPA plus 2026 state components; no unresolved value is silently zeroed; Sam Givhan is the SD-7 Republican incumbent; no race has multiple incumbents; finance and incumbency tests pass.
- Handoff recipient: `forecast_model`
- Known risks: Multiple renewed PCC records, 2025 summaries unavailable for a small number of legal-name variants, post-2022 special-election incumbents, and candidate party changes.
