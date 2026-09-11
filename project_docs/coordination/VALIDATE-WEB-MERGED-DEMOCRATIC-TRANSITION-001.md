# Task contract: VALIDATE-WEB-MERGED-DEMOCRATIC-TRANSITION-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently validate the merged ideology and Democratic-caucus release candidate before publication.
- Read scope: `scripts/build_democratic_transition_page.py`; `scripts/build_ideology_thesis_page.py`; `scripts/build_ideology_performance_page.py`; `scripts/build_caucus_analysis_page.py`; `scripts/build_blue_oxblood_site.py`; `scripts/site_brand.py`; focused tests; validated ideology and cluster inputs; release-candidate HTML.
- Write scope: `project_docs/validation/WEB_MERGED_DEMOCRATIC_TRANSITION_VALIDATION.md`; this contract; the matching active-task ledger row.
- Warehouse mode: `read-only`
- Upstream inputs: `WEB-MERGED-DEMOCRATIC-TRANSITION-001` release candidate and implementation audit.
- Expected output: Independent PASS/FAIL report with source-freshness, analytical-label, redirect, interaction, console, accessibility, responsive-layout, and publication-safety checks.
- Acceptance checks: Verify current 274-member payload and 115 Democratic observations; verify headline values and cycle composition against source CSVs; verify no 3D or stale standalone caucus UI; exercise controls and candidate selection in a browser; test desktop and 390/497px widths; verify no severe console errors; verify builders do not read from `docs/` upstream.
- Handoff recipient: `/root`.
