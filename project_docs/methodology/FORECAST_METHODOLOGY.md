# 2026 Alabama legislative forecast methodology

## Headline model

The headline is the poll-adjusted 2024 presidential margin allocated into the
Alabama House and Senate districts used in 2026.

`2026 headline margin = poll-adjusted 2024 presidential margin`

A modern Southern tournament evaluated demographics, inferred incumbency/open
seat status, and strictly prior-cycle candidate quality as additions to that
baseline. None passed the prespecified average, latest-cycle, worst-cycle, and
number-of-cycles-improved gates. Those features therefore do not alter the
headline margin.

## National environment

The 2024-to-2026 adjustment uses current generic-ballot polling and historical
national vote data. The polling feed is quality gated using the supplied Nate
Silver pollster ratings, deduplicates pollsters, and applies recency and
population weights. Reviewed race and education crosstabs, ACS district
composition, and historical national voting patterns transfer the national
change into Alabama without replacing the observed 2024 district result.

## Modern Southern validation

The calibration panel contains 1,188 contested state-legislative races from
Arkansas, Georgia, Tennessee, and Texas in 2018–2024. Expanding-window folds
predict 2020, 2022, and 2024 using only earlier cycles. All four margin models
are compared on the same 893 model-ready out-of-sample contests.

| Model | Mean forward MAE | 2024 MAE change | Promoted |
|---|---:|---:|---|
| Baseline | 4.751 | 0.000 | Yes |
| Demographics + incumbency | 5.591 | +0.349 | No |
| Plus prior candidate quality | 5.630 | +0.260 | No |
| Demographics | 6.031 | +0.483 | No |

The much larger pre-2016 Southern panel is useful for historical CMO
decomposition, but its structural expectation performs substantially worse in
Alabama in 2018–2022. It is not carried into the 2026 headline or displayed as
a current forecast scenario.

## Probability calibration

Probability families are fitted to the selected baseline's 893 out-of-sample
margins. A Student-t curve with five degrees of freedom and a 5.75-point scale
minimizes Brier score, then log loss, over the prespecified grid.

District probabilities are conditional on the headline margin. A separate
50,000-draw simulation adds shared national, Alabama, and chamber error plus
district-specific error. This correlation prevents the chamber distribution
from treating every district as independent.

## Public views

- **Headline:** the selected poll-adjusted presidential baseline.
- **Democratic environment:** headline plus one historical national polling
  error standard deviation.
- **Republican environment:** headline minus one historical national polling
  error standard deviation.

The two environment views are sensitivity scenarios. They do not alter model
selection. The retired historical-CMO view used a superseded expectation and
is no longer presented as a forecast.

## Finance and candidate quality

Finance is excluded because the multi-state calibration panel lacks comparable,
cutoff-consistent candidate-finance coverage. Missing finance is never treated
as zero. Prior candidate quality is linked to normalized candidates rather than
seats, shrunk toward zero, and calculated only from earlier cycles; it did not
pass the promotion gate.

## Limitations

- Only three forward validation cycles support the modern tournament.
- The calibration panel currently covers four Southern states.
- Alabama polling is sparse, requiring a national-to-state transfer.
- Candidate quality is difficult to separate from incumbency, fundraising,
  opponent weakness, and electoral selection.
- Polling, geographic, and model-selection uncertainty are not fully separable
  with the available history.

## Reproducibility

`scripts/run_robust_forecast_pipeline.py` hashes every controlling data and code
input, records the tournament, probability grid, error decomposition,
simulation seed, and scenario definitions, and publishes a versioned manifest.
The website consumes those versioned outputs and never reads back from `docs/`.
