# Task contract: FORECAST-FINANCE-DIRECTION-030 headline fundraising direction repair

- Accountable role: `forecast_model`
- Owner: `/root`
- Status: `complete`
- Objective: Publish a forecast-model release candidate whose fundraising contribution is based on the observed Democratic-versus-Republican fundraising gap and can never favor the party that raised less.
- Non-goals: Candidate/committee identity changes, finance-source edits, warehouse schema changes, probability recalibration, or direct publication to `docs/`.
- Upstream snapshot: `data/processed/finance/2026_candidate_finance_reconciled.csv` and `data/processed/forecast_calibration/post2016_polling_cmo_*` as of 2026-08-28.
- Read scope: `data/processed/finance/2026_candidate_finance_reconciled.csv`; `data/processed/forecast_calibration/post2016_polling_cmo_*`; `data/processed/forecast_calibration/robust_forecast_v1_error_components.csv`; `scripts/run_post2016_polling_cmo_forecast.py`; forecast dashboard/tests as read-only consumers.
- Write scope: `scripts/promote_post2016_headline_forecast.py`; `data/processed/forecast_calibration/post2016_headline_v1_*`; `project_docs/model/POST2016_HEADLINE_FORECAST_V1.md`; `project_docs/audits/FORECAST_FINANCE_DIRECTION_REPAIR.md`; `project_docs/coordination/FORECAST-FINANCE-DIRECTION-030.md`. The orchestrator ledger entry is recorded separately and is not an ongoing domain write scope.
- Warehouse mode: `read-only`
- Inputs: Reconciled 2026 candidate finance, post-2016 forecast tournament outputs, and existing uncertainty components.
- Outputs: Rebuilt headline scenario, uncertainty, seat distribution, manifest, methodology, and a before/after audit.
- Acceptance checks: `python scripts/validate_agent_workflow.py`; `python scripts/promote_post2016_headline_forecast.py`; every finance-complete headline race has a fundraising-adjustment sign matching the observed D-minus-R log fundraising gap; SD-7 retains $19,146.16 Democratic and $370,509.84 Republican receipts and has a negative Democratic fundraising adjustment; missing finance remains missing and receives zero adjustment; relevant forecast tests pass.
- Handoff recipient: `web_product`, then `validation_release`
- Known risks: Direct fundraising is correlated with incumbency and donor expectations; only one true forward Alabama holdout is available; switching headline specification changes margins beyond SD-7.
