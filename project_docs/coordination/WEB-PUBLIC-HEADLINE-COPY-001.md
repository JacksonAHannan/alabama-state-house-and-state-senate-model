# Task contract: WEB-PUBLIC-HEADLINE-COPY-001 — headline dashboard and public copy audit

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Publish the post-2016 headline forecast with Democratic- and Republican-favorable polling-error views, and rewrite public pages so explanations serve readers rather than describe internal version history or pipeline state.
- Non-goals: Do not change canonical data, CMO arithmetic, ideology estimates, the forecast model package, or visual design beyond copy needed for clarity.
- Upstream snapshot: Forecast build `e178fb3f50c98c9c312b`, current CMO data products, and the current Blue/Oxblood public site at commit `3f355b5`.
- Read scope: `data/processed/forecast_calibration/post2016_headline_v1_*`; current public builders, pages, tests, and public data exports.
- Write scope: `scripts/build_2026_forecast_dashboard.py`; `scripts/build_war_story_page.py`; `scripts/tests/test_forecast_dashboard.py`; `scripts/tests/test_published_site_consistency.py`; `scripts/tests/test_cmo_story_historical_cycles.py`; `artifacts/site/`; `artifacts/blue_oxblood_site/`; `docs/`; `project_docs/coordination/WEB-PUBLIC-HEADLINE-COPY-001.md`.
- Warehouse mode: `read-only`
- Inputs: The release-candidate forecast package, current roster/finance/map inputs, and all generated public pages.
- Outputs: Updated forecast, forecast methodology, CMO page and methodology, compatible public downloads, and an audit with no stale internal-only claims.
- Acceptance checks: Dashboard payload matches build `e178fb3f50c98c9c312b`; all three forecast views reconcile; modeled candidate finance displays match the model inputs and preserve missing observations; maps and interactions remain functional; public copy contains no stale version-transition language, raw build IDs, pipeline jargon, or claims that the headline excludes incumbency and finance; focused and full-site tests pass.
- Handoff recipient: `validation_release`
- Known risks: Existing builders contain unreachable legacy templates; the audit targets rendered public content and operative source strings without refactoring unrelated dead code.

## Handoff

- Forecast payload uses build `e178fb3f50c98c9c312b` and contains Headline, Dem scenario, and Rep scenario views for the same 48 races.
- Four changed public HTML pages and all 14 checked release/model artifacts reproduce byte-for-byte across consecutive builds.
- Public pages contain none of the version-transition and internal release phrases named in the acceptance checks.
- Focused release tests: 26 passed. Full repository suite: 478 passed with 11 pre-existing warnings.
- Independently approved by `VALIDATE-POST2016-PUBLIC-001` for publication.
