# Southern WAR v3 missing-context sensitivity and uncertainty audit

Read-only audit of the exact run below. It refits the published structural specification within each cycle, checks parity with the published values, and then measures how much headline WAR depends on the zero-filled lag compatibility encoding and on within-cycle sampling. Nothing here changes model values or approves release.

- Model run: `WAR-POST2016-V3-4AF79A70EAA8F39EBD49`
- Warehouse build run: `RUN-92AB8DE353AC47D6AECE3D7767C29FCD`
- Manifest SHA256: `c6c09e19335965380e068c40484437bf460db81add232dc8d7cf78d135a905a6`
- race_war.csv SHA256: `afe25d61789bc41c9d989615547291a706eae121540cd2569de1493a2190ccec`
- Audit script SHA256: `b9729974c96519abd6bbfa08d678b9444204eb269ddb5cea59ef1247f941c12b`
- Generated (UTC): 2026-09-08T13:20:14.003192+00:00; runtime 5.68 s
- Selected specification: `decaying_lag` with alpha 100; lag columns ['prior_pres_margin', 'lag_current_ticket_change', 'lag_change_x_years']
- Machine-readable outputs: `data/processed/war/post2016_southern_war_v3_sensitivity`

## Parity gate

Status: **passed** (tolerance 1e-08). Maximum absolute difference between the within-cycle refit and the published values:

- `fitted_structural_expected_gap`: 6.484e-14
- `fitted_structural_nonlag_expected_gap`: 6.484e-14
- `war`: 6.484e-14

## Missing-context coverage by cycle

Rows without validated prior-presidential context enter the selected design with `prior_pres_margin`, `lag_current_ticket_change` and `lag_change_x_years` set to 0.0. Their published `fitted_lag_component` is therefore exactly zero by construction; the encoding still influences the fitted coefficients.

| Cycle | Races | Lag context | Missing context | Missing share |
| --- | --- | --- | --- | --- |
| 2018 | 1,025 | 347 | 678 | 0.661 |
| 2019 | 144 | 0 | 144 | 1.000 |
| 2020 | 870 | 268 | 602 | 0.692 |
| 2022 | 761 | 335 | 426 | 0.560 |
| 2023 | 90 | 0 | 90 | 1.000 |
| 2024 | 770 | 334 | 436 | 0.566 |

## Context sensitivity

Each alternative is a descriptive same-cycle refit compared with headline WAR (`alternative - headline`). Sign change share uses the published D/R/EVEN rule. Cycles with no lag-available races cannot support the lag-available fits and show `n/a` for those alternatives. States absent from the lag-available fit carry zero state coefficients in `war_missing_excluded_fit`, so that alternative isolates the fitting influence of missing rows rather than offering a like-for-like score.

### `war_no_lag_spec`: `fundamentals_no_lag` design fitted within each cycle on the full sample

| Cycle | Lag context | Races | Scored | Mean diff | MAE | Max abs diff | Sign change share | Spearman |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all | all | 3,660 | 3,660 | 0.000 | 0.682 | 13.213 | 0.052 | 0.977 |
| all | available | 1,284 | 1,284 | -0.034 | 1.329 | 13.213 | 0.115 | 0.922 |
| all | missing | 2,376 | 2,376 | 0.018 | 0.332 | 3.914 | 0.018 | 0.996 |
| 2018 | all | 1,025 | 1,025 | 0.000 | 1.267 | 9.672 | 0.060 | 0.970 |
| 2018 | available | 347 | 347 | -0.124 | 2.040 | 9.672 | 0.104 | 0.926 |
| 2018 | missing | 678 | 678 | 0.063 | 0.870 | 3.914 | 0.038 | 0.990 |
| 2019 | all | 144 | 144 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 |
| 2019 | available | 0 | 0 | n/a | n/a | n/a | n/a | n/a |
| 2019 | missing | 144 | 144 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 |
| 2020 | all | 870 | 870 | 0.000 | 0.561 | 6.103 | 0.051 | 0.979 |
| 2020 | available | 268 | 268 | -0.116 | 1.401 | 6.103 | 0.142 | 0.909 |
| 2020 | missing | 602 | 602 | 0.051 | 0.187 | 1.069 | 0.010 | 0.999 |
| 2022 | all | 761 | 761 | 0.000 | 0.546 | 13.213 | 0.066 | 0.964 |
| 2022 | available | 335 | 335 | 0.045 | 1.127 | 13.213 | 0.128 | 0.905 |
| 2022 | missing | 426 | 426 | -0.036 | 0.090 | 0.470 | 0.016 | 0.999 |
| 2023 | all | 90 | 90 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 |
| 2023 | available | 0 | 0 | n/a | n/a | n/a | n/a | n/a |
| 2023 | missing | 90 | 90 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 |
| 2024 | all | 770 | 770 | 0.000 | 0.382 | 5.190 | 0.045 | 0.984 |
| 2024 | available | 334 | 334 | 0.046 | 0.737 | 5.190 | 0.093 | 0.955 |
| 2024 | missing | 436 | 436 | -0.035 | 0.110 | 1.559 | 0.009 | 0.999 |

