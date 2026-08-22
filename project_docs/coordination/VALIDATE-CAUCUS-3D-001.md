# Task contract: VALIDATE-CAUCUS-3D-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently validate the three-dimensional caucus visualization, its axis derivation, interaction behavior, coverage disclosure, and responsive rendering.
- Non-goals: Edit implementation, data, or public outputs.
- Upstream snapshot: `WEB-CAUCUS-3D-001` release candidate.
- Read scope: caucus builder, generated artifact/public page, cluster profiles/assignments, and focused tests.
- Write scope: `project_docs/audits/CAUCUS_3D_VALIDATION.md`; `project_docs/coordination/VALIDATE-CAUCUS-3D-001.md`; `project_docs/coordination/active_tasks.csv`.
- Warehouse mode: `read-only`
- Inputs: Rotatable 3D caucus page candidate.
- Outputs: Independent pass/fail report.
- Acceptance checks: Party axes exactly match top three profile ranges; centroid and complete-case positions use source values; sparse coverage is disclosed; drag/reset, hover/click, party/era changes work; no browser errors or desktop/497px overflow; tests pass.
- Handoff recipient: `web_product`
- Known risks: Sparse complete cases, point occlusion, and perspective ambiguity.
