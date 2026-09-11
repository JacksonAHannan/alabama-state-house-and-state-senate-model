# Task contract: WEB-IDEOLOGY-COVERAGE-REFRESH-001

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Rebuild the legislator atlas, ideology analysis, and caucus explorer from the repaired, validated evidence with no stale embedded payloads.
- Read scope: Current reviewed ideology/caucus outputs, career and pre-election marts, web builders, shared styles, and page tests.
- Write scope: `scripts/build_legislator_ideology_page.py`; `dashboard/legislator_ideology.js`; `scripts/tests/test_legislator_ideology_page.py`; `scripts/tests/test_caucus_analysis_page.py`; `artifacts/site/legislators.html`; `artifacts/site/ideology-performance.html`; `artifacts/site/caucuses.html`; `docs/legislators.html`; `docs/ideology-performance.html`; `docs/caucuses.html`; this contract and ledger row.
- Warehouse mode: `read-only`
- Upstream inputs: `IDEOLOGY-COVERAGE-RERUN-001` review candidate, promoted only after validation PASS.
- Expected outputs: Fresh pages distinguishing focal-election scores from career-through-2026 profiles and using current analysis/cluster payloads.
- Acceptance checks: Builders and focused page tests pass; no old embedded data; career/pre-election labels are explicit; browser console and readability checks pass.
- Handoff recipient: `validation_release`.
