# Task contract: VALIDATE-PUBLISHED-MERGED-DEMOCRATIC-TRANSITION-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently validate the themed public copies after approved ideology/caucus publication.
- Read scope: `docs/ideology-performance.html`; `docs/caucuses.html`; all public-page navigation; approved artifact and prior validation report; published-site tests.
- Write scope: `project_docs/validation/PUBLISHED_MERGED_DEMOCRATIC_TRANSITION_VALIDATION.md`; this contract; matching active-task ledger row.
- Warehouse mode: `read-only`
- Upstream inputs: Approved `WEB-MERGED-DEMOCRATIC-TRANSITION-001` artifact and completed public site build.
- Expected output: Final PASS/FAIL report for public artifact equality, shared-theme behavior, navigation, redirect, browser runtime, and responsive layout.
- Acceptance checks: Run published consistency tests; verify 115 Democratic rows/points; verify no document overflow at 390/497/desktop; verify no severe console errors; verify all public navs have one merged ideology link and no standalone caucus link; verify redirect target.
- Handoff recipient: `/root`.
