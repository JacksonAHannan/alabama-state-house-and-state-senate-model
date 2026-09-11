# Task contract: FORECAST-IDEOLOGY-FEATURES-008 prospective ideology features

- Accountable role: `forecast_model`
- Owner: `/root`
- Status: `complete`
- Objective: Build a leakage-safe, explicit-missingness 2026 candidate and race ideology feature export from repaired identities, carry those fields into the current prospective forecast payload, and reassess forecast eligibility without changing headline coefficients merely because coverage increased.
- Non-goals: Do not impute missing challenger ideology as zero; do not train on post-election evidence; do not alter historical CMO or public `docs/`; do not include ideology in the headline forecast without comparable forward-validation support.
- Upstream snapshot: Completed `IDEOLOGY-POSTREPAIR-COVERAGE-005`, current reviewed 2026 roster/incumbency, and completed `FORECAST-2026-INPUT-REPAIR-001` headline forecast.
- Read scope: `data/processed/ideology/candidate_career_ideology_through_2026.csv`; `data/processed/ideology/candidate_ideology_v3_model_features.csv`; `data/processed/ideology/candidate_legislator_identity_crosswalk.csv`; `data/processed/war/2026_final_candidate_roster.csv`; `data/processed/war/2026_candidate_incumbency.csv`; `data/processed/elections/canonical_cmo_candidates.csv`; current polling, finance, and baseline forecast inputs.
- Write scope: `scripts/build_2026_forecast_ideology_features.py`; `scripts/run_post2016_polling_cmo_forecast.py`; `data/processed/forecast_calibration/2026_candidate_ideology_features.csv`; `data/processed/forecast_calibration/2026_race_ideology_features.csv`; `data/processed/forecast_calibration/2026_ideology_feature_coverage.csv`; `data/processed/forecast_calibration/post2016_polling_cmo_`; `data/processed/forecast_calibration/post2016_headline_v1_`; `project_docs/model/POST2016_POLLING_CMO_EXPERIMENT.md`; `project_docs/model/POST2016_HEADLINE_FORECAST_V1.md`; `project_docs/coordination/FORECAST-IDEOLOGY-FEATURES-008.md`; `project_docs/coordination/active_tasks.csv`
- Warehouse mode: `read-only`
- Inputs: Reviewed roster and incumbency, exact prior-winner candidate IDs, repaired candidate-to-legislator identities, cycle-valid candidate ideology features, and career roll-call evidence available by the 2026 general election.
- Outputs: Candidate-level ideology features, race-level Democratic-minus-Republican differences with coverage flags, refreshed forecast feature/forecast files, and explicit eligibility decision.
- Acceptance checks: Builder succeeds; roster key is unique and complete; no missing ideology value is replaced by zero; race features are unique by chamber/district; current forecast tests pass; predictions are unchanged when ideology remains descriptive-only.
- Handoff recipient: `web_product` for local page rebuilding and `validation_release` before publication.
- Known risks: Ideology coverage is concentrated among incumbents and past officeholders, creating severe candidate-selection bias; current-cycle roll calls are valid pre-election signals but not comparable for challengers.

## Handoff

- Candidate coverage is 116 of 189 (61.4%), but it is sharply selected: 90 of 121 incumbents have evidence versus 2 of 67 major-party non-incumbents.
- Among the 48 modeled Democratic-versus-Republican races, at least one candidate has evidence in 38; both candidates have evidence in only one.
- Consequently, the ideology fields are attached to all 48 prospective feature rows as descriptive data, with `ideology_forecast_applied = False` and an explicit exclusion reason.
- The headline margin and win-probability outputs changed by exactly 0.0 after the attachment.
- Six forecast tests passed. Candidate and race keys are complete and unique; missing ideology stays null rather than becoming zero.
