# Southern historical WAR map field contract

## Scope and grain

The product covers the 90 prespecified state/cycle/chamber regular-election
slices from 2016 through 2022 in the 14-state Southern model scope. `race_war.csv`
contains one strict model-valid D-versus-R contest per exact
`state_code/cycle/chamber/district` key. `candidate_cycle_war.csv` contains two
party-oriented rows per scored race. Public geometry contains every Census
district feature in each exact election-year state/chamber boundary file.

## Score

All values use Democratic two-party margin points:

`raw_gap = legislative_dem_margin - baseline_dem_margin`

`war = raw_gap - fitted_structural_expected_gap`

Post-2016 scores are copied exactly from Southern WAR v3. The 2016 score is a
descriptive backcast from the selected post-2016 `decaying_lag` ridge model
(alpha 100), fit without 2016 outcomes. The Democratic candidate receives the
race WAR and the Republican candidate its exact negative.

## Geometry join

The scored-race to geometry join is `1:1` within a scored slice. Geometry may
also contain unscored districts, producing a `1:0` score relationship from the
district feature. An unmatched scored race, duplicate normalized district ID,
or geometry feature outside the scheduled state/cycle/chamber slice fails the
release. Election-year Census geometry is presentation evidence and does not
silently replace a provider-reported unknown plan vintage in the warehouse.

## Finance overlay

Finance joins `1:0..1` on the exact race key. Amounts and the D-to-R log ratio
are non-null only when `finance_complete=1`. Otherwise the public status is
`unknown`; it is never zero-filled. Finance is descriptive and excluded from
headline WAR because it failed the prespecified nested forward promotion gate.
