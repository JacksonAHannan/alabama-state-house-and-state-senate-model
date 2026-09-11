# Task contract: ELECTION-GEO-ARKANSAS-PRE2000-001

- Accountable role: `elections_geography`
- Owner: `/root`
- Status: `complete`
- Objective: Normalize the official Arkansas 1994, 1996, and 1998 county-sheet precinct workbooks into reviewable legislative and federal-context observations suitable for extending the Southern panel before 2000.
- Non-goals: No canonical warehouse publication, model rerun, Alabama outputs, or website changes.
- Upstream snapshot: Immutable official Arkansas SOS downloads and the local Klarner archive.
- Read scope: `data/raw/southern_sos_elections/AR/1994/`; `.../AR/1996/`; `.../AR/1998/`; acquisition manifests; Klarner staging inputs.
- Write scope: `scripts/build_arkansas_pre2000_precinct_staging.py`; `scripts/tests/test_arkansas_pre2000_precinct_staging.py`; `data/processed/precinct_history/arkansas_pre2000/`; `project_docs/sources/ARKANSAS_PRE2000_PRECINCT_STAGING.md`; `project_docs/coordination/ELECTION-GEO-ARKANSAS-PRE2000-001.md`
- Warehouse mode: `read-only`
- Inputs: One official workbook per general election, including the 1998 workbook inside its source ZIP.
- Outputs: Normalized precinct candidate observations, district summaries, coverage/review audit, and deterministic manifest.
- Acceptance checks: Raw files remain unchanged; candidate rows inherit the active contest label and district; totals columns are excluded; votes are numeric and nonnegative; duplicate county/precinct/office/district/candidate rows are reconciled without double counting; major-party legislative outcomes reconcile to Klarner where possible; manifest hashes/counts are stable; focused tests pass.
- Handoff recipient: `validation_release`, then combined-panel integration.
- Known risks: Workbook formatting varies by county/year; repeated headings and candidate blocks exist; some unopposed contests may omit vote rows; 1994 contains inconsistent labels.
