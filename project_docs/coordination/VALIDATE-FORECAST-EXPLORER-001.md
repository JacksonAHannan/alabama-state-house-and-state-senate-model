# Task contract: VALIDATE-FORECAST-EXPLORER-001 — independent public-site validation

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently validate the chamber paths, competitive-race overview, expanded district profiles, component comparisons, and candidate CMO timelines prepared by `WEB-FORECAST-EXPLORER-001`.
- Acceptance checks: Reproduce payload arithmetic and source joins; verify both chambers and all scenarios; confirm current CMO scores power timelines; inspect desktop and mobile rendering, keyboard controls, overflow, and browser errors; confirm no model arithmetic changed and no stale Candidate Atlas returned; issue PASS or FAIL with concrete findings.
- Read scope: `scripts/build_2026_forecast_dashboard.py`; `dashboard/forecast_dashboard.js`; `dashboard/forecast_dashboard.css`; `scripts/build_war_story_page.py`; relevant tests and generated `docs/`; current forecast, CMO, roster, election-context, and demographic inputs.
- Write scope: `project_docs/audits/FORECAST_EXPLORER_VALIDATION.md`; `project_docs/coordination/VALIDATE-FORECAST-EXPLORER-001.md`.
- Upstream inputs: `WEB-FORECAST-EXPLORER-001` release candidate in the shared workspace.
- Expected outputs: Independent validation report with commands, observations, and release recommendation.
- Warehouse access: read-only.
- Handoff recipient: `/root`.

## Validation handoff

- Verdict: **PASS**
- Completed: 2026-08-23
- Report: `project_docs/audits/FORECAST_EXPLORER_VALIDATION.md`
- Release decision: Approved. Forecast/component arithmetic, all chamber/scenario paths, profile and CMO-v6 joins, provenance downloads, responsive rendering, keyboard focus, console behavior, focused tests, and workflow validation pass.
