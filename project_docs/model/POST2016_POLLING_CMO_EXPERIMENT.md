# Post-2016 polling-CMO forecast experiment

## Question

Treat the polling-implied national swing as the prospective federal result in each district, then estimate the legislative-minus-federal residual from generic downballot lag, incumbency, and fundraising. Training is restricted to elections after 2016.

## Data and validation

The common finance-complete panel has 59 contested races in 2018 and 30 in 2022. The only genuine forward test trains on 2018 and predicts 2022.
Historical generic-ballot snapshots use the final nonpartisan poll from each currently B-or-better Silver-rated pollster within 21 days of the election. The resulting polling margins are 2018: D+7.68 (10 pollsters), 2022: D-1.89 (14 pollsters).

The baseline is the previous presidential margin in the district plus the polling-implied national swing. Realized national House results are retained only for diagnostics and never enter a feature. The target is the observed legislative margin minus that polling-federal baseline.

2022 incumbency is reconstructed by exact resolved-name matches to 2018 winners in the same chamber and party. District equality is not required because the 2022 election followed redistricting.

Fundraising is cash contributions plus other receipts from the identified Alabama principal campaign committee during the election calendar year and preceding calendar year. The model uses `log1p(D / $50,000) - log1p(R / $50,000)`. Missing committee observations remain missing; the 2026 finance term is omitted for those races rather than converted to zero.

The orthogonalized version first predicts that log fundraising gap from the polling-federal margin, its absolute value, chamber, and incumbency balance. In the forward test, this first-stage model is fit only on 2018 before generating 2022 residuals. No legislative result, CMO target, or realized national result enters the first stage.

A second orthogonalization sensitivity fits that same outcome-free first stage separately within 2018 and 2022. This uses the 2022 covariate and fundraising distribution but never the 2022 legislative result, mirroring a forecast in which the current cycle's complete finance snapshot is available before Election Day.

## Forward result

| Specification | 2022 MAE | RMSE | Winner accuracy | Improvement vs polling federal |
|---|---:|---:|---:|---:|
| polling_federal_plus_incumbency_within_cycle_orthogonal_fundraising | 7.08 | 11.46 | 90.0% | +2.91 |
| polling_federal_plus_fundraising | 8.18 | 12.75 | 90.0% | +1.82 |
| polling_federal_plus_incumbency_fundraising | 8.43 | 13.02 | 90.0% | +1.57 |
| polling_federal_plus_within_cycle_orthogonal_fundraising | 8.47 | 12.63 | 93.3% | +1.52 |
| polling_federal_plus_incumbency_viability | 8.47 | 12.75 | 90.0% | +1.52 |
| polling_federal_plus_orthogonal_fundraising | 8.55 | 13.12 | 90.0% | +1.45 |
| polling_federal_plus_incumbency_partial_orthogonal25 | 8.64 | 13.16 | 90.0% | +1.36 |
| polling_federal_plus_incumbency_partial_orthogonal50 | 8.84 | 13.33 | 90.0% | +1.16 |
| polling_federal_plus_incumbency_partial_orthogonal75 | 9.04 | 13.51 | 90.0% | +0.96 |
| polling_federal_plus_incumbency_orthogonal_fundraising | 9.26 | 13.69 | 93.3% | +0.74 |
| polling_federal_plus_incumbency | 9.54 | 14.13 | 90.0% | +0.46 |
| polling_federal_only | 10.00 | 14.57 | 90.0% | +0.00 |
| polling_federal_plus_generic_lag | 10.30 | 15.33 | 90.0% | -0.31 |

The best observed specification is `polling_federal_plus_incumbency_within_cycle_orthogonal_fundraising` at 7.08 MAE. The raw combined incumbency-and-fundraising model records 8.43 MAE, the cross-cycle orthogonalized combined model records 9.26, the within-cycle covariate-orthogonalized model records 7.08, and the unadjusted polling-federal baseline records 10.00.

Paired race bootstrap comparisons for the combined model:

| Reference | Mean MAE improvement | 95% interval | Probability of improvement |
|---|---:|---:|---:|
| polling_federal_only | +1.57 | [-0.68, +3.86] | 91.4% |
| polling_federal_plus_incumbency | +1.11 | [-0.85, +2.82] | 87.7% |
| polling_federal_only | +0.74 | [-1.99, +3.46] | 70.9% |
| polling_federal_plus_incumbency | +0.28 | [-2.36, +2.59] | 60.6% |
| polling_federal_only | +2.91 | [+0.83, +5.00] | 99.6% |
| polling_federal_plus_incumbency | +2.46 | [+0.47, +4.26] | 99.0% |

Combined-model coefficient stability (points of Democratic margin per original-scale unit):

