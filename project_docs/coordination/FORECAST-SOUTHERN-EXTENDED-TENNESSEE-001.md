# Task contract: FORECAST-SOUTHERN-EXTENDED-TENNESSEE-001

- Accountable role: `forecast_model`
- Owner: `/root`
- Status: `complete`
- Objective: Extend the validated 2,383-row Southern panel with strictly reconciled Tennessee 1998 contests and official governor precinct context.
- Non-goals: No canonical warehouse, production forecast, Alabama CMO, or website changes.
- Upstream snapshot: Validated Arkansas-extended panel and validated Tennessee staging build `b94bf629de0d40f3157c`.
- Read scope: Extended panel/manifest; Tennessee staging/manifest/reconciliation; Klarner archive.
- Write scope: `scripts/build_tennessee_extended_historical_southern_panel.py`; `scripts/tests/test_tennessee_extended_historical_southern_panel.py`; `data/processed/forecast_calibration/historical_southern_extended_tn_*`; `data/processed/forecast_calibration/historical_southern_extended_v2_*`; `project_docs/methodology/HISTORICAL_SOUTHERN_EXTENDED_TENNESSEE.md`; `project_docs/coordination/FORECAST-SOUTHERN-EXTENDED-TENNESSEE-001.md`
- Warehouse mode: `read-only`
- Inputs: 2,383 validated rows, 79 reconciled Tennessee districts, and governor D/R precinct observations.
- Outputs: Tennessee district baselines, coverage/exclusion audit, deduplicated v2 panel, and deterministic manifest.
- Acceptance checks: Existing 2,383 rows remain unchanged; Tennessee admissions require staging eligibility, contested positive D/R Klarner outcomes, finite baseline, and at least 95% legislative-turnout join coverage; allocation conserves joined context votes; keys are unique; missing OCR cells are never zero-filled; focused tests pass.
- Handoff recipient: `validation_release`, then `cmo_model` tournament rerun.
- Known risks: OCR context is incomplete; 50 governor rows are unresolved; exact name joins omit recoverable aliases; district coverage is uneven.
