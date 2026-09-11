# Alabama historical WAR backcast sensitivity — 2026-09-11

Internal execution evidence for checklist items `alabama-07` (label and test the cross-era backcasts: era sensitivity and transportability of the 412 pre-2016 races) and `alabama-08` (18 races with missing lag context: test the effect of the zero-fill compatibility encoding).

This is a **read-only sensitivity audit**. No data, model, warehouse, checklist or published export was modified. The machine-readable companion of this report is `ALABAMA_BACKCAST_SENSITIVITY_2026_09_11.json` in this directory; the full CSV set and an identical `summary.json` are written under `data/processed/war/alabama_historical_war_v1_sensitivity` (`generated_at_utc` `2026-09-11T15:07:08.095186+00:00`).

## What was audited

- Published historical run: `AL-HIST-WAR-V1-76814789B2F7641E4255` (bound expected id `AL-HIST-WAR-V1-76814789B2F7641E4255`)
- Warehouse build run: `RUN-504CE4C4DF904D88A5A40D268F3FCEAB` (live `RUN-504CE4C4DF904D88A5A40D268F3FCEAB`)
- Southern source run: `WAR-POST2016-V3-530FBD4238CC483E557C`; Alabama modern source: `AL-WAR-V1-C00FF05BC2BE58E16087`
- `manifest.json` SHA256 `da0333ff2603d4d9d3422e766670552b484ad0b74a88b48bfc62056867fc3bc9`; `race_war.csv` SHA256 `6ad950e385cddf8c3636679b1304523c0702bb916ce1129efc6763c5ef859fdc`
- Audit script SHA256 `a6631a2f39d8ab1d17856641cf17e390a3a2a1abec9fce3bbb08bea9762635e5`
- Generated (UTC) 2026-09-11T15:07:08.095186+00:00; runtime 2.03 s; repository commit `38c30819f3524c3d97cb7a1bfa4fb6ec00e8f249`
- Published specification `decaying_lag` with alpha 100; no-lag comparator `fundamentals_no_lag`
- Machine-readable outputs: `data/processed/war/alabama_historical_war_v1_sensitivity`
- Commands: `.venv/Scripts/python.exe scripts/audit_alabama_backcast_sensitivity.py --draws 200 --seed 20260911` and `.venv/Scripts/python.exe -m pytest --testmon --testmon-noselect -p no:cacheprovider scripts/tests/test_alabama_backcast_sensitivity.py -q`

Reproduction path: `scripts/build_alabama_historical_war_v1.prepare_historical_races()` rebuilds the 509-race historical frame from `data/processed/war/cmo_v5_races.csv` and `data/processed/elections/canonical_cmo_features.csv`; `retrain_post2016_southern_war_v2.load_training()` reads the modern strict training frame from the central warehouse read-only (`sqlite3.connect('file:...?mode=ro', uri=True)`, one bounded query over `mart_southern_war_training_with_finance` with `cycle > 2016 AND training_status = 'strict_war_ready_no_finance'`); the published design (`v2.design_matrices`) is refitted on the modern rows only and applied to the historical rows exactly as the builder does.

## Parity gate

Status: **passed** (tolerance 1e-08) on the 412 backcast races (cycles 1994-2014). Maximum absolute difference between the rebuild and the published values:

- `raw_gap_all_509_races`: 3.553e-15
- `raw_gap`: 3.553e-15
- `fitted_structural_expected_gap`: 3.553e-15
- `fitted_structural_nonlag_expected_gap`: 1.776e-15
- `fitted_lag_component`: 1.776e-15
- `war`: 7.105e-15
- `modern_backcast_structural_expected_gap`: 3.553e-15
- `modern_backcast_war`: 7.105e-15

The `raw_gap_all_509_races` line is an input-parity check over every historical race, including the 97 published 2018/2022 races, which preserve the Alabama WAR v1 same-cycle residual instead of being reproduced by this model. The remaining lines are the backcast parity gate on the 412 pre-2016 races; those 412 races are the only ones the diagnostics below use.

Modern training frame: 3,660 strict races over cycles [2018, 2019, 2020, 2022, 2023, 2024]; 2,376 rows (64.9%) carry no validated prior presidential context and therefore enter the selected design with the zero-fill compatibility encoding. Historical frame: 509 races, 412 backcast, 97 published modern (2018/2022).

