# Task contract: WEB-UX-LIBRARY-REBUILD-001 public-site UX rebuild

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Rebuild the public site around the shared design-reference guidance, with simpler navigation, consistent measure language, accessible analytical graphics, responsive comparison views, improved map/detail behavior, compact methodology navigation, and retirement of the stale atlas route.
- Non-goals: No model arithmetic, warehouse schema, raw data, candidate identity, forecast probability, CMO value, or ideology classification changes.
- Upstream snapshot: `master` commit `9d7a9c5`; current approved forecast, CMO v6, CQI, and ideology publication payloads as of 2026-08-24.
- Read scope: `dashboard/`; `scripts/site_brand.py`; public page builders; `docs/`; `artifacts/site/`; `data/processed/forecast_calibration/`; `data/processed/war/`; `research/cmo_ideology/`; `D:/Books/04 - Economics and Finance/UI-UX References/design-library/`.
- Write scope: `dashboard/blue_oxblood_theme.css`; `dashboard/forecast_dashboard.css`; `dashboard/forecast_dashboard.js`; `scripts/site_brand.py`; `scripts/build_2026_forecast_dashboard.py`; `scripts/build_war_story_page.py`; `scripts/build_democratic_transition_page.py`; `scripts/build_blue_oxblood_site.py`; `scripts/tests/test_site_brand.py`; `scripts/tests/test_forecast_dashboard.py`; `scripts/tests/test_cmo_story_historical_cycles.py`; `scripts/tests/test_ideology_performance_page.py`; `scripts/tests/test_published_site_consistency.py`; `artifacts/site/`; `artifacts/blue_oxblood_site/`; `docs/`; `project_docs/coordination/WEB-UX-LIBRARY-REBUILD-001.md`; `project_docs/coordination/active_tasks.csv`.
- Warehouse mode: `read-only`
- Inputs: Approved embedded publication payloads and current HTML generators; design-library guidance on navigation, hierarchy, responsive reflow, analytical density, data visualization, interaction, accessibility, and design systems.
- Outputs: Rebuilt public HTML pages and compatibility redirects; shared UI shell and tokens; responsive and accessibility regression tests; visual-review candidate.
- Acceptance checks: `python scripts/validate_agent_workflow.py`; `python scripts/build_blue_oxblood_site.py`; focused public-page tests pass; all interactive chart points have accessible names; all substantive pages render without document-level overflow at 390, 768, and 1440 CSS pixels; no severe browser errors; model payloads and publication exports remain unchanged.
- Handoff recipient: `validation_release`
- Known risks: Presentation refactors could accidentally alter embedded payloads, change public terminology, obscure dense comparisons, or leave compatibility routes publicly ambiguous. Publication remains blocked pending independent validation.

## Completion handoff

- Changed implementation: shared branding/navigation/footer and responsive theme; forecast map/detail and compact view controls; CMO glossary, responsive explorer, candidate history, and accessible row/detail behavior; ideology comparisons, responsive charts, interactive evidence details, and mobile contents; methods landing and legacy-route redirects.
- Generated outputs: rebuilt `docs/` and corresponding `artifacts/site/` public pages. No model values, warehouse tables, raw evidence, or analytical payloads were changed.
- Checks: deterministic site build passed; focused public-page tests passed; full repository suite passed with 490 tests; workflow validation passed.
- Independent validation: `VALIDATE-WEB-UX-LIBRARY-001` passed exact 1440/768/390 browser gates, keyboard/accessibility checks, contrast inspection, console checks, terminology review, and byte-stable rebuild checks. See `project_docs/audits/WEB_UX_LIBRARY_REBUILD_VALIDATION.md`.
- Caveat: the working tree contains unrelated pre-existing work that was preserved and remains outside this task.
