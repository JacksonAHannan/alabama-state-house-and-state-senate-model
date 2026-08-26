# Task contract: VALIDATE-WEB-IDEOLOGY-WAR-012

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently validate the WAR-first ideology and caucus release candidate before publication.
- Acceptance checks: Rebuild succeeds; focused page, compatibility, and brand tests pass; headline and terminology are internally consistent; Split Ticket credit is visible; internal schema compatibility is preserved; desktop/mobile structure and JavaScript are free of blocking defects; findings are recorded with a pass/fail decision.
- Read scope: `scripts/build_democratic_transition_page_v2.py`; `scripts/build_democratic_transition_page.py`; `scripts/site_brand.py`; relevant tests; current ideology and clustering inputs; `artifacts/site/ideology-performance.html`.
- Write scope: `project_docs/audits/IDEOLOGY_WAR_HEADLINE_VALIDATION.md`; `project_docs/coordination/VALIDATE-WEB-IDEOLOGY-WAR-012.md`; `project_docs/coordination/active_tasks.csv`.
- Upstream inputs: Completed `WEB-IDEOLOGY-WAR-HEADLINE-011` local release candidate.
- Expected outputs: Independent validation report and task status update.
- Warehouse mode: `read-only`
- Handoff recipient: `WEB-IDEOLOGY-WAR-PUBLISH-012`.

## Validation handoff

- Verdict: **PASS**
- Completed: 2026-08-26
- Validated artifact SHA-256: `74D66315684355098892DCB142999CA95F7E526B160460179EB9C90248F9C16E`
- Report: `project_docs/audits/IDEOLOGY_WAR_HEADLINE_VALIDATION.md`
- In-memory rebuild exactly matched the staged artifact; 24 focused tests and workflow validation passed.
- All six adjusted contrasts were independently reconstructed and matched the payload.
- Exact 1440px and 390px browser gates passed after independently verifying the accessibility remediation for 87 issue-chart buttons and 131 similarity-map points.
