# Historical Shor–McCarty ideology and Democratic overperformance

## Scope

The headline analysis covers matched Democratic candidate-cycles from 1998 through 2018. Alabama service flags in the individual Shor–McCarty file begin in 1996, so 1994 is retained only as a later-observed sensitivity tier. Career ideal points may incorporate post-election votes even when pre-election service is observed.

The full candidate crosswalk contains **476** Democratic candidate-cycles through 2018, with **256** accepted matches. The headline analytical panel contains **209** rows and **179** people.

## Coverage

| cycle | fuzzy_review | matched |
|---|---|---|
| 1994.00 | 25.00 | 47.00 |
| 1998.00 | 27.00 | 58.00 |
| 2002.00 | 24.00 | 50.00 |
| 2006.00 | 27.00 | 35.00 |
| 2010.00 | 26.00 | 37.00 |
| 2014.00 | 32.00 | 24.00 |
| 2018.00 | 59.00 | 5.00 |

## Ideology terciles

| ideology_tercile | candidate_cycles | people | mean_cmo | median_cmo | mean_federal | median_federal | mean_presidential | median_presidential |
|---|---|---|---|---|---|---|---|---|
| liberal | 70.00 | 60.00 | 9.83 | 6.80 | 26.88 | 28.09 | 31.45 | 28.76 |
| middle | 69.00 | 57.00 | 22.64 | 23.53 | 34.31 | 32.41 | 36.67 | 33.31 |
| conservative | 70.00 | 62.00 | 26.90 | 26.40 | 43.57 | 40.80 | 42.13 | 40.18 |

## Headline sequential decomposition

| outcome | specification | n | people | coefficient_per_sd | cluster_se | ci_low | ci_high | p_value | status |
|---|---|---|---|---|---|---|---|---|---|
| candidate_cmo_total_oof | cycle_chamber_total | 209.00 | 179.00 | 7.57 | 0.82 | 5.96 | 9.17 | 0.00 | estimated |
| candidate_cmo_total_oof | plus_district_context | 209.00 | 179.00 | 4.94 | 1.06 | 2.87 | 7.01 | 0.00 | estimated |
| candidate_cmo_total_oof | plus_incumbency | 209.00 | 179.00 | 4.96 | 1.06 | 2.88 | 7.03 | 0.00 | estimated |
| candidate_cmo_total_oof | plus_incumbency_finance | 158.00 | 137.00 | 4.66 | 1.08 | 2.54 | 6.78 | 0.00 | estimated |
| federal_index_overperformance | cycle_chamber_total | 187.00 | 171.00 | 5.51 | 1.43 | 2.72 | 8.31 | 0.00 | estimated |
| federal_index_overperformance | plus_district_context | 187.00 | 171.00 | 7.16 | 2.00 | 3.24 | 11.09 | 0.00 | estimated |
| federal_index_overperformance | plus_incumbency | 187.00 | 171.00 | 7.15 | 2.00 | 3.22 | 11.07 | 0.00 | estimated |
| federal_index_overperformance | plus_incumbency_finance | 139.00 | 131.00 | 8.19 | 2.27 | 3.73 | 12.64 | 0.00 | estimated |
| presidential_overperformance | cycle_chamber_total | 199.00 | 170.00 | 4.33 | 1.37 | 1.64 | 7.01 | 0.00 | estimated |
| presidential_overperformance | plus_district_context | 199.00 | 170.00 | 4.10 | 1.36 | 1.43 | 6.77 | 0.00 | estimated |
| presidential_overperformance | plus_incumbency | 199.00 | 170.00 | 4.17 | 1.35 | 1.51 | 6.82 | 0.00 | estimated |
| presidential_overperformance | plus_incumbency_finance | 150.00 | 129.00 | 2.36 | 1.81 | -1.20 | 5.91 | 0.20 | estimated |

`cycle_chamber_total` preserves the total relationship. District context, incumbency, and finance are then introduced sequentially; attenuation may represent confounding or removal of pathways through which ideological fit helped candidates survive, become incumbents, and raise money.

## Temporal and source-quality sensitivities

| sample | outcome | n | people | coefficient_per_sd | cluster_se | p_value | status |
|---|---|---|---|---|---|---|---|
| pre_election_service | candidate_cmo_total_oof | 177.00 | 152.00 | 7.17 | 0.85 | 0.00 | estimated |
| pre_election_service | federal_index_overperformance | 157.00 | 145.00 | 5.24 | 1.59 | 0.00 | estimated |
| pre_election_service | presidential_overperformance | 170.00 | 146.00 | 3.78 | 1.43 | 0.01 | estimated |
| canonical_federal_geography | candidate_cmo_total_oof | 56.00 | 48.00 | 6.52 | 2.16 | 0.00 | estimated |
| canonical_federal_geography | federal_index_overperformance | 56.00 | 48.00 | 3.36 | 3.23 | 0.30 | estimated |
| canonical_federal_geography | presidential_overperformance | 54.00 | 46.00 | 0.35 | 3.05 | 0.91 | estimated |
| 1994_later_observed_sensitivity | candidate_cmo_total_oof | 47.00 | 44.00 | 4.04 | 2.85 | 0.16 | estimated |
| 1994_later_observed_sensitivity | federal_index_overperformance | 35.00 | 32.00 | 1.70 | 3.08 | 0.58 | estimated |
| 1994_later_observed_sensitivity | presidential_overperformance | 44.00 | 42.00 | -3.87 | 2.06 | 0.07 | estimated |

## Era results

| sample | outcome | n | people | coefficient_per_sd | cluster_se | p_value | status |
|---|---|---|---|---|---|---|---|
| era:2008_2014 | candidate_cmo_total_oof | 61.00 | 50.00 | 7.70 | 2.03 | 0.00 | estimated |
| era:2008_2014 | federal_index_overperformance | 51.00 | 45.00 | 0.05 | 3.48 | 0.99 | estimated |
| era:2008_2014 | presidential_overperformance | 59.00 | 48.00 | 1.13 | 2.62 | 0.67 | estimated |
| era:post_2016 | candidate_cmo_total_oof | 5.00 | 5.00 |  |  |  | underpowered |
| era:post_2016 | federal_index_overperformance | 5.00 | 5.00 |  |  |  | underpowered |
| era:post_2016 | presidential_overperformance | 5.00 | 5.00 |  |  |  | underpowered |
| era:pre_2008 | candidate_cmo_total_oof | 143.00 | 142.00 | 7.29 | 1.00 | 0.00 | estimated |
| era:pre_2008 | federal_index_overperformance | 131.00 | 130.00 | 5.70 | 1.79 | 0.00 | estimated |
| era:pre_2008 | presidential_overperformance | 135.00 | 134.00 | 5.22 | 1.45 | 0.00 | estimated |

## Interpretation limits

- Shor–McCarty is a one-dimensional career roll-call score, not a cycle-specific social-conservatism measure.
- Challengers who never served cannot receive a Shor score, creating survivor selection.
- The 1994 sensitivity tier uses people observed from 1996 onward and is not contemporaneous evidence.
- Pre-2010 federal district baselines include provisional geographic allocations; the canonical-geography sample is reported separately.
- These estimates are descriptive associations, not causal effects.
