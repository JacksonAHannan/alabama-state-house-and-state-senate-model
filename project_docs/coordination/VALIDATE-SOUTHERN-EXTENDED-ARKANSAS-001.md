# Task contract: VALIDATE-SOUTHERN-EXTENDED-ARKANSAS-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently validate the Arkansas 1994-1998 extension to the historical Southern panel.
- Non-goals: No implementation, model rerun, warehouse, production forecast, or website changes.
- Upstream snapshot: `FORECAST-SOUTHERN-EXTENDED-ARKANSAS-001` review candidate.
- Read scope: Validated combined panel; validated Arkansas staging; extension script/tests/outputs/manifest; Klarner archive.
- Write scope: `project_docs/audits/SOUTHERN_EXTENDED_ARKANSAS_VALIDATION.md`; `project_docs/coordination/VALIDATE-SOUTHERN-EXTENDED-ARKANSAS-001.md`
- Warehouse mode: `read-only`
- Inputs: 2,273 existing rows, 119 reconciled Arkansas rows, and 110 proposed strict admissions.
- Outputs: Pass/fail experimental panel approval and integration caveats.
- Acceptance checks: Independent deterministic rebuild; all existing rows unchanged; allocation weights and joined context votes conserve; every Arkansas admission passes reconciliation, contested two-party, finite baseline, and 95% turnout-join gates; exact counts 2,273 + 110 = 2,383; unique keys; hashes/counts and focused tests pass.
- Handoff recipient: `cmo_model`
- Known risks: Arkansas-only pre-2000 extension; uneven district coverage; turnout-share allocation; secondary Klarner outcomes.
