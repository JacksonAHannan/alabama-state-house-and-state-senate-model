# Prospective model comparison

> **Implemented selection:** The direct poll-adjusted presidential baseline is
> now the headline 2026 forecast. Incumbency, demographic-residual, finance, and
> prior-CMO adjustments are retained only as scenarios unless they pass the
> forward promotion gate documented in `project_docs/methodology/FORECAST_METHODOLOGY.md`.

## Evaluation rule

Models are compared using expanding-cycle forward tests, never random-fold fit. The common comparison window is 2018 and 2022 because the direct prior-presidential benchmark is not complete for the structurally incomplete 2014 feature set. Results are also stratified by training-era start and chamber.

## Initial result

The direct prior-presidential margin is the leading prospective benchmark:

| Test cycle | Direct prior presidential MAE |
|---|---:|
| 2018 | 13.11 |
| 2022 | 12.03 |

For the 2022 holdout, its MAE is 12.20 points in House races and 11.51 in Senate races. It outperforms the fitted presidential-only, presidential-plus-incumbency, core non-finance, FTM fundraising, transaction-expenditure, and chamber-offset models when trained from 2010.

Training-era sensitivity matters. When trained only on 2018 and tested on 2022, the FTM-adjusted model reaches 11.26 MAE, slightly better than the direct presidential benchmark's 12.03. That result comes from only one training cycle and is insufficient by itself to select the more complex model.

## Provisional selection

Use 2024 presidential district margin as the provisional 2026 forecast baseline. Do not promote a fitted or finance-adjusted model unless it demonstrates consistent improvement across more than one forward cycle. Finance remains useful for CMO sensitivity and race context rather than as a required headline forecast feature.

Detailed outputs are `2026_model_era_sensitivity.csv`, `2026_model_era_predictions.csv`, and `2026_model_benchmark_summary.csv`.
