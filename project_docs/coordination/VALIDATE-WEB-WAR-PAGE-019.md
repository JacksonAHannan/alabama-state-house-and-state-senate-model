# Task contract: VALIDATE-WEB-WAR-PAGE-019

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently validate the WAR-first historical candidate page and the corrected 2010 HD-32 previous-presidential context before public release.
- Acceptance checks: Confirm page title, H1, shared navigation, default map, selected-candidate headline, candidate table, and methodology consistently identify WAR; confirm CQI/Candidate Quality Index are absent from public copy; confirm CMO is retained as a distinct observed comparison; reproduce 2010 HD-32 as Obama +24.05 and Barbara Bigsby Boyd presidential overperformance +18.69; check desktop/mobile rendering, interactions, console errors, accessibility basics, and relevant tests; return an explicit approve/block decision.
- Read scope: `scripts/build_war_story_page.py`; `scripts/site_brand.py`; related tests; `docs/cmo.html`; `docs/cmo-methodology.html`; `docs/data/cmo_v6_southern_`; corrected canonical presidential inputs and audit.
- Write scope: `project_docs/audits/WEB_WAR_PAGE_VALIDATION.md`; `project_docs/coordination/VALIDATE-WEB-WAR-PAGE-019.md`; `project_docs/coordination/active_tasks.csv`.
- Upstream inputs: Local release candidate from `WEB-WAR-PAGE-REBUILD-018` and completed corrected-geography/model refresh tasks 015-017.
- Expected outputs: Independent audit, test evidence, and explicit release decision.
- Warehouse mode: `read-only`
- Handoff recipient: `web_product` and `/root`.

## Validation handoff

- Decision: **BLOCK**
- Completed: 2026-08-26
- Report: `project_docs/audits/WEB_WAR_PAGE_VALIDATION.md`
- Sole blocker: `docs/index.html` visibly labels the WAR route `Historical CMO model`.
- All other gates passed: corrected HD-32 arithmetic and payload, WAR-first page/methodology behavior, distinct supporting CMO, 1440/390 browser and accessibility checks, 19 focused tests, and workflow validation.
- Required next step: repair the source label, rebuild, and submit a narrow post-repair validation task.
