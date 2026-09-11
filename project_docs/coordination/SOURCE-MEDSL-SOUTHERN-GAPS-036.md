# Task contract: SOURCE-MEDSL-SOUTHERN-GAPS-036

- Accountable role: `source_provenance`
- Owner: `/root`
- Status: `complete`
- Objective: Acquire the nine MEDSL individual-state ZIP bundles that close the identified 2022 and 2024 Southern legislative ticket-context gaps, with reproducible provenance and integrity checks.
- Non-goals: Do not alter source bytes after download, normalize election observations, publish warehouse tables, retrain models, or modify `docs/`.
- Upstream snapshot: MEDSL `2022-elections-official` and `2024-elections-official` GitHub repositories as inspected on 2026-08-30.
- Read scope: MEDSL GitHub repository metadata and downloads; current source audit and coordination documents.
- Write scope: `scripts/download_medsl_southern_gap_files.py`; `data/raw/historical_statewide_elections/medsl_github/`; `project_docs/sources/MEDSL_SOUTHERN_GAP_ACQUISITION.md`; `project_docs/coordination/SOURCE-MEDSL-SOUTHERN-GAPS-036.md`; `project_docs/coordination/active_tasks.csv`.
- Warehouse mode: `read-only`.
- Inputs: Four 2022 state bundles (KY, MO, OK, SC) and five 2024 state bundles (AR, KY, OK, SC, TN) published by MEDSL.
- Outputs: Nine immutable ZIP files, a CSV manifest with repository paths, GitHub blob identifiers, retrieval timestamps, byte sizes and SHA-256 hashes, plus a content-validation report.
- Acceptance checks: `python scripts/validate_agent_workflow.py`; `python scripts/download_medsl_southern_gap_files.py`; all nine ZIPs open successfully; expected CSV members and required offices are present; recorded byte sizes and SHA-256 values match local files.
- Handoff recipient: `cmo_model` for normalization and gap-matrix refresh.
- Known risks: GitHub files may be revised upstream; provenance therefore records the Git blob SHA and local SHA-256 rather than relying on mutable branch URLs alone.

## Handoff

- Changed files: `scripts/download_medsl_southern_gap_files.py`; nine ZIPs and `manifest.csv` under `data/raw/historical_statewide_elections/medsl_github/`; `project_docs/sources/MEDSL_SOUTHERN_GAP_ACQUISITION.md`; this contract and its ledger row.
- Generated result: 14,888,837 source bytes across nine validated ZIPs. All required legislative and ticket offices are present, and each selected ticket office contains both major parties.
- Checks run: acquisition script completed twice; ZIP integrity, standardized schema, required-office, major-party, byte-size and SHA-256 checks passed; workflow validation passed.
- Caveats: The sources are downloaded but not normalized or promoted into an analytical mart.
- Downstream action: Refresh the post-2016 gap matrix, then normalize precinct observations and aggregate ticket results to legislative districts.