### `war_lag_available_fit`: selected design fitted and scored only on lag-available races

| Cycle | Lag context | Races | Scored | Mean diff | MAE | Max abs diff | Sign change share | Spearman |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all | all | 3,660 | 1,284 | 0.057 | 1.382 | 13.241 | 0.121 | 0.880 |
| all | available | 1,284 | 1,284 | 0.057 | 1.382 | 13.241 | 0.121 | 0.880 |
| all | missing | 2,376 | 0 | n/a | n/a | n/a | n/a | n/a |
| 2018 | all | 1,025 | 347 | -0.010 | 2.814 | 13.241 | 0.187 | 0.808 |
| 2018 | available | 347 | 347 | -0.010 | 2.814 | 13.241 | 0.187 | 0.808 |
| 2018 | missing | 678 | 0 | n/a | n/a | n/a | n/a | n/a |
| 2019 | all | 144 | 0 | n/a | n/a | n/a | n/a | n/a |
| 2019 | available | 0 | 0 | n/a | n/a | n/a | n/a | n/a |
| 2019 | missing | 144 | 0 | n/a | n/a | n/a | n/a | n/a |
| 2020 | all | 870 | 268 | 0.083 | 1.849 | 5.464 | 0.216 | 0.813 |
| 2020 | available | 268 | 268 | 0.083 | 1.849 | 5.464 | 0.216 | 0.813 |
| 2020 | missing | 602 | 0 | n/a | n/a | n/a | n/a | n/a |
| 2022 | all | 761 | 335 | 0.112 | 0.344 | 1.259 | 0.048 | 0.988 |
| 2022 | available | 335 | 335 | 0.112 | 0.344 | 1.259 | 0.048 | 0.988 |
| 2022 | missing | 426 | 0 | n/a | n/a | n/a | n/a | n/a |
| 2023 | all | 90 | 0 | n/a | n/a | n/a | n/a | n/a |
| 2023 | available | 0 | 0 | n/a | n/a | n/a | n/a | n/a |
| 2023 | missing | 90 | 0 | n/a | n/a | n/a | n/a | n/a |
| 2024 | all | 770 | 334 | 0.051 | 0.560 | 2.331 | 0.048 | 0.976 |
| 2024 | available | 334 | 334 | 0.051 | 0.560 | 2.331 | 0.048 | 0.976 |
| 2024 | missing | 436 | 0 | n/a | n/a | n/a | n/a | n/a |

### `war_missing_excluded_fit`: lag-available fit scoring every race with the zero-fill encoding

| Cycle | Lag context | Races | Scored | Mean diff | MAE | Max abs diff | Sign change share | Spearman |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all | all | 3,660 | 3,426 | 0.962 | 3.423 | 40.786 | 0.213 | 0.712 |
| all | available | 1,284 | 1,284 | 0.057 | 1.382 | 13.241 | 0.121 | 0.880 |
| all | missing | 2,376 | 2,142 | 1.504 | 4.647 | 40.786 | 0.269 | 0.673 |
| 2018 | all | 1,025 | 1,025 | 1.841 | 5.411 | 40.786 | 0.279 | 0.616 |
| 2018 | available | 347 | 347 | -0.010 | 2.814 | 13.241 | 0.187 | 0.808 |
| 2018 | missing | 678 | 678 | 2.789 | 6.741 | 40.786 | 0.326 | 0.583 |
| 2019 | all | 144 | 0 | n/a | n/a | n/a | n/a | n/a |
| 2019 | available | 0 | 0 | n/a | n/a | n/a | n/a | n/a |
| 2019 | missing | 144 | 0 | n/a | n/a | n/a | n/a | n/a |
| 2020 | all | 870 | 870 | 0.955 | 2.531 | 15.182 | 0.200 | 0.844 |
| 2020 | available | 268 | 268 | 0.083 | 1.849 | 5.464 | 0.216 | 0.813 |
| 2020 | missing | 602 | 602 | 1.343 | 2.834 | 15.182 | 0.193 | 0.858 |
| 2022 | all | 761 | 761 | 1.316 | 1.856 | 7.915 | 0.162 | 0.806 |
| 2022 | available | 335 | 335 | 0.112 | 0.344 | 1.259 | 0.048 | 0.988 |
| 2022 | missing | 426 | 426 | 2.263 | 3.046 | 7.915 | 0.251 | 0.768 |
| 2023 | all | 90 | 0 | n/a | n/a | n/a | n/a | n/a |
| 2023 | available | 0 | 0 | n/a | n/a | n/a | n/a | n/a |
| 2023 | missing | 90 | 0 | n/a | n/a | n/a | n/a | n/a |
| 2024 | all | 770 | 770 | -0.552 | 3.333 | 16.689 | 0.192 | 0.708 |
| 2024 | available | 334 | 334 | 0.051 | 0.560 | 2.331 | 0.048 | 0.976 |
| 2024 | missing | 436 | 436 | -1.014 | 5.457 | 16.689 | 0.303 | 0.645 |

