# Post-2016 Southern WAR v4 field contract

## Grain

`race_war.csv` is unique on `state_code`, `cycle`, `chamber`, and `district`
for strict D-versus-R final contests after 2016 and through 2022.

`candidate_cycle_war.csv` contains exactly two party-oriented rows per race.
It never estimates or pools a person-level effect.

## Required inputs

A row is `model_eligible` only when all of the following are observed on the
same race key and correct district-plan vintage:

- legislative Democratic two-party margin;
- older, recent, and current presidential margins required for its cycle;
- national environment swing;
- Democratic-minus-Republican incumbency balance;
- direct ACS SLD nonwhite and white-college shares.

Missing inputs remain null.  No missing value is converted to observed zero.

## Calculation

`environment_baseline_margin = current_pres_margin + national_environment_swing`

`lag_swing_from_older = environment_baseline_margin - older_pres_margin`

`lag_swing_from_recent = environment_baseline_margin - recent_pres_margin`

`raw_gap = legislative_dem_margin - environment_baseline_margin`

`war = raw_gap - fitted_structural_expected_gap`

The fitted structural gap uses recent presidential margin, both swing fields,
incumbency balance, nonwhite share, white-college share, and state/chamber
intercepts.  It excludes finance and candidate history.

Positive race WAR is Democratic overperformance.  Democratic candidate-cycle
WAR equals race WAR; Republican candidate-cycle WAR equals `-war`.

## Publication gate

No dependent map, historical backcast, ideology product, forecast, or public
site may consume V4 until presidential-context coverage is complete and the
declared forward validation is accepted.  An unscored row is not a zero-WAR
row.

