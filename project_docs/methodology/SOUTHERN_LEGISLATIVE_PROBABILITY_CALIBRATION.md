# Southern legislative probability calibration

## Purpose

This pipeline uses contested state House and state Senate elections in Arkansas,
Georgia, Louisiana, Mississippi, Tennessee, and Texas to estimate how often a
party wins at a given expected legislative margin. Alabama is excluded from
model fitting so the exercise tests geographic portability rather than merely
reproducing Alabama's historical outcomes.

## Sources and sample

- Klarner State Legislative Election Returns provide contest-level results
  through 2022.
- MEDSL precinct returns provide available 2024 legislative results.
- Daily Kos district results provide 2016 presidential baselines on the
  pre-2020 plans.
- National block-level 2020 presidential results are aggregated through the
  2022 and 2024 legislative block-assignment files.
- Census ACS five-year SLD tabulations provide nonwhite, overall-college, and
  white-college shares for each election vintage.

The primary calibration panel has 1,188 contested D-versus-R races with a
presidential baseline. It includes Georgia, Tennessee, and Texas in all four
even-year cycles; Arkansas enters in 2022 because a compatible 2016 district
baseline is not yet available. Louisiana's jungle-election structure and the
odd-year Mississippi elections are retained in source audits but excluded from
the primary even-year calibration.

## Validation design

The tournament uses genuine expanding-window tests:

- train 2018, test 2020;
- train 2018-2020, test 2022; and
- train 2018-2022, test 2024.

It also leaves each state out in turn. Models are compared using Brier score,
log loss, calibration error, winner accuracy, margin MAE, and RMSE.

The district baseline is conditioned on the realized national environment.
Midterms use the realized national U.S. House swing and presidential years use
the realized presidential swing. This deliberately estimates district-level
uncertainty separately from national polling uncertainty. A prospective
simulation must add polling/environment error as its own shared component.

## Initial findings

The direct environment-adjusted presidential baseline beats demographic
context and demographic-reactivity residual models in every aggregate metric:

| Model | Forward MAE | Winner accuracy | Brier | Log loss |
|---|---:|---:|---:|---:|
| Direct environment baseline | 4.74 | 96.1% | 0.0315 | 0.1093 |
| Demographic context | 5.22 | 95.5% | 0.0339 | 0.1187 |
| Demographic reactivity | 6.57 | 94.0% | 0.0457 | 0.1652 |

In the 2024 holdout, the direct baseline has a 3.62-point MAE and 97.9% winner
accuracy. The fitted probability scale in forward tests is approximately 6-8
margin points, far below the current Alabama simulator's all-era 27.6-point
total scale.

A flexible margin-and-incumbency probability calibrator has the best average
forward Brier score, but a simple normal-margin calibrator performs better in
the 2024 holdout and does not depend on 2024 incumbency fields that are missing
from MEDSL. This argues for either the simple calibrator or a conservative
ensemble, not immediate promotion of the flexible model.

For Alabama HD-21, the current Basic margin is R+10.9 and Fundamentals+ is
R+12.6. The flexible Southern calibration yields Republican probabilities of
approximately 88.6% and 91.5%, respectively. These are experimental until the
national and district uncertainty layers are recombined and coverage is tested.

## Reproduction

```powershell
python scripts/download_southern_sld_demographics.py
python scripts/build_southern_legislative_probability_panel.py
python scripts/run_southern_legislative_probability_tournament.py
python scripts/run_southern_demographic_forecast_tournament.py
```

No result in this research pipeline changes the public forecast automatically.

## Production probability candidate (2026-08-19)

The production candidate now treats the two jobs separately: Basic and
Fundamentals+ produce expected margins, while a recent-era Southern calibrator
converts either margin into a conditional win probability. Normal, logistic,
and Student-t error curves were tuned inside each forward-cycle and
leave-state-out training fold. Because their Brier scores were effectively
tied, the zero-centered normal curve was selected under a simplicity rule. Its
fitted scale is 6.0 margin points.

The curve is conditional on the forecast environment. National polling error
must remain an explicit shared scenario layer rather than being folded into a
large district-specific band. See `project_docs/model/2026_PROBABILITY_MODEL.md`
and reproduce with:

```powershell
python scripts/build_2026_probability_model.py
```
