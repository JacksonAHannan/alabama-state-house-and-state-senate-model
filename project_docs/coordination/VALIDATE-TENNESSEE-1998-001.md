# Task contract: VALIDATE-TENNESSEE-1998-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete` — V6 passes for conservative experimental staging. SD-33 readable precincts are retained, its 1,193-vote OCR shortfall remains explicit and ineligible, and all source/header/gate/hash checks pass with documented governor-coverage caveats.
- Objective: Independently validate Tennessee 1998 OCR staging for experimental panel integration.
- Non-goals: No parser implementation, panel integration, model rerun, warehouse, or website changes.
- Upstream snapshot: `ELECTION-GEO-TENNESSEE-1998-001` review candidate.
- Read scope: Three official Tennessee PDFs; OCR cache/metadata; parser/tests/outputs/manifest; Klarner archive.
- Write scope: `project_docs/audits/TENNESSEE_1998_PRECINCT_VALIDATION.md`; `project_docs/coordination/VALIDATE-TENNESSEE-1998-001.md`
- Warehouse mode: `read-only`
- Inputs: 47,212 OCR tokens, 3,948 legislative rows, 2,518 governor rows, 116 district reconciliation rows, and a 117-row district-header audit.
- Outputs: Pass/fail staging approval, visual OCR sample findings, usable district inventory, and integration caveats.
- Acceptance checks: Source/cache hashes; deterministic parser rebuild from frozen cache; visual sampling across all reports; all House districts 1-99, odd Senate districts 1-33, and the source-confirmed special Senate District 8 contest are assigned from documented report order; no cross-block state bleed or totals rows; canonical county mapping review; unique keys/nonnegative votes; every eligible district independently satisfies finite max(10,1%) reconciliation; governor incompleteness is quantified and not zero-filled; manifest counts/hashes and eight tests pass.
- Handoff recipient: `forecast_model` historical panel integration.
- Known risks: OCR substitutions; 50 unresolved governor rows; incomplete statewide context; only 59 reconciled districts; token OCR itself is expensive to reproduce.
