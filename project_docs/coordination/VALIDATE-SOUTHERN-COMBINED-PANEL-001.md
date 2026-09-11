# Task contract: VALIDATE-SOUTHERN-COMBINED-PANEL-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently validate the combined HEDA/OpenElections historical Southern panel and strict source/coverage gates.
- Non-goals: No implementation, production model, warehouse, or website changes.
- Upstream snapshot: `FORECAST-SOUTHERN-COMBINED-PANEL-001` review candidate.
- Read scope: Combined-panel pipeline/tests/outputs/manifest and both validated upstream staging products.
- Write scope: `project_docs/audits/SOUTHERN_COMBINED_PANEL_VALIDATION.md`; `project_docs/coordination/VALIDATE-SOUTHERN-COMBINED-PANEL-001.md`
- Warehouse mode: `read-only`
- Inputs: 1,805 HEDA strict rows and 908 OpenElections strict candidates before overlap.
- Outputs: Pass/fail experimental panel approval.
- Acceptance checks: Rebuild deterministically; validate precinct allocation and legislative-turnout join coverage; HEDA overlap precedence; all explicit cycle/district exclusions; 2,273 unique strict rows and 468 additive OE rows; manifest hashes/counts; focused tests pass.
- Handoff recipient: `cmo_model`
- Known risks: Only secondary sources; 1994–1998 still absent; Georgia 2014 remains sensitivity-only.
