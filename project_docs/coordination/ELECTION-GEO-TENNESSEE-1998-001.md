# Task contract: ELECTION-GEO-TENNESSEE-1998-001

- Accountable role: `elections_geography`
- Owner: `/root`
- Status: `complete`
- Objective: OCR and normalize the official Tennessee 1998 House, Senate, and governor precinct reports into reviewable legislative-turnout and Democratic/Republican context staging.
- Non-goals: No canonical warehouse, combined-panel admission, model rerun, Alabama outputs, or website changes.
- Upstream snapshot: Immutable official Tennessee SOS PDFs and the local Klarner archive.
- Read scope: `data/raw/southern_sos_elections/TN/1998/house-p.pdf`; `senate-p.pdf`; `gov-p.pdf`; source manifest; Klarner archive.
- Write scope: `scripts/build_tennessee_1998_precinct_staging.py`; `scripts/tests/test_tennessee_1998_precinct_staging.py`; `data/processed/precinct_history/tennessee_1998/`; `project_docs/sources/TENNESSEE_1998_PRECINCT_STAGING.md`; `project_docs/coordination/ELECTION-GEO-TENNESSEE-1998-001.md`
- Warehouse mode: `read-only`
- Inputs: 142 scanned official report pages with no embedded text.
- Outputs: Cached page-level OCR evidence, normalized precinct legislative turnout, governor D/R observations, district reconciliation audit, OCR quality/coverage report, and deterministic manifest.
- Acceptance checks: Raw PDFs remain unchanged; OCR provenance and confidence are retained; district/county/precinct state does not bleed across report blocks; totals rows are excluded; vote values are nonnegative; keys are unique after explicit reconciliation; major-party district totals reconcile to Klarner under a declared tolerance; low-confidence/ambiguous rows remain excluded; source/output hashes and focused tests pass.
- Handoff recipient: `validation_release`, then historical panel integration.
- Known risks: Scanned tables, OCR digit substitutions, variable candidate counts, multi-page districts/counties, write-in columns, and missing zero glyphs.
