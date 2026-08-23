# Task contract: VALIDATE-CMO-MODE-SCALE-001 - independent mode-display validation

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently validate the mode-specific CMO map scales and synchronized selected-candidate headline display.
- Non-goals: No implementation, model, warehouse, or publication edits.
- Upstream snapshot: `WEB-CMO-MODE-SCALE-001` release candidate.
- Read scope: Updated builder, tests, generated CMO page, and current CMO payload.
- Write scope: `project_docs/audits/CMO_MODE_SCALE_VALIDATION.md`; this contract.
- Warehouse mode: `read-only`.
- Inputs: Local CMO release candidate produced by the implementation task.
- Outputs: PASS/FAIL audit with mode-by-mode palette, legend, headline-value, responsiveness, and interaction checks.
- Acceptance checks: All four modes use the intended scale and headline measure; candidate quality is visually distinct from CMO; missing values remain unavailable; console and focused tests pass.
- Handoff recipient: `/root`.
- Known risks: DOM state can retain a stale selected candidate when a mode changes; validation must switch modes after selection.

## Validation handoff

- Verdict: **PASS**
- Completed: 2026-08-23
- Report: `project_docs/audits/CMO_MODE_SCALE_VALIDATION.md`
- Release decision: Approved. Mode-specific values, signs, percentiles, scales, palettes, legends, fills, missingness, selected-candidate synchronization, responsive interactions, runtime behavior, focused tests, and workflow validation pass.
