# Alabama historical WAR v1 field contract

## Grain and coverage

`race_war.csv` contains one contested Democratic-versus-Republican Alabama general-election race for each eligible cycle from 1994 through 2022, uniquely keyed by `cycle`, `chamber`, and `district`.

`candidate_cycle_war.csv` contains exactly two party-oriented rows per race, uniquely keyed by `cycle`, `chamber`, `district`, and `canonical_party`.

Uncontested, non-D–R, and missing-vote races remain outside this product. Their absence does not imply a zero WAR.

## Estimand

All race quantities use Democratic two-party margin points:

`raw_gap = legislative_dem_margin - baseline_dem_margin`

`race_war = raw_gap - fitted_structural_expected_gap`

The Democratic candidate receives `candidate_cycle_war = race_war`; the Republican receives its exact negative. Candidate identity does not pool or alter the score.

## Scoring scopes

- For 1994–2014, `scoring_scope = post2016_southern_model_backcast`. The selected Southern `decaying_lag` ridge specification with alpha 100 is fit once on strict Southern races with `cycle > 2016` and applied backward to historical Alabama race context.
- For 2018 and 2022, `scoring_scope = published_same_cycle_residual`. Values must exactly equal Alabama WAR v1 and retain its same-cycle descriptive fitted expectation.

The backcast prediction is retained for 2018/2022 as a diagnostic but does not replace the published rating.

## Identity authority

Candidate display names come from the canonical Alabama election candidate record. Archived election-page names may supply a secondary spelling cross-check in the page builder. Finance `provider_candidate_name`, committee names, committee IDs, and finance aliases are prohibited from display-name selection.

## Missingness and extrapolation

Missing prior-presidential context remains explicitly labeled. For exact compatibility with the selected modern design matrix, unavailable numeric lag inputs are encoded as zero for prediction; this is not an observed zero and is identified by `lag_context_available = false`.

No fundraising, ideology, candidate history, career average, or pooled candidate coefficient enters WAR.
