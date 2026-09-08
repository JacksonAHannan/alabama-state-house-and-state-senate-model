# Task contract: ALABAMA-2018-CERTIFIED-SOURCE-20260908

- Accountable role: `source_provenance`
- Owner: `/root`
- Status: `complete`
- Objective: Parse the official Alabama 2018 certified legislative canvass and reconcile it to the official precinct workbooks while preserving every blank source cell as unknown.
- Product/layer and checklist IDs: Southern historical WAR source evidence; advances `southern-06` without changing eligibility or scores.
- Dependencies: Official Alabama SOS 2018 precinct ZIP and newly acquired certified canvass PDF with exact hashes.
- Non-goals: No warehouse registration or mutation, canonical authority change, candidate rating, model fit, source-lineage attachment, manifest promotion, publication or release approval.
- Upstream snapshot: precinct ZIP SHA256 `fb467ac457e8ac30c3d817afa4ea94f72ca6b4d3bab6f677bee624c579946c4e`; certified PDF SHA256 `a83be9be26ac195989bf94ad5097e4269f516674f645373526a9d6621f310044`.
- Read scope: The two immutable 2018 SOS sources, the missingness-preserving 2022 adapter utilities, warehouse schema contracts and current Southern readiness evidence.
- Write scope: `scripts/alabama_2018_official_results.py`; `scripts/tests/test_alabama_2018_official_results.py`; `project_docs/audits/ALABAMA_2018_CERTIFIED_CANVASS_ACQUISITION.json`; `project_docs/audits/ALABAMA_2018_CERTIFIED_SOURCE_RECONCILIATION.json`; this contract and active-task row.
- Warehouse mode: `read-only`
- Inputs: All 67 county workbooks in the official precinct archive and all 192 pages of the certified canvass.
- Outputs: Reusable source adapter, focused fixtures and a compact exact reconciliation audit.
- Acceptance checks: Exact 105 House plus 35 Senate district coverage; one certified write-in record per contest; unique physical precinct cells; blanks retained as unknown; exact all-party/name/category reconciliation or explicit review rows; source/code hashes recorded. Four focused tests passed in 16.50 seconds, including audit replay.
- Review requirement: Focused self-checks; warehouse adoption and lineage repair require separate integration review.
- Publication authority: `none`
- Recovery/replay: Read-only source parsing. No generated analytical artifact or database recovery is required.
- Handoff recipient: `warehouse_integrator`
- Known risks: Exact certified totals do not by themselves prove which upstream file produced each existing canonical candidate row; source bridging remains separate.

## Handoff

The adapter covers all 140 legislative districts and 352 certified rows. It
aligns the canvass's surname labels to fuller precinct names only at unique exact
chamber/district/party/category grain. Of 38,699 physical precinct cells, 24,912
are blank and remain unknown. The comparison has 322 exact totals and 30 review
rows; four current strict Southern races intersect six major-party discrepancies
with 12 votes of aggregate absolute difference. The cohort is ready for reviewed
warehouse source-set staging, not canonical promotion.
