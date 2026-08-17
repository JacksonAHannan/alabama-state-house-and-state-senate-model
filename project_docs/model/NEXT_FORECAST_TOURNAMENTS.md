# Next forecast tournaments

## Basic-model guardrail

The benchmark is deliberately simple: prior district presidential margin plus the final A-rated national generic-ballot swing under the supported post-2016 transfer rule. A complex model must improve mean MAE by at least 0.25 points, recent MAE by 0.10, 2022 by 0.10, at least four of six cycles, never lose by more than one point in a cycle, and have a cycle-bootstrap 95% upper bound below zero.

| Specification | Mean MAE | Delta vs basic | 95% cycle-bootstrap delta | 2018-22 | 2022 | Cycles improved | Gate |
|---|---:|---:|---:|---:|---:|---:|---|
| all_plus_candidate_history__ridge20__blend20 | 23.03 | -1.58 | [-2.70, -0.36] | 11.42 | 10.56 | 5 | fail |
| demographics_regions_finance_incumbency__ridge20__blend20 | 23.03 | -1.58 | [-2.70, -0.36] | 11.42 | 10.56 | 5 | fail |
| demographics_regions_finance__ridge20__blend20 | 23.07 | -1.54 | [-2.71, -0.30] | 11.54 | 10.65 | 5 | fail |
| demographics_regions__ridge20__blend20 | 23.13 | -1.48 | [-2.69, -0.22] | 11.70 | 10.91 | 4 | fail |
| all_plus_candidate_history__ridge100__blend20 | 23.14 | -1.47 | [-2.70, -0.13] | 11.74 | 10.92 | 4 | fail |
| demographics_regions_finance_incumbency__ridge100__blend20 | 23.14 | -1.47 | [-2.70, -0.12] | 11.74 | 10.92 | 4 | fail |
| demographics__ridge20__blend20 | 23.14 | -1.47 | [-2.70, -0.10] | 11.73 | 10.97 | 4 | fail |
| demographics_regions_finance__ridge100__blend20 | 23.15 | -1.46 | [-2.70, -0.09] | 11.76 | 10.95 | 4 | fail |
| demographics_regions__ridge100__blend20 | 23.15 | -1.46 | [-2.70, -0.08] | 11.76 | 10.96 | 4 | fail |
| demographics__ridge100__blend20 | 23.16 | -1.46 | [-2.69, -0.08] | 11.77 | 10.97 | 4 | fail |
| all_plus_candidate_history__ridge20__blend10 | 23.50 | -1.12 | [-1.77, -0.43] | 11.10 | 9.97 | 5 | fail |
| demographics_regions_finance_incumbency__ridge20__blend10 | 23.50 | -1.12 | [-1.77, -0.43] | 11.10 | 9.97 | 5 | fail |

## Past-only selection audit

A selector restricted to earlier held-out cycles produced mean MAE 24.07, versus 24.61 for always using the basic model. It selected the basic model in 2 of 6 cycles.

## 2026 basic views

The 75% view is -2.11 points from default. The continued-nationalization 125% view is +2.11 points from default. The 125% view is explicitly untestable and cannot win the statistical tournament.

Regional variables are fitted jointly and shrunk in the tournament. Candidate-history specifications are historical research only until an equivalent 2026 feature build is available.
