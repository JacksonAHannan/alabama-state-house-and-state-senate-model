# Task contract: VALIDATE-HEADER-ATLAS-CLEANUP-001 — independent masthead and navigation validation

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently validate the corrected forecast identity lockup and removal of stale Candidate Atlas links from the Ideology & Caucuses page.
- Acceptance checks: Forecast has one portrait adjacent to the name/subtitle at desktop and mobile widths; spacing matches the compact pattern on CMO/ideology pages; Ideology & Caucuses has no `legislators.html`/Candidate Atlas links in its header or footer; navigation and page scripts work; no overflow or severe console errors; focused tests pass; explicit PASS/FAIL verdict.
- Read scope: `dashboard/blue_oxblood_theme.css`; `scripts/build_democratic_transition_page.py`; `docs/index.html`; `docs/ideology-performance.html`; relevant web tests.
- Write scope: `project_docs/audits/HEADER_ATLAS_CLEANUP_VALIDATION.md`; `project_docs/coordination/VALIDATE-HEADER-ATLAS-CLEANUP-001.md`.
- Upstream inputs: `WEB-HEADER-ATLAS-CLEANUP-001` release candidate.
- Expected outputs: Independent browser/test audit and publication verdict.
- Warehouse access: read-only.
- Handoff recipient: `orchestrator`.

## Validation handoff

- Verdict: **PASS**
- Completed: 2026-08-22
- Report: `project_docs/audits/HEADER_ATLAS_CLEANUP_VALIDATION.md`
- Release decision: Approved. The forecast renders one compact portrait identity lockup; Ideology & Caucuses contains no Candidate Atlas header/footer copy or links; responsive, navigation, runtime, focused-test, and workflow gates passed.
