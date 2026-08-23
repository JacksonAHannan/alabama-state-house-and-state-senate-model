# Task contract: WEB-FORECAST-EXPLORER-001 — forecast and CMO exploration

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Add chamber-majority paths, a competitive-race overview, expanded district profiles, forecast-component comparisons, and candidate CMO career timelines to the public forecast without changing model arithmetic.
- Acceptance checks: Both chambers and all three forecast scenarios render valid majority paths and competitive-race lists; district profiles expose current baseline, prior result, status, finance, and available demographic context; component views reconcile exactly to each displayed final margin; candidate timelines use the current published CMO field and do not restore the stale Candidate Atlas; focused tests, full site build, browser checks, and independent validation pass.
- Read scope: Current forecast/CMO builders and tests; versioned forecast calibration outputs; current CMO candidate output; roster, finance, election-context, and demographic processed data.
- Write scope: `scripts/build_2026_forecast_dashboard.py`; `dashboard/forecast_dashboard.js`; `dashboard/forecast_dashboard.css`; `scripts/build_war_story_page.py`; `scripts/tests/test_forecast_dashboard.py`; `scripts/tests/test_cmo_story_historical_cycles.py`; generated forecast, CMO, and methodology files under `artifacts/site/`, `artifacts/blue_oxblood_site/`, and `docs/`; `project_docs/coordination/WEB-FORECAST-EXPLORER-001.md`.
- Upstream inputs: Current public site at commit `2cc54a8`; `post2016_headline_v1` forecast release; current CMO candidate output.
- Expected outputs: A self-contained, public-facing forecast explorer with the five requested additions and refreshed generated pages.
- Warehouse access: read-only.
- Handoff recipient: `validation_release`.

## Handoff

- Added scenario-aware majority paths and race-watch lists for both chambers.
- Added complete district profiles with 2024 presidential context, canonical 2022 results, seat status, ACS/CVAP demographics, region shares, and existing candidate-finance cards.
- Added exact component waterfalls and side-by-side headline/Dem/Rep scenario comparisons.
- Added current-CMO timelines to returning 2026 candidates and graphical repeat-candidate timelines on the CMO page; ambiguous name/party identity groups are suppressed.
- Generated source-ledger downloads for every new profile/history source.
- Focused suite passed 37/37; independent task `VALIDATE-FORECAST-EXPLORER-001` returned PASS.
