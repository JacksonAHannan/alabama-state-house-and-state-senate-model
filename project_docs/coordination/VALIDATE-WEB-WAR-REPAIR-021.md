# Task contract: VALIDATE-WEB-WAR-REPAIR-021

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Revalidate the repaired WAR release candidate and confirm the previous sole blocking naming issue is resolved without regressions.
- Acceptance checks: Confirm `Historical WAR model` appears and `Historical CMO model` does not; rerun the focused workflow and site tests; perform a targeted browser smoke check; return explicit approve/block decision.
- Read scope: Repaired forecast source and generated page, completed prior audit, WAR page/methodology, and relevant focused tests.
- Write scope: `project_docs/audits/WEB_WAR_REPAIR_VALIDATION.md`; `project_docs/coordination/VALIDATE-WEB-WAR-REPAIR-021.md`; `project_docs/coordination/active_tasks.csv`.
- Upstream inputs: Completed `WEB-WAR-LINK-REPAIR-020` candidate and blocked audit `VALIDATE-WEB-WAR-PAGE-019`.
- Expected outputs: Focused independent release approval or a concrete blocking defect.
- Warehouse mode: `read-only`
- Handoff recipient: `/root` for publication.

## Validation handoff

- Verdict: **APPROVE**
- Completed: 2026-08-26
- Evidence: `project_docs/audits/WEB_WAR_REPAIR_VALIDATION.md`
- Summary: Exact source/artifact scans show `Historical WAR model` once and `Historical CMO model` zero times in every repaired forecast target. Workflow validation and all 19 focused tests pass. Desktop and 390px browser smoke checks found no overflow or severe console errors, and the previously validated Boyd/HD-32 WAR, CMO, and 2008 presidential context remain intact.
