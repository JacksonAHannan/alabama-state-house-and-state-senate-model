# Task contract: WEB-WAR-PAGE-REBUILD-018

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`

## Handoff

- Rebuilt the historical candidate page with WAR as the headline measure and CMO as a separately labeled observed comparison.
- Rebuilt the methodology copy, shared navigation, methods landing, and responsive Blue/Oxblood publication candidate.
- Corrected the 2010 HD-32 presidential context to Obama +24.05 and Barbara Bigsby Boyd's presidential-relative overperformance to +18.69.
- Focused and publication consistency tests pass; desktop and 390 px browser checks show no horizontal overflow.
- Awaiting independent `validation_release` approval under `VALIDATE-WEB-WAR-PAGE-019` before publication.
- Objective: Rebuild the historical candidate page as the WAR page, promote the partial-pooled candidate-quality estimate to the headline display, retain CMO and raw ticket comparisons as distinct supporting measures, and display the corrected presidential context.
- Acceptance checks: Page title, H1, primary navigation, default map, candidate headline, first result-table metric, and methodology identify WAR; no public CQI or Candidate Quality Index label remains; CMO remains explicitly labeled as observed ticket overperformance; the default WAR map uses its own scale; selected-candidate headline follows the active measure; 2010 HD-32 shows the prior presidential result as Democratic and approximately D+24.1 with Democratic raw presidential overperformance approximately +18.7; Split Ticket receives linked naming credit; focused UI tests and browser checks pass.
- Read scope: Completed `CMO-WAR-CONTEXT-REFRESH-017` outputs, current shared theme, current WAR/CMO page builder, methodology content, and existing public-page tests.
- Write scope: `scripts/build_war_story_page.py`; `scripts/site_brand.py`; `scripts/tests/test_cmo_story_historical_cycles.py`; `scripts/tests/test_site_brand.py`; `scripts/tests/test_published_site_consistency.py`; `artifacts/site/alabama-legislative-cmo.html`; `artifacts/site/alabama-legislative-war-legacy.html`; `artifacts/blue_oxblood_site/`; `docs/`; `project_docs/coordination/WEB-WAR-PAGE-REBUILD-018.md`; `project_docs/coordination/active_tasks.csv`.
- Upstream inputs: Refreshed v6 Southern-prior candidate/race/quality files, corrected canonical presidential context, and the blue/oxblood shared site shell.
- Expected outputs: A local and publication-ready WAR page, WAR methodology page, refreshed downloadable data, and regression tests.
- Warehouse mode: `read-only`
- Handoff recipient: `validation_release`.
