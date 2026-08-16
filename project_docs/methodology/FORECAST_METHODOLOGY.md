# 2026 Alabama legislative forecast methodology

## Selected headline specification

The headline district margin is deliberately baseline-first:

`2026 forecast = allocated 2024 presidential margin + district demographic environment swing + promoted adjustments`

The environment swing uses the selected Catalist/YouGov demographic transfer,
poststratified with Alabama ACS district cells. It is anchored to the observed
2024 presidential result rather than the demographic model's fitted 2024 level.

No residual adjustment currently passes the promotion gate, so the headline is:

`2026 forecast = poll_adjusted_dem_margin`

The previous full-margin ridge forecast is preserved at
`data/processed/war/2026_prospective_features_and_forecast_legacy_core_20260815.csv`.
It must not be used for headline ratings.

## Why the model was changed

The legacy model predicted the complete legislative margin and used categorical
cycle effects. Because 2026 was unseen, one-hot encoding mapped it to the omitted
2010 reference environment. Demographic and historical missingness effects could
then overwhelm the district baseline. Senate District 2 moved from a sensible
poll-adjusted D+4.6 baseline to R+8.5 even though neither nominee was an incumbent.

The revised model never uses an election-year category for prospective scoring.
It models only the residual above a strong baseline and uses ridge models without
an intercept, so adjustments shrink toward zero.

## Backtest and promotion rule

Comparable forward tests begin in 2014 because 2010 lacks a district-level 2008
presidential baseline. For each later cycle, models train only on earlier cycles.
Every candidate layer predicts:

`legislative margin - prior presidential margin`

The historical archive does not contain consistent vintage, district-level
generic-ballot projections for 2014–2022. Consequently, the residual-layer gate
uses the transparent direct prior-presidential benchmark; it does not invent or
backfill a historical polling environment. Acquiring equivalent-date historical
poll snapshots remains a prerequisite for a fully matched environment backtest.

A layer is promoted only if it improves both:

1. mean expanding-window forward MAE; and
2. latest-cycle forward MAE.

Current results are in `2026_residual_layer_backtest_summary.csv`:

| Layer | Mean forward MAE | Latest MAE | Promoted |
|---|---:|---:|---|
| Direct baseline | 12.57 | 12.03 | Yes |
| Finance scenario | 13.28 | 10.28 | No |
| Incumbency | 14.01 | 10.65 | No |
| Incumbency + demographics | 15.79 | 11.44 | No |

Demographic main effects therefore do not re-enter the headline after already
being used in the polling transfer. Finance is shown as a scenario, not treated
as a causal or validated headline adjustment.

## Candidate CMO

Prior candidate CMO uses only historical out-of-fold scores. Exact normalized
name-and-party matches are averaged and shrunk by `n / (n + 2)`. This is retained
as a scenario because there are too few repeat candidates for a genuine forward
candidate-history validation. Candidates without history receive zero.

## Uncertainty and seat simulation

Fifty thousand deterministic-seed simulations add three error components:

- a common statewide error;
- a chamber-specific error; and
- a district-specific error.

Their scales are estimated from direct-baseline forward errors. District win
probabilities and 80%/95% intervals are empirical simulation quantities. The
seat distribution includes certified single-major-party districts as fixed seats
and simulates the 47 contested Democratic-versus-Republican races.

Only two comparable forward cycles exist, so this correlation structure and all
probabilities remain experimental.

## District-level audit outputs

`2026_forecast_decomposition.csv` reports, for every modeled race:

- allocated 2024 presidential margin;
- environment adjustment;
- poll-adjusted baseline;
- each promoted adjustment (currently zero);
- prior-CMO and finance scenario adjustments;
- headline margin and simulated win probability; and
- the selected specification and reason.

The dashboard renders this decomposition directly. It must not describe finance,
incumbency, demographics, or CMO as part of the headline unless the corresponding
promotion flag is true.