Every manifest-recorded input hash matches the bytes on disk.

## Era transportability: backcast versus same-era Alabama fit

The published specification and alpha are fitted on the 412-race Alabama frame itself (pooled 1994-2014) to give a **same-era descriptive comparator**. It shares the specification but not the training data, so a level difference is expected: the modern fit extrapolates `years_since_2016` (training support 2-8 years) to -22…-2 years, while the era fit estimates that term inside the historical window. Correlation and sign agreement describe whether the two residuals order races alike; the difference distribution describes the level shift.

### Per-cycle comparison

| Cycle | Races | Backcast mean WAR | Same-era mean WAR | Pearson | Spearman | MAE of difference | Mean diff | Median diff | p05 diff | p95 diff | Max abs diff | Sign change share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all | 412 | 20.455 | 0.000 | 0.939 | 0.936 | 20.693 | -20.455 | -21.657 | -31.347 | -7.427 | 33.149 | 0.340 |
| 1994 | 72 | 18.543 | -2.515 | 0.945 | 0.934 | 21.123 | -21.058 | -23.364 | -29.388 | -6.131 | 30.529 | 0.319 |
| 1998 | 85 | 27.906 | 3.178 | 0.943 | 0.943 | 24.728 | -24.728 | -25.053 | -32.852 | -15.057 | 33.149 | 0.329 |
| 2002 | 74 | 16.771 | -3.875 | 0.964 | 0.958 | 20.647 | -20.647 | -20.681 | -30.337 | -8.735 | 30.892 | 0.311 |
| 2006 | 62 | 31.741 | 10.759 | 0.953 | 0.941 | 21.631 | -20.982 | -21.726 | -30.183 | -11.969 | 31.313 | 0.306 |
| 2010 | 63 | 14.558 | -4.281 | 0.934 | 0.921 | 18.839 | -18.839 | -18.443 | -26.222 | -7.488 | 26.467 | 0.429 |
| 2014 | 56 | 10.610 | -3.567 | 0.908 | 0.911 | 15.126 | -14.177 | -12.614 | -26.683 | -4.662 | 27.915 | 0.357 |

Overall: Pearson 0.939 / Spearman 0.936, MAE of the difference 20.693 points, sign agreement 0.660.

## Leave-one-era-out: 1994-2006 versus 2010-2014

Each half is fitted separately with the published specification and alpha; the table scores the held-out half against the backcast. Coefficient drift on the structural terms shows how unstable the in-era relationship is between the two halves. Direction matters: a fit on the shorter 2010-2014 window extrapolates its `years_since_2016` trend 8-20 years back, so that direction is itself an extrapolation and its MAE and maximum difference are not a clean transportability estimate.

| Fit era | Scored era | Fit races | Scored | Pearson | Spearman | MAE of difference | Mean diff | Max abs diff | Sign change share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1994_2006 | 2010_2014 | 293 | 119 | 0.927 | 0.921 | 26.130 | -26.091 | 37.164 | 0.571 |
| 2010_2014 | 1994_2006 | 119 | 293 | 0.728 | 0.735 | 25.300 | -22.666 | 80.843 | 0.328 |

### Coefficients and era drift (structural terms)

