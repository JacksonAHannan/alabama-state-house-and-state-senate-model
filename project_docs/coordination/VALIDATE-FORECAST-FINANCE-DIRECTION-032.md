# Task contract: VALIDATE-FORECAST-FINANCE-DIRECTION-032 independent forecast finance validation

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently determine whether the repaired direct relative-fundraising forecast and staged pages are safe to publish.
- Non-goals: Modify model code, model outputs, dashboard code, staged HTML, finance identities, or `docs/`.
- Upstream snapshot: `FORECAST-FINANCE-DIRECTION-030` build `8cad753f1720c2a1b107` and `WEB-FORECAST-FINANCE-DIRECTION-031` staged artifacts.
- Read scope: `scripts/promote_post2016_headline_forecast.py`; `scripts/build_2026_forecast_dashboard.py`; `data/processed/finance/2026_candidate_finance_reconciled.csv`; `data/processed/forecast_calibration/post2016_*`; `artifacts/site/alabama-2026-legislative-forecast.html`; `artifacts/site/forecast-methodology.html`; relevant tests and methodology/audits.
- Write scope: `project_docs/audits/FORECAST_FINANCE_DIRECTION_VALIDATION.md`; `project_docs/coordination/VALIDATE-FORECAST-FINANCE-DIRECTION-032.md`.
- Warehouse mode: `read-only`
- Inputs: Reconciled finance, rebuilt headline model, staged forecast page, staged methodology page.
- Outputs: Independent pass/fail validation report with exact commands and any blockers.
- Acceptance checks: Verify all 45 finance-complete races have contribution signs consistent with observed D-minus-R receipts; verify SD-7 totals and negative Democratic finance effect; verify three incomplete races remain missing/zero-adjustment; verify selected manifest/model/methodology agree; run forecast tests; inspect staged page for stale residualized-headline language and basic rendering/data integrity.
- Handoff recipient: `orchestrator`
- Known risks: Direct fundraising is correlated with incumbency and donor expectations; approval concerns internal consistency and release safety, not causal identification.

## Validation handoff

- Verdict: **APPROVE**
- Completed: 2026-08-28
- Report: `project_docs/audits/FORECAST_FINANCE_DIRECTION_VALIDATION.md`
- Evidence: 45/45 finance-complete contests have correctly directed contributions; SD-7 uses `$19,146.16` D versus `$370,509.84` R and a `-8.87793` Democratic finance effect; HD-82, HD-99, and SD-23 retain a missing party-side observation and zero adjustment; manifest hashes/build ID reproduce; staged payload reconciles all 48 contests; focused workflow and 27 tests pass; desktop/mobile staged pages have no overflow or severe console errors.
- Publication condition: run the normal publication build and publication-consistency test so the intentionally unchanged `docs/` copies receive this approved staged package.
