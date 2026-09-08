# Task contract: SOUTHERN-HISTORICAL-PANEL-001

- Accountable role: `forecast_model`
- Owner: `/root`
- Status: `complete`
- Objective: Build an experimental 1994–2016 Southern legislative comparison panel from validated HEDA precinct fragments, same-cycle statewide/federal context, and Klarner candidate metadata.
- Non-goals: No replacement of the recent-era production probability model, no canonical warehouse writes, no website publication, and no use of context allocations without an explicit quality flag.
- Upstream snapshot: `HEDA-HISTORICAL-STAGING-001` review candidate; final promotion conditional on `VALIDATE-HEDA-HISTORICAL-001`.
- Read scope: `data/processed/precinct_history/heda/`; `data/raw/historical_statewide_elections/dataverse_files.zip`; `project_docs/methodology/SOUTHERN_LEGISLATIVE_PROBABILITY_CALIBRATION.md`
- Write scope: `scripts/build_historical_southern_legislative_panel.py`; `scripts/tests/test_historical_southern_legislative_panel.py`; `data/processed/forecast_calibration/historical_southern_heda_*.csv`; `project_docs/methodology/HISTORICAL_SOUTHERN_CMO_PANEL.md`; `project_docs/coordination/SOUTHERN-HISTORICAL-PANEL-001.md`
- Warehouse mode: `read-only`
- Inputs: HEDA legislative precinct-fragment and context staging; Klarner contest and candidate records.
- Outputs: District-cycle legislative outcomes, allocated same-cycle baseline margins, candidate/incumbency metadata, coverage diagnostics, and allocation-quality fields.
- Acceptance checks: Unit tests pass; keys are unique by state/year/chamber/district; statewide context is not duplicated across split precinct fragments; allocations sum back to source precinct context where weights are available; missing baselines remain missing.
- Handoff recipient: `cmo_model`
- Known risks: Split-precinct context requires turnout-share allocation; HEDA coverage is concentrated in 2001–2012 and is not a complete 1994–2016 panel; secondary-source discrepancies remain reviewable.
