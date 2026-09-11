# Task contract: VALIDATE-SOUTHERN-HISTORICAL-PANEL-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently validate the revised HEDA staging provenance/reproducibility and the experimental historical Southern comparison panel's eligibility and allocation safeguards.
- Non-goals: No changes to source, staging, panel, canonical warehouse, models, or website.
- Upstream snapshot: Revised `HEDA-HISTORICAL-STAGING-001` and `SOUTHERN-HISTORICAL-PANEL-001` review candidates dated 2026-08-22.
- Read scope: `scripts/build_heda_historical_precinct_staging.py`; `scripts/build_historical_southern_legislative_panel.py`; their focused tests; `data/processed/precinct_history/heda/`; `data/processed/forecast_calibration/historical_southern_heda_*.csv`; relevant task and methodology documents.
- Write scope: `project_docs/audits/SOUTHERN_HISTORICAL_PANEL_VALIDATION.md`; `project_docs/coordination/VALIDATE-SOUTHERN-HISTORICAL-PANEL-001.md`
- Warehouse mode: `read-only`
- Inputs: Revised HEDA staging and experimental panel release candidates.
- Outputs: Pass/fail audit for staging reproducibility and experimental fitness, explicitly distinguishing canonical promotion from model experimentation.
- Acceptance checks: Temporary rebuilds are deterministic; manifests and hashes reconcile; panel keys are unique; allocations conserve context; only finite positive Klarner D/R contests with baselines are model eligible; HEDA leakage cannot create eligibility; focused tests pass.
- Handoff recipient: `warehouse_integrator` and `cmo_model`
- Known risks: HEDA geography can assign split precincts incompletely; 1994–2000 coverage remains absent; allocated baselines are unsuitable as unqualified canonical facts.
