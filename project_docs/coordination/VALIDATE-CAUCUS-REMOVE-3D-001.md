# Task contract: VALIDATE-CAUCUS-REMOVE-3D-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently verify complete removal of the 3D caucus view without regression to the constellation.
- Non-goals: Edit implementation, source data, or public outputs.
- Upstream snapshot: `WEB-CAUCUS-REMOVE-3D-001` release candidate.
- Read scope: Caucus builder, generated artifact/public page, and focused tests.
- Write scope: `project_docs/audits/CAUCUS_REMOVE_3D_VALIDATION.md`; `project_docs/coordination/VALIDATE-CAUCUS-REMOVE-3D-001.md`; `project_docs/coordination/active_tasks.csv`.
- Warehouse mode: `read-only`
- Inputs: Constellation-only caucus page candidate.
- Outputs: PASS/FAIL removal and regression audit.
- Acceptance checks: Confirm generated HTML and live DOM contain no 3D markup, controls, copy, handlers, or styles; verify constellation party/era updates, hover/click/keyboard detail, evidence encoding, desktop/exact-497 layout, browser console, focused tests, and workflow validation.
- Handoff recipient: `orchestrator`
- Known risks: Removal must not disrupt constellation initialization or shared candidate detail.