| Feature | Modern backcast | Era pooled | 1994-2006 | 2010-2014 | Era drift | Era-comparable |
| --- | --- | --- | --- | --- | --- | --- |
| incumbency_balance | 6.161 | 13.893 | 13.556 | 6.603 | -6.953 | True |
| baseline_dem_margin | -0.130 | -0.152 | -0.138 | -0.103 | 0.036 | True |
| baseline_margin_squared | 0.114 | -0.093 | -0.124 | -0.001 | 0.123 | True |
| years_since_2016 | 0.134 | -0.339 | 0.314 | -0.723 | -1.037 | True |
| odd_year | -3.320 | 0.000 | 0.000 | 0.000 | 0.000 | False |
| presidential_cycle | -7.289 | 0.000 | 0.000 | 0.000 | 0.000 | False |
| state_code_AL | -0.324 | 0.000 | 0.000 | 0.000 | 0.000 | False |
| state_code_AR | 5.155 | 0.000 | 0.000 | 0.000 | 0.000 | False |
| state_code_FL | 1.205 | 0.000 | 0.000 | 0.000 | 0.000 | False |
| state_code_GA | -1.588 | 0.000 | 0.000 | 0.000 | 0.000 | False |
| state_code_KY | 3.979 | 0.000 | 0.000 | 0.000 | 0.000 | False |
| state_code_LA | -3.742 | 0.000 | 0.000 | 0.000 | 0.000 | False |
| state_code_MO | -0.483 | 0.000 | 0.000 | 0.000 | 0.000 | False |
| state_code_MS | -7.876 | 0.000 | 0.000 | 0.000 | 0.000 | False |
| state_code_NC | -1.796 | 0.000 | 0.000 | 0.000 | 0.000 | False |
| state_code_OK | -1.768 | 0.000 | 0.000 | 0.000 | 0.000 | False |
| state_code_SC | -0.144 | 0.000 | 0.000 | 0.000 | 0.000 | False |
| state_code_TN | -1.269 | 0.000 | 0.000 | 0.000 | 0.000 | False |
| state_code_TX | 1.785 | 0.000 | 0.000 | 0.000 | 0.000 | False |
| state_code_VA | -1.168 | 0.000 | 0.000 | 0.000 | 0.000 | False |
| chamber_lower | -0.123 | -0.033 | 0.078 | 0.431 | 0.353 | True |
| chamber_upper | 0.123 | 0.033 | -0.078 | -0.431 | -0.353 | True |
| baseline_office_family_federal_composite | -0.293 | -0.288 | 0.595 | -0.848 | -1.443 | True |
| baseline_office_family_generic_ballot | -1.168 | 0.000 | 0.000 | 0.000 | 0.000 | False |
| baseline_office_family_governor | -0.589 | 0.000 | 0.000 | 0.000 | 0.000 | False |
| baseline_office_family_president | 3.317 | 0.000 | 0.000 | 0.000 | 0.000 | False |
| baseline_office_family_state_composite | -3.252 | 0.288 | -0.595 | 0.848 | 1.443 | True |
| baseline_office_family_statewide_other | -4.227 | 0.000 | 0.000 | 0.000 | 0.000 | False |
| baseline_office_family_us_house | 5.785 | 0.000 | 0.000 | 0.000 | 0.000 | False |
| baseline_office_family_us_senate | -4.998 | 0.000 | 0.000 | 0.000 | 0.000 | False |

Largest era drift among era-comparable structural terms: `incumbency_balance` -6.953 (1994-2006 13.556 to 2010-2014 6.603; pooled 13.893, modern backcast 6.161). Terms whose column is constant inside an era window are marked not era-comparable and their coefficients are not identified there. Because the design keeps every categorical level, complementary dummy pairs (`chamber_lower`/`chamber_upper`, `baseline_office_family_federal_composite`/`state_composite`) carry mirrored coefficients; each mirrored pair is one degree of freedom, not two.

### Lag-term coefficients

| Feature | Modern backcast | Era pooled | 1994-2006 | 2010-2014 | Era drift | Era-comparable |
| --- | --- | --- | --- | --- | --- | --- |
| prior_pres_margin | 0.071 | -0.093 | -0.106 | -0.047 | 0.058 | True |
| lag_current_ticket_change | -0.105 | -0.279 | -0.251 | -0.134 | 0.117 | True |
| lag_change_x_years | 0.005 | 0.007 | 0.008 | 0.055 | 0.047 | True |

## Missing lag context: the zero-fill encoding

18 of the 412 backcast races carry `lag_context_available == False`. Their three lag design columns are set to 0.0, so their published `fitted_lag_component` is exactly zero by construction while the encoding still influenced the modern coefficients those rows are scored with. `war_no_lag_spec` refits the `fundamentals_no_lag` design on the modern frame; `war_lag_available_fit` refits the published design on modern rows with validated lag context only. Both are recomputed alternatives, not replacement WAR. Missing-context counts by cycle: 1994 5, 1998 2, 2002 7, 2006 4.

Across those races the `no_lag_spec` delta ranges +2.008 to +5.864 WAR points (mean +3.874), while `lag_available_fit` ranges -17.187 to -0.045 (mean -9.117). The larger swing comes from changing which modern rows estimate the base coefficients, so the encoding's influence is not confined to the zero entries of those 18 races.

