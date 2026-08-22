# Task contract: VALIDATE-CMO-ABSOLUTE-COLOR-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently validate that all CMO map views now use a direct linear signed-point color scale and consistent public labeling.
- Non-goals: Edit implementation, recalculate CMO, or change public outputs.
- Upstream snapshot: `WEB-CMO-ABSOLUTE-COLOR-001` release candidate.
- Read scope: CMO builder, generated artifact/public page, approved CMO v4 payload, and focused tests.
- Write scope: `project_docs/audits/CMO_ABSOLUTE_COLOR_VALIDATION.md`; `project_docs/coordination/VALIDATE-CMO-ABSOLUTE-COLOR-001.md`; `project_docs/coordination/active_tasks.csv`.
- Warehouse mode: `read-only`
- Inputs: Regenerated CMO map release candidate.
- Outputs: PASS/FAIL audit of values, colors, labels, modes, browser console, and responsive rendering.
- Acceptance checks: Verify 0 maps to neutral, ±15 to exactly 50% endpoint interpolation, ±30 and beyond to endpoints; verify map mode values remain raw uncensored CMO/governor/presidential points before the visual cap; verify legend, tooltip, and note consistency; verify desktop and exact 497px rendering; run focused tests and workflow validation.
- Handoff recipient: `orchestrator`
- Known risks: Values beyond ±30 are visually capped but must remain uncapped in tooltips.
