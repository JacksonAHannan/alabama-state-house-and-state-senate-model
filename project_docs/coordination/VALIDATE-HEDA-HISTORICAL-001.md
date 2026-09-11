# Task contract: VALIDATE-HEDA-HISTORICAL-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently validate the HEDA Southern historical precinct staging outputs and determine whether Florida 2010 is fit for warehouse integration.
- Non-goals: No changes to the staging pipeline, generated staging data, canonical warehouse, models, or website.
- Upstream snapshot: `HEDA-HISTORICAL-STAGING-001` review candidate dated 2026-08-22.
- Read scope: `scripts/build_heda_historical_precinct_staging.py`; `scripts/tests/test_heda_historical_precinct_staging.py`; `data/raw/historical_statewide_elections/dataverse_files (4).zip`; `data/raw/historical_statewide_elections/dataverse_files.zip`; `data/processed/precinct_history/heda/`; `project_docs/sources/HEDA_HISTORICAL_PRECINCT_STAGING.md`
- Write scope: `project_docs/audits/HEDA_HISTORICAL_STAGING_VALIDATION.md`; `project_docs/coordination/VALIDATE-HEDA-HISTORICAL-001.md`
- Warehouse mode: `read-only`
- Inputs: HEDA staging release candidate and independent Klarner contest archive.
- Outputs: Pass/fail validation report covering reproducibility, provenance, keys, split precinct handling, missingness, district aggregation, Florida 2010 completeness, and reconciliation caveats.
- Acceptance checks: Rebuild into a temporary output directory; run focused tests; compare hashes/row counts and Florida district coverage; document all discrepancies and a promotion recommendation.
- Handoff recipient: `warehouse_integrator`
- Known risks: Both HEDA and Klarner are secondary sources; exact party totals may differ because of uncontested races, vote allocation conventions, or revisions.
