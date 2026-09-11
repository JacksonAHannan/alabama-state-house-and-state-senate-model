# Task contract: VALIDATE-SOUTHERN-EXTENDED-TENNESSEE-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete` — PASS for experimental panel use. The 2,383 prior rows are value-identical, 19 Tennessee rows pass all four independently recomputed gates, allocation and coverage invariants hold, hashes are current, rebuilds are deterministic, and focused tests pass 4/4.
- Objective: Independently validate the Tennessee 1998 extension before it is used by a model tournament.
- Non-goals: No model selection, canonical warehouse, website, or production forecast changes.
- Upstream snapshot: `FORECAST-SOUTHERN-EXTENDED-TENNESSEE-001` review candidate, build ID recorded in its manifest.
- Read scope: Tennessee staging and integration code, tests, manifests, prior 2,383-row panel, Tennessee candidate/coverage/allocation outputs, and v2 panel.
- Write scope: `project_docs/audits/SOUTHERN_EXTENDED_TENNESSEE_VALIDATION.md`; `project_docs/coordination/VALIDATE-SOUTHERN-EXTENDED-TENNESSEE-001.md`.
- Warehouse mode: `read-only`
- Inputs: Review-candidate source, generated outputs, and immutable upstream inputs referenced by manifests.
- Outputs: A PASS/FAIL audit with exact evidence and any blocking findings.
- Acceptance checks: Independently rebuild in temporary space; verify all 2,383 prior rows and values are preserved; verify Tennessee row counts and unique keys; recompute all four admission gates; confirm zero-turnout rows do not allocate context; confirm split allocations conserve observed votes; validate coverage bounds, hashes, determinism, and focused tests.
- Handoff recipient: `/root` and then `cmo_model` only after PASS.
- Known risks: Tennessee OCR omissions may make valid contests ineligible; the strict sample is expected to be substantially smaller than all reconciled districts.
