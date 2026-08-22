# Task contract: VALIDATE-CAUCUS-EXPLORER-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently validate the interactive caucus explorer for data consistency, interaction behavior, responsive layout, accessibility, and appropriately cautious interpretation.
- Non-goals: Edit page implementation, clustering outputs, or public files.
- Upstream snapshot: `WEB-CAUCUS-EXPLORER-001` release candidate.
- Read scope: caucus builder, generated artifact/public page, validated cluster outputs, and page tests.
- Write scope: `project_docs/audits/CAUCUS_EXPLORER_VALIDATION.md`; `project_docs/coordination/VALIDATE-CAUCUS-EXPLORER-001.md`; `project_docs/coordination/active_tasks.csv`.
- Warehouse mode: `read-only`
- Inputs: Interactive caucus page release candidate.
- Outputs: Independent pass/fail validation report.
- Acceptance checks: Controls update content correctly; candidate details work; payload matches source outputs; Republican caveat remains prominent; desktop and exact 497px layouts have no critical overflow; browser has no errors; focused tests pass.
- Handoff recipient: `web_product`
- Known risks: Generated theme may alter styling or navigation; dense charts may fail on narrow screens.
