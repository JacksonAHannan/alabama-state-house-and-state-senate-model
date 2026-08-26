# Task contract: FORECAST-2026-FINANCE-RECON-001 — Integrate reconciled 2026 finance

- Accountable role: `forecast_model`
- Owner: `/root`
- Status: `complete`
- Objective: Make the headline forecast consume the roster-complete August 14 finance reconciliation, exclude the three unverified live-summary zeros from fundraising adjustments, and rebuild forecast model artifacts.
- Non-goals: Change historical finance training data, alter forecast specification or probability calibration, publish `docs/`, or push the website.
- Upstream snapshot: Completed `FINANCE-2026-ZERO-AUDIT-001` staging output and current post-2016 headline forecast.
- Read scope: `data/processed/finance/2026_candidate_finance_reconciled.csv`; current post-2016 forecast scripts, source panels, polling, incumbency, and tests.
- Write scope: `scripts/run_post2016_polling_cmo_forecast.py`; `scripts/build_2026_forecast_dashboard.py`; `scripts/tests/test_post2016_polling_cmo_forecast.py`; `data/processed/forecast_calibration/post2016_polling_cmo_`; `data/processed/forecast_calibration/post2016_headline_v1_`; `project_docs/model/POST2016_POLLING_CMO_EXPERIMENT.md`; `project_docs/model/POST2016_HEADLINE_FORECAST_V1.md`; `project_docs/coordination/FORECAST-2026-FINANCE-RECON-001.md`; `project_docs/coordination/active_tasks.csv`
- Warehouse mode: `read-only`
- Inputs: Reconciled 2026 candidate finance; frozen historical training panel; current polling and incumbency inputs.
- Outputs: Rebuilt forecast candidate, scenarios, uncertainty, manifests, and builders wired to the reconciled display source.
- Acceptance checks: `python scripts/run_post2016_polling_cmo_forecast.py`; `python scripts/promote_post2016_headline_forecast.py`; `python -m pytest scripts/tests/test_2026_candidate_finance_reconciliation.py scripts/tests/test_post2016_polling_cmo_forecast.py -q`; Allison Montgomery's model and dashboard-payload amount is $6,257.20; unverified candidates do not receive a fundraising adjustment; every complete race has two observed finance records.
- Handoff recipient: `web_product`
- Known risks: Recovered fundraising changes within-cycle normalization for all contested races; the three source-absent candidates must remain missing rather than zero; regenerated outputs may change forecast margins.

## Handoff

- The forecast candidate and promoted headline artifacts were rebuilt with 45
  of 48 contested races finance-complete.
- The only finance-incomplete contests are HD-82, HD-99, and SD-23 because the
  Republican candidate in each is absent from the cutoff-specific state
  summary.  Those races receive no fundraising adjustment.
- The dashboard builder now reads the reconciled candidate table, and its
  payload smoke test confirms Allison Montgomery displays $6,257.20 raised and
  $3,969.71 spent.
- `docs/` and the generated public artifact were deliberately not rebuilt or
  published under this task.  The existing artifact/version consistency tests
  will remain stale until a separately scoped web publication and independent
  validation task runs.
