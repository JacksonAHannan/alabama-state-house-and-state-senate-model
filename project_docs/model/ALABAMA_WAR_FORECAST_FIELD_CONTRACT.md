# Alabama WAR and generic-candidate forecast field contract

## Alabama WAR

`data/processed/war/alabama_war_v1/race_war.csv` contains one strict Alabama post-2016 D-versus-R final contest. `war` is the Democratic-oriented race residual:

`war = raw_gap - fitted_structural_expected_gap`

`candidate_cycle_war.csv` contains two views of that differential. Democratic candidate-cycle WAR equals race WAR and Republican candidate-cycle WAR is its negative. No pooled candidate coefficient may be called WAR.

## Forecast estimand

The 2026 forecast estimates the district margin conditional on district, election environment, and each nominee's own demonstrated WAR where a prior Alabama race is matched. Nominees without a matched prior race are evaluated generically: no imputed candidate strength is assigned to them. Prior CMO, ideology, and fundraising remain neither model features nor post-model adjustments.

The national environment is the quality-gated national generic-ballot Democratic two-party margin. Historical validation reconstructs 2018 and 2022 district baselines as prior presidential district margin plus the contemporaneous generic-ballot swing from the prior national presidential margin. The 2026 baseline uses the published uniform generic-ballot adjustment to each district's 2024 presidential margin. That uniform national-to-Alabama generic-ballot transfer is an owner-selected model assumption; its Alabama-specific validity is not established beyond the single 2022 forward holdout.

The headline forecast applies the candidate-independent structural expected gap learned by the selected post-2016 Southern WAR `decaying_lag` ridge specification to that generic-ballot-adjusted baseline. Prospective Alabama rows enter the same design with the generic-ballot-adjusted district margin as `baseline_dem_margin`, the 2024 presidential district margin as `prior_pres_margin`, and the national generic-ballot swing as `lag_current_ticket_change`. Incumbency remains a symmetric race condition and contributes exactly through the fitted WAR structural model.

Candidate history enters only as a post-model adjustment, never as a design column. `candidate_war_adjustment` is the Democratic-oriented sum of both nominees' carried-forward WAR: the persistence coefficient estimated on repeat candidates in the Southern v3 panel, multiplied by each nominee's most recent Alabama candidate-cycle WAR. Its estimation, matching and limits are fixed by `alabama_forecast_candidate_history_manifest.json`:

- Persistence is estimated by OLS with candidate-clustered standard errors over consecutive appearances of one candidate identity. The years-elapsed interaction is applied only when it is statistically supported; it currently is not, so no decay is applied.
- Identity matching is the verified prior-winner crosswalk first, then an exact unique normalized name. Ambiguous names are left unmatched; a match is never forced.
- A result older than the carry limit (the largest observed training gap plus one cycle) is recorded but enters as zero.
- A rematch contributes one race residual, not two, because the two nominees' prior WAR values are exact negatives of each other.

The 2018-to-2022 Alabama forward test is an advisory validation diagnostic, not a promotion gate. All three specifications - generic-ballot baseline, WAR structure, and WAR structure plus candidate history - must be published together with their MAE, RMSE, winner accuracy and Brier score. The selected specification must remain published with an explicit warning when it performs worse than the generic-ballot-only baseline; a validation result may not silently zero a model component that the forecast identity requires.

## Required fields and exclusions

Every scenario row must contain `generic_ballot_environment_margin`, `environment_baseline_margin`, `war_structural_expected_gap`, `generic_structural_adjustment`, `generic_downballot_lag`, `incumbency_adjustment`, `predicted_dem_margin`, `dem_win_probability`, `candidate_war_adjustment`, `candidate_history_used`, `finance_used=false`, and `generic_candidate_assumption`. `candidate_history_used` must equal `candidate_war_adjustment != 0`, and `generic_candidate_assumption` must be its negation. `generic_downballot_lag + incumbency_adjustment` must equal `war_structural_expected_gap` within floating-point tolerance. The `fundamentals_only_no_candidate_history` scenario is the same forecast with the carry switched off and must carry `candidate_war_adjustment=0` on every row.

`alabama_war_forecast_v1_2026_scenarios.csv` carries `status=uniform_generic_ballot_environment_selected` on every row, recording the uniform generic-ballot environment that the forecast uses. The legacy Catalist/YouGov demographic-transfer status value and the legacy `geographic_elasticity`, `demographic_swing_2024_2026`, `demographic_poll_adjusted_margin`, `low_elasticity_075_margin`, `high_elasticity_125_margin`, `votehub_2026_dem_margin`, and `fundraising_adjustment` columns are not part of the active contract and must not appear in the export.

The prospective identity is:

`predicted_dem_margin = environment_baseline_margin + war_structural_expected_gap + candidate_war_adjustment`

No field matching candidate identity, prior candidate WAR/CMO, candidate history, ideology, fundraising, receipts, expenditures, or campaign finance may appear in the forecast design-feature list recorded by the manifest. Candidate history is added after the structural prediction and must remain separable from it.

Same-cycle fitted Alabama WAR is retrospective. Cross-cycle forecast errors and probabilities are separate prospective diagnostics and must not be labeled WAR.

District win probabilities use a Student-t distribution with five degrees of freedom. The scale is the maximum-likelihood scale of the forward-holdout margin residuals (`probability.selection_rule = maximum_likelihood_on_holdout_margin_residuals`); the manifest records the scale, the holdout Brier score and the empirical coverage of the nominal 80% interval (`probability.holdout_coverage_80`). Selecting the scale by binary-outcome Brier is not permitted: on a holdout whose winners are all correctly ordered it is monotone in sharpness and returns the search-grid bound. The scale is tuned and evaluated on the same holdout; no independent probability evaluation exists until a second Alabama forward cycle is available.

## Seat treatment and chamber summaries

Every seat in both chambers (105 House, 35 Senate) is classified from the dated
roster into exactly one class: `modeled` (one Democratic and one Republican
nominee; the generic race is forecast), `single_major_party` (exactly one major
party nominated; the seat is fixed for that party in chamber summaries whether
or not an independent or minor-party candidate also filed; no probability is
forecast), `independent_only` (no major-party nominee; unmodeled, shown with
null margin and probability, never assigned), and `unresolved` (roster
disagreement not yet adjudicated; unmodeled and visible). Independents in a
`modeled` race are not forecast; probabilities refer to the two-party margin.
Chamber seat distributions add the fixed single-major-party seats to the
simulated modeled seats. The published page states the class of every seat, and
`project_docs/audits/FORECAST_ROSTER_UNIVERSE_*` records the partition and its
roster provenance for each release.

