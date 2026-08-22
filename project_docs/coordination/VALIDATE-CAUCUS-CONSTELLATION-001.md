# Task contract: VALIDATE-CAUCUS-CONSTELLATION-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently validate the all-issue caucus constellation, evidence encoding, interaction behavior, responsive rendering, and retained three-issue view.
- Non-goals: Edit implementation, source data, model assignments, or public outputs.
- Upstream snapshot: `WEB-CAUCUS-CONSTELLATION-001` release candidate.
- Read scope: caucus page builder, generated artifact/public page, validated cluster assignments and issue matrices, and focused tests.
- Write scope: `project_docs/audits/CAUCUS_CONSTELLATION_VALIDATION.md`; `project_docs/coordination/VALIDATE-CAUCUS-CONSTELLATION-001.md`; `project_docs/coordination/active_tasks.csv`.
- Warehouse mode: `read-only`
- Inputs: All-issue constellation release candidate and validated clustering outputs.
- Outputs: PASS/FAIL audit with coordinate reproduction, cluster/coverage checks, interaction checks, browser errors, and responsive screenshots or measurements.
- Acceptance checks: Independently reproduce deterministic coordinates from the clustering matrix; verify all classified candidate-cycles appear with correct cluster colors and evidence encoding; verify envelopes and centroids update by party and era; verify hover/click/keyboard detail and view tabs; verify the secondary three-issue chart remains functional; verify desktop and exact 497px layouts have no overflow or console errors; run focused tests and workflow validator.
- Handoff recipient: `orchestrator`
- Known risks: Projection loss, visual overlap, imputation sensitivity, and candidate-cycle repetition must remain explicit.
