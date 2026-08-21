# Task contract: VALIDATE-IDEOLOGY-BORDERS-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`

## Handoff

- Outcome: `PASS`
- Evidence: all contracted panel families have computed left/right edges at
  desktop and exact 497 px mobile widths; nested dividers remain coherent;
  both widths have zero document overflow; controls and console pass; focused
  tests pass 11/11.
- Changed implementation/public/model files: none.
- Report: `project_docs/audits/IDEOLOGY_BORDER_VALIDATION.md`.
- Downstream invalidation: none.
- Next action: web owner may publish the remediated ideology page.
- Objective: Independently validate the ideology-page panel-border remediation at desktop and mobile widths.
- Acceptance checks: Summary, statistics, callout, formula, mini-card, issue-note, evidence-summary, and method panels have visible left/right edges; nested borders remain visually coherent; no horizontal overflow; interactions and console remain clean; focused tests pass.
- Read scope: `scripts/build_ideology_thesis_page.py`; `docs/ideology-performance.html`; `artifacts/site/ideology-performance.html`; existing ideology screenshots and tests.
- Write scope: `project_docs/audits/IDEOLOGY_BORDER_VALIDATION.md`; this contract and its active-task row only.
- Warehouse mode: read-only.
- Upstream inputs: Current ideology analysis outputs and rebuilt blue/oxblood page.
- Expected output: Independent PASS/FAIL report with viewport evidence and actionable findings.
- Handoff recipient: `/root`.
