# Task contract: SOURCE-LOUISIANA-ALL-STAGES-039 — Louisiana legislative stages

- Accountable role: `source_provenance`
- Owner: `/root`
- Status: `complete`
- Objective: Acquire and register precinct-level Louisiana legislative results for both the first round and runoff in every 1995–2023 regular legislative cycle exposed by the Secretary of State portal.
- Non-goals: No canonical warehouse writes, model fitting, website publication, or candidate-identity adjudication.
- Upstream snapshot: Louisiana SOS graphical-results feed inspected 2026-08-30 and existing immutable Louisiana downloads through 2015.
- Read scope: `data/raw/southern_sos_elections/LA/`; `scripts/acquire_southern_sos_precinct_results.py`; Louisiana SOS public result endpoints.
- Write scope: `scripts/acquire_southern_sos_precinct_results.py`; `scripts/tests/test_southern_sos_acquisition.py`; `data/raw/southern_sos_elections/LA/`; `data/processed/source_audits/southern_sos_download_manifest.csv`; `data/processed/source_audits/southern_sos_precinct_inventory.csv`; `data/processed/source_audits/southern_sos_unresolved_links.csv`; `project_docs/sources/LOUISIANA_LEGISLATIVE_RESULTS_ACQUISITION.md`; `project_docs/coordination/SOURCE-LOUISIANA-ALL-STAGES-039.md`
- Warehouse mode: `read-only`
- Inputs: Official Louisiana SOS `ElectionRaces.htm` indexes and `csv/ByPrecinct_<race_id>.csv` exports for the 1995–2023 first-round and runoff dates.
- Outputs: Immutable election-date-indexed precinct CSVs, source manifest rows with election dates/stages, coverage audit, tests, and acquisition note.
- Acceptance checks: `python scripts/validate_agent_workflow.py`; `python scripts/acquire_southern_sos_precinct_results.py --louisiana-legislative-only`; `python -m pytest scripts/tests/test_southern_sos_acquisition.py -q`; all 16 configured dates have a readable race index and all 913 listed legislative contests have valid precinct CSVs.
- Handoff recipient: `cmo_model`
- Known risks: Louisiana's open-primary system requires preserving round identity; a district may be decided in the first round or advance to a runoff, and same-party runoffs must not be collapsed prematurely.

## Handoff

- Outcome: `accepted candidate`
- Upstream snapshot used: Louisiana SOS graphical-results feed retrieved 2026-08-30 and pre-existing immutable Louisiana files through 2015.
- Changed source files: `scripts/acquire_southern_sos_precinct_results.py`; `scripts/tests/test_southern_sos_acquisition.py`; `project_docs/sources/LOUISIANA_LEGISLATIVE_RESULTS_ACQUISITION.md`.
- Generated outputs: 16 race indexes and 913 precinct contest CSVs under `data/raw/southern_sos_elections/LA/`; three Louisiana acquisition audit CSVs under `data/processed/source_audits/`.
- Commands run: `python scripts/acquire_southern_sos_precinct_results.py --louisiana-legislative-only`; `python -m pytest scripts/tests/test_southern_sos_acquisition.py -q`; `python scripts/validate_agent_workflow.py`.
- Validation results: 929 files registered with distinct SHA-256 hashes; all 16 dates complete; zero unresolved downloads; nine acquisition tests passed.
- Manual decisions: None.
- Assumptions and limitations: The acquisition includes two unexpired-term contests from 1999 as raw evidence; downstream regular-cycle normalization must identify them explicitly.
- Warehouse changes requested: None; source files and audits remain outside the canonical warehouse.
- Downstream invalidation: Southern Louisiana outcome staging and gap audit required rebuild.
- Reviewer: Source acceptance checks completed locally; model promotion remains subject to `validation_release`.
- Next action: Normalize final-stage outcomes while retaining first-round candidate observations.
