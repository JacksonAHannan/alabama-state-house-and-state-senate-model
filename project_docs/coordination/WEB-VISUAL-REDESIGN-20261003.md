# Task contract: WEB-VISUAL-REDESIGN-20261003 maps and graphics redesign

- Accountable role: `web_product`
- Owner: `/root`
- Status: `review`
- Objective: Implement the 2026-10-03 visual audit's recommendations across the forecast, Alabama WAR, Southern WAR, ideology and methodology pages as local release candidates.
- Product/layer and checklist IDs: presentation layer of all four products; `roadmap-05`.
- Dependencies: `FORECAST-VISUAL-EXPORTS-20261003` (environment-versus-seats and forecast-over-time charts); `ALABAMA-SEATS-BY-CYCLE-20261003` (historical seat chart). All other work is unblocked.
- Owner decisions (2026-10-03): local build only; WAR maps use a non-party purple–orange diverging fill (no arrows); majority line only, no supermajority line; build the missing data too.
- Defaults chosen under the audit: drop the CARTO raster basemap and draw a county and city context layer from registered Census files; no new JavaScript dependency (positions precomputed in Python, vanilla JS); ideology issue rows keep the ontology's pole orientation; ratings print the forecast's existing cut-offs; display casing is a presentation transform that leaves source names unchanged.
- Non-goals: no model arithmetic, probability, WAR value, grouping, identity adjudication, warehouse or source changes; no `docs/` writes; no commits or pushes.
- Upstream snapshot: working tree on 2026-10-03: HEAD `178d6f48` plus uncommitted work (candidate identity module, forecast rerun 2026-09-17, historical and career WAR outputs, caucus page builder edits), which is preserved and built upon.
- Read scope: `dashboard/`; page builders; `scripts/site_brand.py`; `data/processed/`; registered Census geography under `data/raw/`; design-reference library.
- Write scope: `dashboard/`; `scripts/site_brand.py`; `scripts/site_geography.py`; `scripts/build_2026_forecast_dashboard.py`; `scripts/build_war_story_page.py`; `scripts/build_southern_war_map.py`; `scripts/build_democratic_caucus_page.py`; `scripts/build_blue_oxblood_site.py`; `scripts/tests/test_site_brand.py`; `scripts/tests/test_site_geography.py`; `scripts/tests/test_war_explorer_style.py`; `scripts/tests/test_forecast_dashboard.py`; `scripts/tests/test_historical_war_story_page.py`; `scripts/tests/test_southern_war_map.py`; `scripts/tests/test_democratic_caucus_page.py`; `data/processed/site_geography/`; `artifacts/site/`; `artifacts/blue_oxblood_site/` (ignored preview stage); `.gitignore` (ignore `artifacts/site/data/`); `project_docs/audits/WEB_VISUAL_REDESIGN_VALIDATION_2026_10_03.md`.
- Warehouse mode: `read-only`.
- Shared records: `project_docs/CANONICAL_PIPELINES.md` and the internal checklist are edited by the primary session under the open orchestrator claim `CHECKLIST-EXECUTION-20260911`.
- Inputs: published-run payloads already consumed by each builder; Census 2020 tabulation blocks (`CENSUS-2020-AL-TABBLOCK20`) and 2024 places (`SOURCE-REGIONS-001`) for the context layer; election-year district geometry already registered for each map.
- Outputs: themed candidate pages under `artifacts/site/`; shared geography artifacts (context layer, tile layouts) with a manifest; tests; validation note.
- Acceptance checks: focused page tests pass; embedded model payload values unchanged except for added presentation fields; pages render at 390, 768 and 1440 CSS pixels without document-level overflow; zero axe WCAG A/AA violations; every interactive mark keyboard-reachable with an accessible name; no console errors; no remote tile or font dependency.
- Review requirement: independent browser and contract review before any publication request.
- Publication authority: none. Owner chose a local build only on 2026-10-03; `build_southern_war_map.py` gains `--artifact-only` so it can run without writing `docs/`.
- Recovery/replay: renderers are deterministic; candidate outputs live only under `artifacts/site/` and `data/processed/site_geography/`.
- Handoff recipient: `validation_release`.
- Known risks: overlapping uncommitted edits in `build_democratic_caucus_page.py`; layout changes hiding dense comparisons; tile layouts implying adjacency that does not exist; colour changes weakening the separation between forecast lean and WAR residual.

## Handoff state (2026-10-03)

- Implemented as local candidates: every recommendation except the two charts blocked on `FORECAST-VISUAL-EXPORTS-20261003` and the "2022 result" map mode, which is not added because plan equivalence is unverified. Details are in `project_docs/audits/WEB_VISUAL_REDESIGN_VALIDATION_2026_10_03.md`.
- Independent browser and contract review completed. All three blockers, the should-fix findings and the minor findings were fixed and rechecked.
- Final focused run: 114 passed, 0 failed across 12 test files. `test_democratic_caucus_page` gives 4 passed, 1 failed and 5 errors on the working tree, because the existing caucus release gate refuses the pending-label run. Those payload tests pass against the approved HEAD run.
- Preview: `python scripts/build_blue_oxblood_site.py --preview` writes `artifacts/blue_oxblood_site/` (ignored). Nothing was written to `docs/` and nothing was committed.
- Status `review`: a second independent pass over the post-fix candidates and the owner's go-ahead are required before any publication request. The ideology candidate also needs the caucus labels approved.

## Handoff state (2026-10-05 UTC)

- **Owner follow-ups done.**
  - The selection box is replaced by a halo outline with the rest of the map dimmed.
  - Map hatching is fixed.
  - The "2022 result" map mode has its plan-equivalence audit.
  - The polling-replay and environment-versus-seats charts are in.
  - The ideology page renders the approved two-group run.
- Details are in the validation note under "Owner follow-ups".
- **Status: review.** A second independent pass over the current candidates is needed before any publication request.
