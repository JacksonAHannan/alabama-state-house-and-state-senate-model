# Task contract: SOUTHERN-SOS-HISTORICAL-001

- Accountable role: `source_provenance`
- Owner: `/root`
- Status: `complete`
- Corrective scope: Provider-specific acquisition for TX, LA, AR, OK, MS, MO, TN, AL, FL, GA, NC, SC, KY, and VA. Texas and Alabama are already held; active acquisition targets are LA, AR, OK, MS, MO, TN, FL, GA, NC, SC, KY, and VA. A generic archive inventory is not sufficient.
- Objective: Inventory and acquire publicly downloadable official precinct-level election returns needed for a 1994–2016 Southern legislative candidate-quality and downballot-lag panel.
- Non-goals: Download state legislative shapefiles, modify canonical election tables, estimate the model, infer missing precinct returns, or overwrite existing raw files.
- Upstream snapshot: Existing `data/raw/historical_statewide_elections/` holdings and the Klarner 1967–2022 candidate/contest archive.
- Read scope: `data/raw/historical_statewide_elections/`; relevant source manifests and Southern calibration documentation/scripts.
- Write scope: `data/raw/southern_sos_elections/`; `data/processed/source_audits/southern_sos_precinct_inventory.csv`; `data/processed/source_audits/southern_sos_download_manifest.csv`; `data/processed/source_audits/southern_sos_unresolved_links.csv`; `data/processed/source_audits/southern_sos_manual_access.csv`; `scripts/acquire_southern_sos_precinct_results.py`; `scripts/tests/test_southern_sos_acquisition.py`; `project_docs/sources/SOUTHERN_SOS_PRECINCT_ACQUISITION.md`; `project_docs/coordination/SOUTHERN-SOS-HISTORICAL-001.md`; `project_docs/coordination/active_tasks.csv`.
- Warehouse mode: `read-only`
- Inputs: Official election archive pages for AL, AR, FL, GA, KY, LA, MS, NC, SC, TN, TX, and VA; existing raw holdings; target general-election cycles 1994–2016, including odd-year LA/MS/VA cycles.
- Outputs: Immutable downloaded source pages/files, checksummed manifest, state-cycle-office coverage inventory, and unresolved/manual-download list.
- Acceptance checks: Existing files are not overwritten; every downloaded item records state, election date/year, official URL, retrieval time, local path, media type, size, and SHA-256; archive HTML is retained; links are restricted to official state/local election domains; duplicate bytes are identified; coverage distinguishes precinct, county, district, and statewide-only results; `python scripts/acquire_southern_sos_precinct_results.py`, tests, and workflow validation pass.
- Handoff recipient: `elections_geography`
- Known risks: Historical pages may be JavaScript-driven, use session-bound URLs, expose county-by-county files, have anti-bot controls, or provide only canvass PDFs without precinct detail.

## Completion handoff

- Acquired all publicly reachable provider files exposed by the configured SOS,
  election-board, official vendor, and official archival routes.
- Recovered previously hidden Arkansas Tally bulk JSON and Louisiana per-race
  `ByPrecinct` CSV endpoints.
- Corrected Kentucky registration-statistics false positives and recovered its
  2006 county recap files through their alternate directory pattern.
- Generated a separate manual-access table for browser blocks, purchase routes,
  official archive gaps, and records-request targets.
- Downstream owner: `elections_geography`; warehouse access remained read-only.
