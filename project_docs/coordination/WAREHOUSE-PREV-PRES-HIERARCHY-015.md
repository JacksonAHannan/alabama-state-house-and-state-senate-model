# Task contract: WAREHOUSE-PREV-PRES-HIERARCHY-015

- Accountable role: `warehouse_integrator`
- Owner: `/root`
- Status: `complete`
- Objective: Repair the precinct-to-district allocation hierarchy so official same-cycle legislative ballot evidence controls before shared-VTD geometry, then rebuild and audit historical previous-presidential district features.
- Acceptance checks: A precinct reporting one legislative district is assigned wholly to that district even when its matched VTD spans several districts; genuinely split reported precincts retain activity-weighted allocation; precincts without reported district evidence retain spatial/fallback handling; each source election conserves Democratic and Republican votes independently by chamber; HD-32's 2008 presidential margin is independently reconstructed and compared with the prior value; all district-cycle changes are written to an audit; focused geography and presidential tests pass.
- Read scope: Immutable election returns under `data/raw/`; read-only election warehouse; current geography links, allocation weights, presidential precinct files, and downstream CMO inputs.
- Write scope: `scripts/build_geographic_crosswalks.py`; `scripts/tests/test_build_geographic_crosswalks.py`; `scripts/tests/test_build_presidential_district_features.py`; `data/processed/elections/canonical_precinct_district_weights.csv`; `data/processed/elections/canonical_geography_qa.csv`; `data/processed/war/geographic_precinct_district_weights.csv`; `data/processed/war/geographic_precinct_vtd_matches.csv`; `data/processed/war/geographic_crosswalk_qa.csv`; `data/processed/presidential/`; `project_docs/audits/PREVIOUS_PRESIDENTIAL_CONTEXT_AUDIT.md`; `project_docs/coordination/WAREHOUSE-PREV-PRES-HIERARCHY-015.md`; `project_docs/coordination/active_tasks.csv`.
- Upstream inputs: Official Alabama SOS legislative observations in `alabama_elections.sqlite`, approved canonical precinct aliases, 2008-2020 presidential precinct extracts, enacted-plan block assignments, and the user-approved ballot-cooccurrence-first hierarchy.
- Expected outputs: Corrected canonical precinct allocation weights, rebuilt previous-presidential district features and match diagnostics, regression tests, and a before/after district audit.
- Warehouse mode: `writer`
- Handoff recipient: `cmo_model` for dependent historical score rebuild.

## Handoff

- Repaired the allocation hierarchy so precinct-specific ballot evidence is authoritative over shared VTD geometry.
- Rebuilt canonical and analytical precinct weights plus every 2008-2020 presidential source-to-legislative-cycle feature file.
- Corrected 2008 HD-32 from R+5.84 to D+24.05; the full before/after audit is in `project_docs/audits/PREVIOUS_PRESIDENTIAL_CONTEXT_AUDIT.md`.
- Validation passed: 22 focused tests, all expected district rows retained, and Democratic/Republican vote conservation preserved by chamber.
- Downstream CMO/WAR outputs and public pages remain to be rebuilt from these corrected inputs.
