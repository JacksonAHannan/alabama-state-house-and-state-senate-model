# Alabama WAR and generic-candidate forecast field contract

## Alabama WAR

`data/processed/war/alabama_war_v1/race_war.csv` contains one strict Alabama post-2016 D-versus-R final contest. `war` is the Democratic-oriented race residual:

`war = raw_gap - fitted_structural_expected_gap`

`candidate_cycle_war.csv` contains two views of that differential. Democratic candidate-cycle WAR equals race WAR and Republican candidate-cycle WAR is its negative. No pooled candidate coefficient may be called WAR.

## Forecast estimand

The 2026 forecast estimates the margin for a generic Democratic candidate against a generic Republican candidate, conditional on district and election environment. Generic means candidate identity and all historical candidate-performance measures are absent. Prior WAR, prior CMO, repeat-candidate strength, ideology, and fundraising are neither model features nor post-model adjustments.

The national environment is the quality-gated national generic-ballot Democratic two-party margin. Historical validation reconstructs 2018 and 2022 district baselines as prior presidential district margin plus the contemporaneous generic-ballot swing from the prior national presidential margin. The 2026 baseline uses the published uniform generic-ballot adjustment to each district's 2024 presidential margin.

The headline forecast applies the candidate-independent structural expected gap learned by the selected post-2016 Southern WAR `decaying_lag` ridge specification to that generic-ballot-adjusted baseline. Prospective Alabama rows enter the same design with the generic-ballot-adjusted district margin as `baseline_dem_margin`, the 2024 presidential district margin as `prior_pres_margin`, and the national generic-ballot swing as `lag_current_ticket_change`. Incumbency remains a symmetric race condition and contributes exactly through the fitted WAR structural model. Generic means that candidate-specific prior performance is excluded; it does not mean that incumbency is neutralized. Candidate-specific residual WAR is fixed to zero in every prospective row.

The 2018-to-2022 Alabama forward test is an advisory validation diagnostic, not a promotion gate. The selected structural specification must remain published with an explicit warning when it performs worse than the generic-ballot-only baseline; a validation result may not silently zero a model component that the forecast identity requires.

## Required fields and exclusions

Every scenario row must contain `generic_ballot_environment_margin`, `environment_baseline_margin`, `war_structural_expected_gap`, `generic_structural_adjustment`, `generic_downballot_lag`, `incumbency_adjustment`, `predicted_dem_margin`, `dem_win_probability`, `candidate_war_adjustment=0`, `candidate_history_used=false`, `finance_used=false`, and `generic_candidate_assumption=true`. `generic_downballot_lag + incumbency_adjustment` must equal `war_structural_expected_gap` within floating-point tolerance.

The prospective identity is:

`predicted_dem_margin = environment_baseline_margin + war_structural_expected_gap + candidate_war_adjustment`

No field matching candidate identity, prior candidate WAR/CMO, candidate history, ideology, fundraising, receipts, expenditures, or campaign finance may appear in the forecast design-feature list recorded by the manifest.

Same-cycle fitted Alabama WAR is retrospective. Cross-cycle forecast errors and probabilities are separate prospective diagnostics and must not be labeled WAR.
