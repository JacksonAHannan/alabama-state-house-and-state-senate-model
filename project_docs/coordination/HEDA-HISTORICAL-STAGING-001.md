# Task contract: HEDA-HISTORICAL-STAGING-001

- Accountable role: `elections_geography`
- Owner: `/root`
- Status: `complete`
- Objective: Normalize the Historical Election Data Archive holdings for the Southern comparison states into provenance-aware staging outputs, including a directly usable Florida 2010 legislative precinct and district panel.
- Non-goals: No canonical warehouse writes, no model retraining, no publication to `docs/`, and no alteration of raw archives.
- Upstream snapshot: `data/raw/historical_statewide_elections/dataverse_files (4).zip` as downloaded 2026-08-22; existing Klarner and Southern SOS holdings read-only.
- Read scope: `data/raw/historical_statewide_elections/`; `data/processed/source_audits/`; `project_docs/coordination/agent_ownership.json`
- Write scope: `scripts/build_heda_historical_precinct_staging.py`; `scripts/tests/test_heda_historical_precinct_staging.py`; `data/processed/precinct_history/heda/`; `project_docs/sources/HEDA_HISTORICAL_PRECINCT_STAGING.md`; `project_docs/coordination/HEDA-HISTORICAL-STAGING-001.md`
- Warehouse mode: `staging proposal`
- Inputs: HEDA state-year Stata files and archive documentation; Klarner district contest archive for reconciliation where available.
- Outputs: State-year coverage inventory, normalized legislative precinct observations, district aggregates, Florida 2010 model-ready staging, baseline-context observations, and reconciliation diagnostics.
- Acceptance checks: `python scripts/build_heda_historical_precinct_staging.py`; `python -m pytest scripts/tests/test_heda_historical_precinct_staging.py -q`; output keys are unique at their declared grain; missing votes remain missing; district totals reproduce included precinct sums; every row retains archive/member provenance.
- Handoff recipient: `warehouse_integrator`
- Known risks: HEDA is a secondary normalized source; numbered vote slots and district fields vary by state; context-only precincts require later geographic assignment; overlapping official records retain higher authority.
