# Task contract: VALIDATE-POST2016-PUBLIC-001 — independent headline and public-site validation

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently approve or reject the post-2016 headline forecast and public-copy release candidate before it is pushed to GitHub Pages.
- Non-goals: Do not change model code, forecast values, page builders, public pages, or upstream data; report failures to `/root` for correction.
- Upstream snapshot: Forecast build `e178fb3f50c98c9c312b`, generated site from `WEB-PUBLIC-HEADLINE-COPY-001`, and current commit `3f355b5` plus uncommitted release candidate changes.
- Read scope: `scripts/promote_post2016_headline_forecast.py`; `scripts/run_post2016_polling_cmo_forecast.py`; `scripts/build_2026_forecast_dashboard.py`; `scripts/build_war_story_page.py`; `data/processed/forecast_calibration/post2016_*`; `docs/`; `artifacts/site/`; relevant tests and source manifests.
- Write scope: `project_docs/audits/POST2016_HEADLINE_PUBLIC_VALIDATION.md`; `project_docs/coordination/VALIDATE-POST2016-PUBLIC-001.md`.
- Warehouse mode: `read-only`
- Inputs: The selected 2018-to-2022 forward test, 2026 headline/scenario package, site payload and downloads, current maps, roster, finance, polling, and public methodology.
- Outputs: A signed PASS/FAIL audit covering leakage, scenario arithmetic, model/package hashes, district and chamber reconciliation, missing finance, public-copy accuracy, downloads, navigation, responsive layout, console errors, and publication safety.
- Acceptance checks: Independently rebuild the forecast package and site; verify the headline maps to the selected source scenario; verify both polling-error shifts; compare public exports byte-for-byte; run focused tests; render forecast, methodology, CMO, and ideology pages at desktop and mobile widths; issue an explicit release verdict.
- Handoff recipient: `orchestrator`
- Known risks: The owner explicitly selected a model supported by one Alabama forward holdout; validation should ensure the limitation is prominent rather than treating that editorial decision itself as a software failure.

## Validation handoff

- Verdict: **PASS**
- Completed: 2026-08-22
- Report: `project_docs/audits/POST2016_HEADLINE_PUBLIC_VALIDATION.md`
- Release decision: Approved for publication. Numerical/package reconciliation, corrected finance display, responsive browser behavior, public downloads, focused tests, workflow validation, and the full test suite passed. The one-forward-cycle and partial-cycle-finance limitations remain prominently disclosed.