## Bootstrap uncertainty of the structural expected gap

400 within-cycle race bootstrap draws (seed 20260908). SE is the standard deviation of the expected gap across draws; the WAR interval subtracts the 5th/95th expected-gap percentiles from the observed raw gap. `Stable party` is the share of races whose D/R/EVEN label matched the headline in every draw.

### By cycle

| Cycle | Races | Median SE | Mean SE | Median WAR interval width | Interval excludes zero | Stable party | Mean party agreement |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all | 3,660 | 0.759 | 0.994 | 2.466 | 0.792 | 0.630 | 0.949 |
| 2018 | 1,025 | 1.101 | 1.186 | 3.619 | 0.801 | 0.640 | 0.951 |
| 2019 | 144 | 2.364 | 2.528 | 7.616 | 0.785 | 0.653 | 0.947 |
| 2020 | 870 | 0.674 | 0.794 | 2.195 | 0.809 | 0.654 | 0.954 |
| 2022 | 761 | 0.565 | 0.701 | 1.869 | 0.765 | 0.587 | 0.941 |
| 2023 | 90 | 3.483 | 3.320 | 11.467 | 0.744 | 0.622 | 0.936 |
| 2024 | 770 | 0.618 | 0.693 | 2.019 | 0.794 | 0.630 | 0.949 |

### By state

| State | Races | Median SE | Median WAR interval width | Interval excludes zero | Stable party |
| --- | --- | --- | --- | --- | --- |
| AL | 97 | 1.344 | 4.385 | 0.660 | 0.485 |
| AR | 195 | 1.092 | 3.541 | 0.815 | 0.626 |
| FL | 400 | 0.461 | 1.493 | 0.785 | 0.650 |
| GA | 429 | 0.645 | 2.114 | 0.767 | 0.615 |
| KY | 266 | 1.478 | 4.777 | 0.838 | 0.658 |
| LA | 36 | 2.775 | 8.747 | 0.667 | 0.472 |
| MO | 412 | 0.658 | 2.168 | 0.842 | 0.694 |
| MS | 56 | 2.389 | 7.861 | 0.696 | 0.482 |
| NC | 530 | 0.704 | 2.299 | 0.813 | 0.664 |
| OK | 204 | 1.262 | 4.226 | 0.794 | 0.662 |
| SC | 236 | 0.770 | 2.541 | 0.788 | 0.597 |
| TN | 246 | 0.751 | 2.415 | 0.797 | 0.573 |
| TX | 411 | 0.645 | 2.113 | 0.747 | 0.569 |
| VA | 142 | 2.805 | 9.141 | 0.824 | 0.746 |

## Headline WAR versus the same-cycle cross-fitted residual

The published `validation_cross_fitted_residual` is a separate validation diagnostic and is never WAR. This table describes how far the descriptive headline sits from it.

| Cycle | Races | Headline WAR MAE | Cross-fitted residual MAE | MAE of difference | Max abs difference | Pearson | Sign agreement |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all | 3,660 | 5.242 | 6.246 | 2.399 | 18.365 | 0.926 | 0.845 |
| 2018 | 1,025 | 6.422 | 6.532 | 0.514 | 6.067 | 0.997 | 0.972 |
| 2019 | 144 | 13.665 | 14.591 | 2.930 | 10.700 | 0.983 | 0.917 |
| 2020 | 870 | 4.648 | 5.477 | 2.498 | 10.938 | 0.905 | 0.847 |
| 2022 | 761 | 3.142 | 4.538 | 2.921 | 11.840 | 0.788 | 0.763 |
| 2023 | 90 | 16.320 | 18.788 | 6.534 | 18.365 | 0.978 | 0.844 |
| 2024 | 770 | 3.550 | 5.397 | 3.697 | 15.155 | 0.773 | 0.743 |

## What this audit does not establish

- **No predictive validation.** Every alternative, interval and comparison is a same-cycle descriptive refit on the published race universe. Nothing here is a forward, held-out or prospective test, and the cross-fitted comparison remains a same-cycle descriptive residual diagnostic, not out-of-time evidence.
- **No external reference certification.** The audit does not compare any value with Split Ticket or another external WAR series, does not certify the baseline comparators, the warehouse source lineage, plan vintages or excluded races, and does not resolve the open source-file lineage findings recorded elsewhere.
- **Descriptive same-cycle residual only.** Bootstrap SE and intervals describe sampling variability of the structural fit conditional on the selected design, the ridge alpha, the zero-fill encoding and the observed race universe. They exclude specification and alpha selection uncertainty, baseline measurement error and the outcome's own noise, and they are not forecast intervals or candidate-effect estimates.
- **Not a release decision.** The alternatives are audit instruments, not replacement WAR definitions. Running this audit records evidence for reviewers; it does not change model values, clear the upstream release gate or approve publication.
