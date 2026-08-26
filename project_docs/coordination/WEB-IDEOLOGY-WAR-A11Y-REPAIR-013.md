# Task contract: WEB-IDEOLOGY-WAR-A11Y-REPAIR-013

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Add accessible names to every focusable issue-explorer and similarity-map point identified by independent release validation.
- Acceptance checks: Every focusable issue point names candidate, race, group, issue position, and selected measure; every focusable similarity point names candidate, race, group, and evidence coverage; focused tests, JavaScript validation, and headless-browser accessibility counts pass.
- Read scope: Current WAR-first page builder, tests, and validation feedback from `VALIDATE-WEB-IDEOLOGY-WAR-012`.
- Write scope: `scripts/build_democratic_transition_page_v2.py`; `scripts/tests/test_ideology_performance_page.py`; `artifacts/site/ideology-performance.html`; `project_docs/coordination/WEB-IDEOLOGY-WAR-A11Y-REPAIR-013.md`; `project_docs/coordination/active_tasks.csv`.
- Upstream inputs: Completed `WEB-IDEOLOGY-WAR-HEADLINE-011` and failed initial accessibility gate.
- Expected outputs: Repaired local release candidate ready for independent revalidation.
- Warehouse mode: `read-only`
- Handoff recipient: `VALIDATE-WEB-IDEOLOGY-WAR-012`.

## Handoff

- Added dynamic accessible names to all issue-explorer points, naming candidate, race, group, issue position, and selected performance measure.
- Added button roles and dynamic accessible names to all similarity-map points, naming candidate, race, group, and issue-dimension coverage.
- Validation: 10 focused tests passed; at both 1440px and 390px, all 87 issue points and all 131 similarity points were named; browser console errors were zero.