| Model | Fit sample | Term | Coefficient |
|---|---|---|---:|
| polling_federal_plus_incumbency_fundraising | pooled_2018_2022 | incumbency_balance | +6.35 |
| polling_federal_plus_incumbency_fundraising | pooled_2018_2022 | fundraising_gap_log50 | +4.92 |
| polling_federal_plus_incumbency_orthogonal_fundraising | pooled_2018_2022 | incumbency_balance | +8.85 |
| polling_federal_plus_incumbency_within_cycle_orthogonal_fundraising | pooled_2018_2022 | incumbency_balance | +8.70 |
| polling_federal_plus_incumbency_fundraising | cycle_2018 | incumbency_balance | +7.61 |
| polling_federal_plus_incumbency_fundraising | cycle_2018 | fundraising_gap_log50 | +5.69 |
| polling_federal_plus_incumbency_orthogonal_fundraising | cycle_2018 | incumbency_balance | +9.05 |
| polling_federal_plus_incumbency_within_cycle_orthogonal_fundraising | cycle_2018 | incumbency_balance | +9.05 |
| polling_federal_plus_incumbency_fundraising | cycle_2022 | incumbency_balance | +1.73 |
| polling_federal_plus_incumbency_fundraising | cycle_2022 | fundraising_gap_log50 | +4.08 |
| polling_federal_plus_incumbency_orthogonal_fundraising | cycle_2022 | incumbency_balance | +5.03 |
| polling_federal_plus_incumbency_within_cycle_orthogonal_fundraising | cycle_2022 | incumbency_balance | +5.03 |
| polling_federal_plus_incumbency_orthogonal_fundraising | pooled_2018_2022 | fundraising_gap_residualized | +8.00 |
| polling_federal_plus_incumbency_within_cycle_orthogonal_fundraising | pooled_2018_2022 | fundraising_gap_within_cycle_residualized | +7.74 |
| polling_federal_plus_incumbency_orthogonal_fundraising | cycle_2018 | fundraising_gap_residualized | +7.55 |
| polling_federal_plus_incumbency_within_cycle_orthogonal_fundraising | cycle_2018 | fundraising_gap_within_cycle_residualized | +7.55 |
| polling_federal_plus_incumbency_orthogonal_fundraising | cycle_2022 | fundraising_gap_residualized | +6.37 |
| polling_federal_plus_incumbency_within_cycle_orthogonal_fundraising | cycle_2022 | fundraising_gap_within_cycle_residualized | +6.37 |

Global shrinkage sensitivity for the combined adjustment:

| Model | Adjustment weight | 2022 MAE | RMSE |
|---|---:|---:|---:|
| polling_federal_plus_incumbency_fundraising | 0% | 10.00 | 14.57 |
| polling_federal_plus_incumbency_fundraising | 25% | 8.63 | 13.45 |
| polling_federal_plus_incumbency_fundraising | 50% | 7.69 | 12.79 |
| polling_federal_plus_incumbency_fundraising | 75% | 7.58 | 12.64 |
| polling_federal_plus_incumbency_fundraising | 100% | 8.43 | 13.02 |
| polling_federal_plus_incumbency_orthogonal_fundraising | 0% | 10.00 | 14.57 |
| polling_federal_plus_incumbency_orthogonal_fundraising | 25% | 8.42 | 13.28 |
| polling_federal_plus_incumbency_orthogonal_fundraising | 50% | 7.58 | 12.65 |
| polling_federal_plus_incumbency_orthogonal_fundraising | 75% | 8.10 | 12.80 |
| polling_federal_plus_incumbency_orthogonal_fundraising | 100% | 9.26 | 13.69 |
| polling_federal_plus_incumbency_within_cycle_orthogonal_fundraising | 0% | 10.00 | 14.57 |
| polling_federal_plus_incumbency_within_cycle_orthogonal_fundraising | 25% | 8.54 | 13.29 |
| polling_federal_plus_incumbency_within_cycle_orthogonal_fundraising | 50% | 7.54 | 12.30 |
| polling_federal_plus_incumbency_within_cycle_orthogonal_fundraising | 75% | 6.92 | 11.67 |
| polling_federal_plus_incumbency_within_cycle_orthogonal_fundraising | 100% | 7.08 | 11.46 |

These weights were evaluated after inspecting the sole holdout. The locally best weight varies by fundraising treatment, so every shrunk result remains a sensitivity rather than an independently selected tuning parameter.

Fundraising first-stage diagnostics:

| Sample | Races | MAE | RMSE | R² | Residual corr. with incumbency |
|---|---:|---:|---:|---:|---:|
| 2018_in_sample | 59 | 0.51 | 0.71 | 0.31 | +0.04 |
| 2022_forward | 30 | 1.01 | 1.30 | 0.12 | +0.41 |
| 2022_within_cycle_covariate_fit | 30 | 0.83 | 0.99 | 0.48 | +0.10 |

## 2026 construction

The primary experimental baseline is the 2024 presidential district margin plus the current national generic-ballot swing. Parallel scenarios use raw fundraising, a cross-cycle structural residual, and a residual normalized within each election cycle using only contemporaneously observable covariates. Sensitivities show 75%-shrunk candidate adjustments and the existing demographic-transfer polling baseline. Models are refit on both 2018 and 2022 after the forward test.

Cutoff-specific official Alabama committee summaries are complete for 45/48 currently contested Democratic-versus-Republican races. Complete races receive the combined lag, incumbency, and fundraising adjustment. The remaining races receive the separately fitted lag-plus-incumbency adjustment and are flagged `finance_model_applied = false`.

Win probabilities use the already validated Student-t link with 5 degrees of freedom and a 5.75-point scale. This experiment changes predicted margins, not the probability calibration.

## Interpretation and gate

This design directly tests the proposed forecast interpretation of CMO: polling supplies the expected federal vote, while candidate and campaign factors explain the expected downballot deviation. The orthogonal feature asks whether fundraising is unusual relative to the amount predicted by district structure and incumbency. It is predictive, not causal; the residual can still reflect donor information, candidate quality, campaign strategy, and measurement error.

Do not replace the live headline from this result alone. The post-2016 Alabama gate provides one forward holdout, historical finance is full-cycle rather than cutoff-aligned to the present 2026 snapshot, and candidate fundraising is endogenous. Promotion requires either comparable multi-state finance or a second Alabama forward cycle.
