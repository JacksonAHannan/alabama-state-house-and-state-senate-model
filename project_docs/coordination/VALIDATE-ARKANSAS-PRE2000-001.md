# Task contract: VALIDATE-ARKANSAS-PRE2000-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently validate official Arkansas 1994-1998 precinct staging and its Klarner reconciliation gate.
- Non-goals: No implementation, combined-panel integration, model rerun, warehouse, or website changes.
- Upstream snapshot: `ELECTION-GEO-ARKANSAS-PRE2000-001` review candidate.
- Read scope: Arkansas raw workbooks/ZIP and acquisition manifest; parser/tests/outputs/manifest; Klarner archive.
- Write scope: `project_docs/audits/ARKANSAS_PRE2000_PRECINCT_VALIDATION.md`; `project_docs/coordination/VALIDATE-ARKANSAS-PRE2000-001.md`
- Warehouse mode: `read-only`
- Inputs: Three official Arkansas general-election workbooks and 66,285 staged observations.
- Outputs: Pass/fail staging approval, cycle-specific eligibility counts, and caveats for panel integration.
- Acceptance checks: Raw hashes unchanged; independent deterministic rebuild; summary/grand-total sheets and totals columns excluded; contest inheritance does not bleed between blocks; votes nonnegative; unique observation keys; statewide context totals plausible; district totals/reconciliation statuses reproduce; all 179 eligible rows satisfy the declared tolerance; manifest counts/hashes and focused tests pass.
- Handoff recipient: `forecast_model` combined-panel integration.
- Known risks: Irregular 1994 labels, absent unopposed vote rows, incomplete county/district coverage, source/Klarner disagreements.