### The 18 no-context races

| Cycle | Chamber | District | Prior pres margin | Raw gap | Backcast WAR | No-lag WAR | No-lag diff | Party | No-lag party | Lag-avail WAR | Lag-avail diff |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1994 | lower | 33 | n/a | -2.867 | 3.173 | 7.006 | 3.833 | D | D | -14.014 | -17.187 |
| 1994 | lower | 49 | n/a | -2.749 | 0.150 | 4.819 | 4.670 | D | D | -14.176 | -14.326 |
| 1994 | lower | 73 | n/a | 12.568 | 4.211 | 10.075 | 5.864 | D | D | -0.221 | -4.432 |
| 1994 | lower | 76 | n/a | 16.556 | 22.235 | 26.212 | 3.976 | D | D | 5.386 | -16.849 |
| 1994 | lower | 97 | n/a | 1.512 | 10.768 | 15.998 | 5.231 | D | D | -4.336 | -15.104 |
| 1998 | lower | 8 | n/a | 40.046 | 37.188 | 41.026 | 3.838 | D | D | 27.524 | -9.664 |
| 1998 | lower | 9 | n/a | 8.953 | 10.862 | 15.075 | 4.213 | D | D | -0.931 | -11.793 |
| 2002 | lower | 13 | n/a | 39.544 | 39.506 | 43.401 | 3.895 | D | D | 31.093 | -8.413 |
| 2002 | lower | 41 | n/a | -7.688 | -10.273 | -5.422 | 4.851 | R | R | -14.425 | -4.152 |
| 2002 | lower | 59 | n/a | 13.222 | 19.110 | 21.217 | 2.107 | D | D | 5.257 | -13.853 |
| 2002 | lower | 63 | n/a | -1.202 | -3.139 | 0.999 | 4.138 | R | D | -9.874 | -6.735 |
| 2002 | lower | 70 | n/a | 9.817 | 15.685 | 17.824 | 2.139 | D | D | 1.855 | -13.829 |
| 2002 | upper | 15 | n/a | -23.151 | -25.438 | -20.666 | 4.773 | R | R | -30.644 | -5.206 |
| 2002 | upper | 19 | n/a | 6.674 | 6.122 | 8.130 | 2.008 | D | D | -4.894 | -11.016 |
| 2006 | lower | 101 | n/a | 8.319 | 6.047 | 10.300 | 4.253 | D | D | 3.281 | -2.765 |
| 2006 | lower | 102 | n/a | -0.396 | -8.074 | -3.985 | 4.089 | R | R | -8.120 | -0.045 |
| 2006 | upper | 33 | n/a | 24.999 | 22.279 | 24.627 | 2.347 | D | D | 14.965 | -7.314 |
| 2006 | upper | 35 | n/a | 26.621 | 17.300 | 20.804 | 3.504 | D | D | 15.879 | -1.421 |

### Summary by cycle and lag-context status

#### `no_lag_spec` (fundamentals_no_lag design fitted on the modern frame)

