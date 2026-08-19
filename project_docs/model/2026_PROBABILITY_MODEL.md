# 2026 district probability model

## Decision

The research candidate converts each forecast margin to a district win
probability with a zero-centered normal error curve:

```text
P(Democratic win) = Phi(expected Democratic margin / 6.0)
```

This replaces the idea that the district probability must be read directly
from the legacy all-era correlated simulation. Margin construction remains the
responsibility of Basic and Fundamentals+; the probability layer does not add
incumbency, finance, demographics, or candidate history a second time.

## Evidence

The calibration sample contains 1,188 contested Democratic-versus-Republican
state legislative races from Arkansas, Georgia, Tennessee, and Texas with
compatible district presidential baselines. Alabama is excluded from fitting.

Validation is performed two ways:

- expanding-window cycle tests: 2018 -> 2020, 2018-20 -> 2022, and
  2018-22 -> 2024;
- leave-one-state-out tests.

Normal, logistic, and Student-t error curves are tuned inside every training
fold. State-cycle-chamber cells receive equal total fitting weight. The three
families are effectively tied on Brier score. The normal family is retained
because its combined validation score is within 0.001 of the nominal winner
and its scale is readily interpretable.

| Validation | Races | Mean Brier | Mean log loss | Winner accuracy |
|---|---:|---:|---:|---:|
| Forward cycle | 905 | 0.0310 | 0.1031 | 96.1% |
| Leave state out | 1,188 | 0.0332 | 0.1287 | 95.8% |

## Current implications

At the current forecast margins:

- HD-21 Basic, R+10.9: 96.5% Republican;
- HD-21 Fundamentals+, R+12.6: 98.2% Republican.

These values are conditional on the displayed forecast margin and current
national environment. They do not include a second, hidden draw of national
polling error. Alternative national environments should be presented as
explicit scenarios or a shared chamber-level uncertainty layer.

## Staged sources and remaining work

The newly collected 2018/2020 MEDSL files and 2022 Georgia, Tennessee, Texas,
and Arkansas sources are preserved locally. Louisiana 2019/2023 and
Mississippi 2019/2023 are also staged. Odd-year elections are not silently
mixed into the even-year environment calibration: their statewide environment
must first be defined consistently, and Arkansas 2022 still lacks Phillips
County in the OpenElections precinct set.

Before public promotion:

1. independently reproduce the validation tables;
2. test probability coverage by chamber, state, margin band, and incumbency;
3. integrate odd-year statewide baselines as a prespecified sensitivity test;
4. decide whether national polling uncertainty is shown through scenarios or
   a separate shared simulation component;
5. update the dashboard and methodology only after that release review.

## Outputs

- `production_probability_2026.csv`
- `production_probability_curve.csv`
- `production_probability_validation_predictions.csv`
- `production_probability_validation_metrics.csv`
- `production_probability_family_comparison.csv`
- `production_probability_model_card.json`
