# Task contract: ELECTION-GEO-OPENELECTIONS-NORMALIZE-001

- Accountable role: `elections_geography`
- Owner: `/root`
- Status: `complete`
- Objective: Normalize the acquired OpenElections gap files into provenance-aware candidate precinct observations and district-level legislative/context staging.
- Non-goals: No canonical warehouse publication, model refit, or authority override.
- Upstream snapshot: `SOURCE-OPENELECTIONS-HISTORICAL-001` review candidate; promotion conditional on source validation.
- Read scope: `data/raw/openelections_historical_gaps/`; its manifest; Klarner contest archive for reconciliation.
- Write scope: `scripts/build_openelections_historical_staging.py`; `scripts/tests/test_openelections_historical_staging.py`; `data/processed/precinct_history/openelections/`; `project_docs/sources/OPENELECTIONS_HISTORICAL_STAGING.md`; `project_docs/coordination/ELECTION-GEO-OPENELECTIONS-NORMALIZE-001.md`
- Warehouse mode: `staging proposal`
- Inputs: Verified AR 2008, GA 2012/14/16, MO 2000–16, and SC 2006 general precinct CSVs.
- Outputs: Candidate-level precinct observations, contest coverage, district legislative totals where district IDs are present, same-cycle context observations, and Klarner reconciliation.
- Acceptance checks: Preserve source candidate/party and vote fields; sum Georgia modes once; missing district stays missing; no candidate-row duplicate keys; aggregate totals reconcile to normalized observations; every row has file/hash provenance; focused tests pass.
- Handoff recipient: `validation_release`, then `warehouse_integrator` or historical panel builder.
- Known risks: Office labels vary; some files may omit legislative district identifiers; OpenElections data may be unofficial or incomplete.