| Cycle | Lag context | Races | Scored | Mean diff | MAE | Max abs diff | Sign change share | Sign changes | Pearson | Spearman |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all | all | 412 | 412 | 2.446 | 4.026 | 25.551 | 0.049 | 20 | 0.982 | 0.982 |
| all | available | 394 | 394 | 2.381 | 4.033 | 25.551 | 0.048 | 19 | 0.982 | 0.982 |
| all | missing | 18 | 18 | 3.874 | 3.874 | 5.864 | 0.056 | 1 | 0.998 | 0.990 |
| 1994 | all | 72 | 72 | 3.713 | 5.556 | 16.713 | 0.083 | 6 | 0.974 | 0.977 |
| 1994 | available | 67 | 67 | 3.638 | 5.619 | 16.713 | 0.090 | 6 | 0.974 | 0.977 |
| 1994 | missing | 5 | 5 | 4.715 | 4.715 | 5.864 | 0.000 | 0 | 0.995 | 1.000 |
| 1998 | all | 85 | 85 | 6.427 | 6.476 | 15.636 | 0.047 | 4 | 0.985 | 0.983 |
| 1998 | available | 83 | 83 | 6.485 | 6.535 | 15.636 | 0.048 | 4 | 0.985 | 0.982 |
| 1998 | missing | 2 | 2 | 4.025 | 4.025 | 4.213 | 0.000 | 0 | n/a | n/a |
| 2002 | all | 74 | 74 | 1.055 | 3.514 | 9.038 | 0.081 | 6 | 0.988 | 0.984 |
| 2002 | available | 67 | 67 | 0.808 | 3.524 | 9.038 | 0.075 | 5 | 0.988 | 0.984 |
| 2002 | missing | 7 | 7 | 3.416 | 3.416 | 4.851 | 0.143 | 1 | 0.999 | 1.000 |
| 2006 | all | 62 | 62 | 0.210 | 2.664 | 25.551 | 0.000 | 0 | 0.989 | 0.994 |
| 2006 | available | 58 | 58 | -0.020 | 2.603 | 25.551 | 0.000 | 0 | 0.989 | 0.993 |
| 2006 | missing | 4 | 4 | 3.548 | 3.548 | 4.253 | 0.000 | 0 | 0.999 | 1.000 |
| 2010 | all | 63 | 63 | 0.227 | 2.354 | 10.511 | 0.048 | 3 | 0.989 | 0.983 |
| 2010 | available | 63 | 63 | 0.227 | 2.354 | 10.511 | 0.048 | 3 | 0.989 | 0.983 |
| 2010 | missing | 0 | 0 | n/a | n/a | n/a | n/a | 0 | n/a | n/a |
| 2014 | all | 56 | 56 | 1.587 | 2.404 | 9.828 | 0.018 | 1 | 0.989 | 0.991 |
| 2014 | available | 56 | 56 | 1.587 | 2.404 | 9.828 | 0.018 | 1 | 0.989 | 0.991 |
| 2014 | missing | 0 | 0 | n/a | n/a | n/a | n/a | 0 | n/a | n/a |

#### `lag_available_fit` (published design fitted on modern lag-available rows only)

| Cycle | Lag context | Races | Scored | Mean diff | MAE | Max abs diff | Sign change share | Sign changes | Pearson | Spearman |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all | all | 412 | 412 | -6.864 | 8.597 | 45.069 | 0.153 | 63 | 0.931 | 0.916 |
| all | available | 394 | 394 | -6.761 | 8.574 | 45.069 | 0.145 | 57 | 0.930 | 0.916 |
| all | missing | 18 | 18 | -9.117 | 9.117 | 17.187 | 0.333 | 6 | 0.943 | 0.930 |
| 1994 | all | 72 | 72 | -14.686 | 18.629 | 45.069 | 0.292 | 21 | 0.843 | 0.764 |
| 1994 | available | 67 | 67 | -14.769 | 19.006 | 45.069 | 0.254 | 17 | 0.843 | 0.757 |
| 1994 | missing | 5 | 5 | -13.580 | 13.580 | 17.187 | 0.800 | 4 | 0.818 | 0.900 |
| 1998 | all | 85 | 85 | -4.159 | 6.801 | 20.664 | 0.118 | 10 | 0.929 | 0.920 |
| 1998 | available | 83 | 83 | -4.000 | 6.706 | 20.664 | 0.108 | 9 | 0.929 | 0.921 |
| 1998 | missing | 2 | 2 | -10.729 | 10.729 | 11.793 | 0.500 | 1 | n/a | n/a |
| 2002 | all | 74 | 74 | -10.803 | 11.325 | 27.739 | 0.257 | 19 | 0.963 | 0.953 |
| 2002 | available | 67 | 67 | -10.988 | 11.565 | 27.739 | 0.269 | 18 | 0.964 | 0.953 |
| 2002 | missing | 7 | 7 | -9.029 | 9.029 | 13.853 | 0.143 | 1 | 0.986 | 1.000 |
| 2006 | all | 62 | 62 | -5.592 | 6.237 | 35.114 | 0.081 | 5 | 0.983 | 0.985 |
| 2006 | available | 58 | 58 | -5.778 | 6.468 | 35.114 | 0.086 | 5 | 0.984 | 0.985 |
| 2006 | missing | 4 | 4 | -2.887 | 2.887 | 7.314 | 0.000 | 0 | 0.983 | 0.800 |
| 2010 | all | 63 | 63 | -3.593 | 4.240 | 17.008 | 0.079 | 5 | 0.989 | 0.984 |
| 2010 | available | 63 | 63 | -3.593 | 4.240 | 17.008 | 0.079 | 5 | 0.989 | 0.984 |
| 2010 | missing | 0 | 0 | n/a | n/a | n/a | n/a | 0 | n/a | n/a |
| 2014 | all | 56 | 56 | -0.798 | 2.338 | 5.783 | 0.054 | 3 | 0.991 | 0.987 |
| 2014 | available | 56 | 56 | -0.798 | 2.338 | 5.783 | 0.054 | 3 | 0.991 | 0.987 |
| 2014 | missing | 0 | 0 | n/a | n/a | n/a | n/a | 0 | n/a | n/a |

