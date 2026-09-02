# Task contract: CMO-ALABAMA-WAR-FORECAST-043 — Alabama WAR and generic-candidate forecast

- Accountable role: `cmo_model`
- Owner: `/root`
- Status: `complete`
- Objective: Publish corrected post-2016 Alabama race-residual WAR ratings, rename the public navigation tab to Alabama WAR, and rebuild the 2026 forecast around a generic-ballot national environment and generic-candidate structural expectation.
- Non-goals: Do not overwrite Southern WAR v1-v3; do not use candidate identity, prior WAR/CMO, ideology, fundraising, or repeat-candidate strength in the forecast; do not silently score uncontested or non-strict races; do not modify warehouse facts.
- Upstream snapshot: Southern residual WAR run `WAR-POST2016-V3-D9C7EE17BD14B8C7D23A`; warehouse run `RUN-4ED478C647B34A7B9A402970625DB334`; current generic-ballot and 2026 roster snapshots.
- Read scope: Southern WAR v3 race and candidate-cycle outputs; historical and current generic-ballot files; 2026 district baseline, roster, and incumbency evidence; existing forecast calibration/error components; current site builders and tests.
- Write scope: `scripts/build_alabama_war_v1.py`; `scripts/build_alabama_historical_war_v1.py`; `scripts/build_democratic_transition_page_v2.py`; `scripts/run_alabama_war_generic_forecast.py`; related WAR, forecast, candidate-name, ideology-page, dashboard, and publication tests; `data/processed/war/alabama_war_v1/`; `data/processed/war/alabama_historical_war_v1/`; `data/processed/forecast_calibration/alabama_war_forecast_v1_*`; the Alabama WAR and forecast methodology/field-contract/audit documents; `scripts/build_war_story_page.py`; `scripts/build_2026_forecast_dashboard.py`; generated `docs/`, `artifacts/site/`, and `artifacts/blue_oxblood_site/`; `project_docs/coordination/CMO-ALABAMA-WAR-FORECAST-043.md`.
- Warehouse mode: `read-only`
- Inputs: Strict Alabama D-versus-R final contests after 2016; 2018 and 2022 historical generic-ballot snapshots; the current quality-gated generic ballot; 2024 presidential district margins; reviewed 2026 incumbency and roster evidence.
- Outputs: Alabama-only race and party-oriented WAR tables; generic-candidate forward validation; 2026 district scenarios, probabilities, uncertainty, chamber distributions, manifests, public pages, and copied public data.
- Acceptance checks: Alabama WAR exactly equals raw gap minus fitted structural expectation; candidate orientations are exact opposites; every 2026 modeled row uses the generic-ballot environment; no candidate-history or finance field enters any forecast design matrix; prior strength is fixed at zero/absent; forecast and site row counts reconcile; navigation reads `Alabama WAR`; manifests hash inputs/code/outputs; targeted and full tests run.
- Handoff recipient: `validation_release`
- Known risks: Only 2018 can train the direct Alabama forward test into 2022; national generic-ballot polling is an imperfect stand-in for Alabama legislative environment; same-cycle WAR is descriptive; current 2026 polling and roster evidence may change.

## Completion

- Alabama WAR run: `AL-WAR-V1-E1F8E11BF2853322239F`.
- Historical WAR run: `AL-HIST-WAR-V1-1FBFE5489CAEFA2E77AB`.
- Forecast build: `00509565ea4fb62b4e10`.
- Public headline applies the selected post-2016 Southern `decaying_lag` WAR structural expectation, including its fitted symmetric incumbency effect, to the generic-ballot-adjusted district baseline. Candidate-specific prior WAR remains zero/absent. The sole Alabama forward holdout warning is published: structural MAE was 9.559 versus 7.073 for the generic-ballot-only benchmark.
- Identifier-shaped historical source labels are resolved through evidence-backed verified adjudications; James C. Fields Jr., Herb Neu, and Christian Coleman are explicitly regression-tested.
- Focused release validation: 52 tests passed across historical WAR, forecast, dashboard, candidate-name provenance, ideology, and publication consistency.
- Full repository validation: 647 passed; one unrelated historical-finance fixture expected 352 complete races while current canonical data contains 353.
