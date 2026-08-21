# Regional and polling forecast challengers

## Final A-rated generic ballots

Pollsters are screened using the current Nate Silver grades in the repository; A+, A, and A- qualify. The final nonpartisan poll from each qualifying pollster within 21 days of Election Day is retained, then pollsters are averaged equally. This is a survivorship-conditioned research series, not a historically contemporaneous rating screen.

| Cycle | Pollsters | Final A-rated margin | Actual House margin | Error |
|---:|---:|---:|---:|---:|
| 1998 | 3 | +1.23 | -0.89 | +2.12 |
| 2002 | 4 | -0.85 | -4.71 | +3.86 |
| 2006 | 3 | +14.68 | +7.89 | +6.79 |
| 2010 | 4 | -3.98 | -6.51 | +2.53 |
| 2014 | 3 | -1.75 | -5.62 | +3.87 |
| 2018 | 5 | +8.88 | +8.51 | +0.37 |
| 2022 | 8 | -1.97 | -2.64 | +0.67 |

The provisional 2026 A-rated-only snapshot is D+7.66 across 7 pollsters through 2026-06-22. It is not a final-cycle estimate and is older than the broader B+-rated environment feed.

## Legislative backtest

| Specification | Mean MAE | 2018–22 MAE | 2022 MAE | Delta vs oracle |
|---|---:|---:|---:|---:|
| a_poll_post2016_ramp_plus_20pct_ridge | 22.56 | 11.41 | 10.64 | -2.04 |
| a_poll_full_transfer | 24.17 | 11.17 | 9.86 | -0.43 |
| oracle_post2016_environment | 24.60 | 11.13 | 9.78 | +0.00 |
| a_poll_post2016_ramp | 24.61 | 11.17 | 9.86 | +0.01 |
| prior_presidential | 25.08 | 12.57 | 12.03 | +0.48 |
| a_poll_two_step_transfer | 25.41 | 11.17 | 9.86 | +0.81 |

The oracle comparator uses the eventual national House environment and is unavailable prospectively. A polling challenger that approaches it without using election results is operationally preferable even when its raw MAE is slightly higher.

## Regional transfer test

| Regional challenger | 2022 MAE | Gain vs polling ridge | Largest adjustment |
|---|---:|---:|---:|
| poll_ramp_plus_regional_100 | 10.32 | -0.46 | 5.73 |
| poll_ramp_plus_regional_25 | 9.97 | -0.12 | 1.43 |
| poll_ramp_plus_regional_50 | 10.09 | -0.23 | 2.87 |
| poll_ridge_plus_regional_100 | 11.08 | -0.44 | 5.73 |
| poll_ridge_plus_regional_25 | 10.73 | -0.09 | 1.43 |
| poll_ridge_plus_regional_50 | 10.82 | -0.18 | 2.87 |

The 2022 regional test estimates effects only from 2018 and 2020 precinct results, caps them at eight points, maps precinct representative points into legislative districts, and then tests partial blends. It is a one-cycle confirmation and therefore cannot by itself select a production weight.
