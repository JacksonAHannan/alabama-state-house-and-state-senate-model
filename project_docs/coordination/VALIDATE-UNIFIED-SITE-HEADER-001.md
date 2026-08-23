# Task contract: VALIDATE-UNIFIED-SITE-HEADER-001 — independent shared-header validation

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently verify that every substantive public page uses the same shared masthead without navigation or responsive regressions.
- Acceptance checks: Forecast, CMO, ideology/caucuses, forecast methodology, CMO methodology, and legacy atlas route have identical header structure, portrait count, wordmark/subtitle, link order, and external destinations; exactly the correct internal route is current; no Candidate Atlas navigation link; no overflow or severe console errors at desktop and mobile widths; page interactions and focused tests pass; explicit PASS/FAIL verdict.
- Read scope: `scripts/site_brand.py`; `dashboard/blue_oxblood_theme.css`; generated `docs/*.html`; relevant web tests.
- Write scope: `project_docs/audits/UNIFIED_SITE_HEADER_VALIDATION.md`; `project_docs/coordination/VALIDATE-UNIFIED-SITE-HEADER-001.md`.
- Upstream inputs: `WEB-UNIFIED-SITE-HEADER-001` release candidate.
- Expected outputs: Independent structural/browser/test audit and publication verdict.
- Warehouse access: read-only.
- Handoff recipient: `orchestrator`.

## Validation handoff

- Verdict: **PASS**
- Completed: 2026-08-23
- Report: `project_docs/audits/UNIFIED_SITE_HEADER_VALIDATION.md`
- Release decision: Approved. All six substantive routes have identical normalized header DOM, one portrait, the same identity and ten-link navigation, correct current-route semantics, no Candidate Atlas navigation, and passing responsive/runtime/interaction/test gates.
