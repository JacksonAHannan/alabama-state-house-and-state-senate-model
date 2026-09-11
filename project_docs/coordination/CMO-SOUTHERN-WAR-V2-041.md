# Task contract: CMO-SOUTHERN-WAR-V2-041 — respecify lag and test viability-gated fundraising

- Accountable role: `cmo_model`
- Owner: `/root`
- Status: `review`
- Objective: Build a new post-2016 Southern WAR research candidate with a leakage-resistant, cycle-varying lag component and a separately gated fundraising sensitivity modeled after Split Ticket's campaign-viability rule.
- Non-goals: Do not overwrite v1, promote fundraising without forward evidence, equate state fundraising with federal total spending, modify warehouse facts, or publish to `docs/`.
- Upstream snapshot: Validated Southern WAR/finance preparation run `RUN-7EACF4A3805E4328A3DE0A361051AF35`; v1 model run `WAR-POST2016-3E87657081BBBCB16754`; validated presidential-context compatibility exports.
- Read scope: `mart_southern_war_training_with_finance`; `data/processed/forecast_calibration/southern_legislative_probability_panel.csv`; `data/processed/elections/canonical_cmo_features.csv`; v1 model artifacts; Split Ticket's published WAR methodology.
- Write scope: `scripts/retrain_post2016_southern_war_v2.py`; `scripts/tests/test_post2016_southern_war_v2.py`; `data/processed/war/post2016_southern_war_v2/`; `project_docs/model/POST2016_SOUTHERN_WAR_V2.md`; `project_docs/audits/POST2016_SOUTHERN_WAR_V2_VALIDATION.md`; `project_docs/coordination/CMO-SOUTHERN-WAR-V2-041.md`.
- Warehouse mode: `read-only`
- Inputs: Strict finance-free WAR outcomes with `cycle > 2016`; exact-key prior-presidential context where validated; complete D/R fundraising observations only for finance evaluation.
- Outputs: Structural lag tournament, cross-fitted structural predictions, lag diagnostics by cycle, viability-threshold fundraising tournament, finance sensitivity, revised race/candidate WAR scores, v1 comparison, coverage, and content-addressed manifest.
- Acceptance checks: No pre-2017 or research-only row enters; prior-presidential joins are exact and duplicate-free; missing lag and finance remain explicit; structural OOF predictions never train on their own race; forward folds use earlier cycles only; finance comparisons use identical complete-row samples; D/R orientation and candidate-effect equations reconcile; output/report hashes reproduce; focused and full tests run.
- Handoff recipient: `validation_release`
- Known risks: Comparable prior-presidential context currently covers only a subset of states/races; fundraising is not total spending and may be endogenous to candidate strength; nominal state-legislative viability thresholds are not portable equivalents of Split Ticket's federal $1.5 million threshold.

## Handoff

- Research-candidate run: `WAR-POST2016-V2-40C209C46EC572EF8278`.
- Lag result: `decaying_lag` with ridge alpha 100 passed the forward added-value gate; validated lag context covers 1,284 of 3,658 races.
- Finance grid: every $10,000 from $10,000 through $100,000, plus $250,000. The $10,000 lower bound is diagnostic only. Nested forward selection chose the $250,000 gate for the latest cycle, but it failed the forward no-finance comparison, so finance is excluded from headline WAR.
- Validation: focused v2 tests passed (5); combined WAR/warehouse regression tests passed (31). The full suite produced 631 passes and two independently reproducible failures outside this task's write scope: the historical-finance complete-row fixture expects 352 but observes 353, and the Georgia finance fixture is missing an expected recovered candidate name.
- Review request: independently check presidential-context coverage, the decay interaction, nested finance-threshold selection, candidate identity pooling, calibration, and uncertainty before any release.