## Bootstrap uncertainty of the backcast expected gap

200 within-cycle training-bootstrap draws (seed 20260911): training races resampled with replacement within each modern training cycle, refit on the published specification and alpha, scoring every backcast race. SE is the standard deviation of the backcast expected gap across draws; the WAR interval subtracts the 5th/95th expected-gap percentiles from the observed raw gap. This is training-sample variability of the descriptive fit, not a forecast interval.

| Cycle | Races | Median SE | Mean SE | Median WAR interval width | Interval excludes zero | Stable party | Mean party agreement |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all | 412 | 2.608 | 3.886 | 8.569 | 0.852 | 0.774 | 0.961 |
| 1994 | 72 | 4.685 | 6.620 | 14.830 | 0.694 | 0.583 | 0.925 |
| 1998 | 85 | 4.875 | 5.026 | 15.711 | 0.894 | 0.835 | 0.962 |
| 2002 | 74 | 2.430 | 3.811 | 7.831 | 0.770 | 0.662 | 0.944 |
| 2006 | 62 | 2.251 | 3.105 | 7.346 | 0.952 | 0.903 | 0.992 |
| 2010 | 63 | 1.485 | 1.923 | 4.728 | 0.921 | 0.889 | 0.984 |
| 2014 | 56 | 1.732 | 1.810 | 5.129 | 0.911 | 0.804 | 0.969 |

## Headline numbers

- Same-era versus backcast, per cycle (Pearson / sign agreement): 1994 0.945 / 0.681; 1998 0.943 / 0.671; 2002 0.964 / 0.689; 2006 0.953 / 0.694; 2010 0.934 / 0.571; 2014 0.908 / 0.643.
- Overall same-era comparison: MAE 20.693 points, differences -31.347 to -7.427 (5th-95th), mean -20.455.
- Largest era coefficient drifts (structural, era-comparable): `incumbency_balance` -6.953; `baseline_office_family_state_composite` 1.443; `baseline_office_family_federal_composite` -1.443.
- 18 no-context races, `no_lag_spec` versus backcast: max |delta| 5.864 points, mean 3.874, 1 sign changes; `lag_available_fit`: max |delta| 17.187, 6 sign changes.
- Bootstrap median SE by cycle: 1994 4.685, 1998 4.875, 2002 2.430, 2006 2.251, 2010 1.485, 2014 1.732.

## What this audit does not establish

- **No predictive validation.** The same-era and out-of-era fits are descriptive in-sample or held-out-half comparators on the same historical race universe; nothing here is a forward, as-of or prospective test, and the backcast remains an extrapolation of a modern relationship.
- **No recertification.** Passing the parity gate proves the reconstruction reproduces the published backcast values from the declared inputs; it does not re-approve the run, the modern residual source, the plan vintages or the baseline provenance.
- **No replacement contract.** The same-era fit is not an alternative WAR definition and its residuals are not candidate-quality measures; the published backcast label stands until a separately authorized decision replaces it.
- **No lag identification.** The 18 no-context races cannot identify a lag contribution; the alternatives measure how much their WAR depends on the encoding, not what the correct prior-presidential context would be.
- **Bootstrap limits.** The intervals exclude specification and alpha selection uncertainty, baseline measurement error and outcome noise, and the bootstrap resamples training rows, so it does not describe uncertainty in the historical frame.
