# Task contract: WEB-IDEOLOGY-DYNAMIC-001

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Rewrite the ideology page for a tighter evidence-first narrative and make its charts more responsive and dynamic without changing approved analytical results.
- Acceptance checks: Narrative clearly states thesis, evidence, selection limits, mechanisms, issue findings, and temporal limitations; absolute scatter supports baseline and party filtering; chart updates animate without obscuring values; filters remain keyboard accessible; reduced-motion preference is respected; no stale or editorialized claims; desktop/mobile layout, console, links, and focused/full tests pass; independent release approval.
- Read scope: approved ideology research outputs; current builder/page/tests; shared blue/oxblood theme.
- Write scope: `scripts/build_ideology_thesis_page.py`; `scripts/tests/test_ideology_performance_page.py`; `docs/ideology-performance.html`; `artifacts/site/ideology-performance.html`; this contract and its active-task row.
- Warehouse mode: read-only.
- Upstream inputs: Current approved absolute-ideology and issue-level research exports.
- Expected output: Rewritten, interactive ideology page using unchanged analytical data.
- Handoff recipient: `validation_release`.
