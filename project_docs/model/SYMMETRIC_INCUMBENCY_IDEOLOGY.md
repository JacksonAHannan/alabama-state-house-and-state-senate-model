# Symmetric incumbency and absolute ideology

## Design

Candidate-directional performance is positive when either party's candidate runs ahead of the named baseline. The party-specific model estimates Republican incumbency and a Democratic-minus-Republican incumbency interaction. The constrained model removes that interaction and estimates ideology on the national absolute Shor–McCarty scale.

## Match coverage

| cycle | party | ambiguous_exact | fuzzy_review | matched |
|---|---|---|---|---|
| 1998.000 | D | 0.000 | 27.000 | 58.000 |
| 1998.000 | R | 0.000 | 53.000 | 32.000 |
| 2002.000 | D | 0.000 | 24.000 | 50.000 |
| 2002.000 | R | 0.000 | 49.000 | 25.000 |
| 2006.000 | D | 0.000 | 27.000 | 35.000 |
| 2006.000 | R | 0.000 | 39.000 | 23.000 |
| 2010.000 | D | 0.000 | 26.000 | 37.000 |
| 2010.000 | R | 1.000 | 20.000 | 42.000 |
| 2014.000 | D | 0.000 | 32.000 | 24.000 |
| 2014.000 | R | 0.000 | 15.000 | 41.000 |
| 2018.000 | D | 0.000 | 59.000 | 5.000 |
| 2018.000 | R | 0.000 | 29.000 | 35.000 |

## Absolute ideological position

| party | incumbent_i | candidate_cycles | people | mean_absolute_np | median_absolute_np | mean_national_party_conservative_percentile |
|---|---|---|---|---|---|---|
| D | 0.000 | 163.000 | 100.000 | -0.163 | -0.113 | 83.398 |
| D | 1.000 | 46.000 | 42.000 | -0.218 | -0.165 | 82.414 |
| R | 0.000 | 126.000 | 101.000 | 0.913 | 0.954 | 64.416 |
| R | 1.000 | 72.000 | 60.000 | 0.930 | 0.936 | 65.891 |

For comparison, the complete national source distribution is:

| party | national_legislators | national_mean_np | national_median_np |
|---|---|---|---|
| D | 11666.000 | -0.773 | -0.790 |
| R | 12560.000 | 0.759 | 0.758 |
| X | 139.000 | -0.120 | -0.038 |

Even Alabama's internally liberal Democratic third is relatively conservative within the national Democratic distribution:

| alabama_democratic_third | candidate_cycles | mean_absolute_np | median_absolute_np | mean_national_democratic_percentile |
|---|---|---|---|---|
| liberal | 70.000 | -0.551 | -0.504 | 65.991 |
| middle | 69.000 | -0.136 | -0.130 | 88.065 |
| conservative | 70.000 | 0.163 | 0.117 | 95.557 |

## Is incumbency different by party?

| outcome | specification | term | coefficient | cluster_se | ci_low | ci_high | p_value |
|---|---|---|---|---|---|---|---|
| candidate_cmo | party_specific_incumbency | incumbent_i | 8.523 | 2.968 | 2.707 | 14.340 | 0.004 |
| candidate_cmo | party_specific_incumbency | democratic_x_incumbency | -5.278 | 4.170 | -13.452 | 2.896 | 0.207 |
| candidate_cmo | party_specific_incumbency_plus_ideology | incumbent_i | 7.176 | 2.945 | 1.404 | 12.948 | 0.016 |
| candidate_cmo | party_specific_incumbency_plus_ideology | democratic_x_incumbency | -3.869 | 4.085 | -11.876 | 4.138 | 0.345 |
| candidate_cmo | party_specific_plus_ideology_context | incumbent_i | 6.518 | 3.028 | 0.583 | 12.453 | 0.032 |
| candidate_cmo | party_specific_plus_ideology_context | democratic_x_incumbency | -3.689 | 4.029 | -11.585 | 4.208 | 0.361 |
| candidate_statewide_overperformance | party_specific_incumbency | incumbent_i | 10.011 | 2.979 | 4.173 | 15.849 | 0.001 |
| candidate_statewide_overperformance | party_specific_incumbency | democratic_x_incumbency | -5.644 | 4.211 | -13.897 | 2.609 | 0.181 |
| candidate_statewide_overperformance | party_specific_incumbency_plus_ideology | incumbent_i | 8.663 | 2.958 | 2.866 | 14.460 | 0.004 |
| candidate_statewide_overperformance | party_specific_incumbency_plus_ideology | democratic_x_incumbency | -4.209 | 4.118 | -12.282 | 3.863 | 0.308 |
| candidate_statewide_overperformance | party_specific_plus_ideology_context | incumbent_i | 7.944 | 3.044 | 1.977 | 13.911 | 0.010 |
| candidate_statewide_overperformance | party_specific_plus_ideology_context | democratic_x_incumbency | -4.002 | 4.057 | -11.954 | 3.949 | 0.325 |
| candidate_federal_overperformance | party_specific_incumbency | incumbent_i | 15.782 | 4.905 | 6.168 | 25.395 | 0.001 |
| candidate_federal_overperformance | party_specific_incumbency | democratic_x_incumbency | -19.028 | 6.305 | -31.386 | -6.669 | 0.003 |
| candidate_federal_overperformance | party_specific_incumbency_plus_ideology | incumbent_i | 14.841 | 4.945 | 5.148 | 24.533 | 0.003 |
| candidate_federal_overperformance | party_specific_incumbency_plus_ideology | democratic_x_incumbency | -17.855 | 6.268 | -30.141 | -5.570 | 0.005 |
| candidate_federal_overperformance | party_specific_plus_ideology_context | incumbent_i | 13.774 | 5.002 | 3.969 | 23.578 | 0.006 |
| candidate_federal_overperformance | party_specific_plus_ideology_context | democratic_x_incumbency | -17.097 | 6.325 | -29.495 | -4.699 | 0.007 |
| candidate_presidential_overperformance | party_specific_incumbency | incumbent_i | 18.759 | 4.157 | 10.611 | 26.907 | 0.000 |
| candidate_presidential_overperformance | party_specific_incumbency | democratic_x_incumbency | -12.338 | 5.470 | -23.060 | -1.616 | 0.025 |
| candidate_presidential_overperformance | party_specific_incumbency_plus_ideology | incumbent_i | 18.029 | 4.222 | 9.755 | 26.303 | 0.000 |
| candidate_presidential_overperformance | party_specific_incumbency_plus_ideology | democratic_x_incumbency | -11.558 | 5.492 | -22.323 | -0.793 | 0.036 |
| candidate_presidential_overperformance | party_specific_plus_ideology_context | incumbent_i | 16.839 | 4.243 | 8.524 | 25.155 | 0.000 |
| candidate_presidential_overperformance | party_specific_plus_ideology_context | democratic_x_incumbency | -10.595 | 5.427 | -21.233 | 0.042 | 0.052 |

The fully contextualized party-specific incumbency contrasts are:

| outcome | contrast | coefficient | cluster_se | ci_low | ci_high | p_value |
|---|---|---|---|---|---|---|
| candidate_cmo | Republican incumbency | 6.518 | 3.028 | 0.583 | 12.453 | 0.031 |
| candidate_cmo | Democratic incumbency | 2.829 | 3.257 | -3.554 | 9.212 | 0.385 |
| candidate_cmo | Democratic-minus-Republican incumbency | -3.689 | 4.029 | -11.585 | 4.208 | 0.360 |
| candidate_statewide_overperformance | Republican incumbency | 7.944 | 3.044 | 1.977 | 13.911 | 0.009 |
| candidate_statewide_overperformance | Democratic incumbency | 3.941 | 3.304 | -2.534 | 10.416 | 0.233 |
| candidate_statewide_overperformance | Democratic-minus-Republican incumbency | -4.002 | 4.057 | -11.954 | 3.949 | 0.324 |
| candidate_federal_overperformance | Republican incumbency | 13.774 | 5.002 | 3.969 | 23.578 | 0.006 |
| candidate_federal_overperformance | Democratic incumbency | -3.323 | 5.114 | -13.346 | 6.699 | 0.516 |
| candidate_federal_overperformance | Democratic-minus-Republican incumbency | -17.097 | 6.325 | -29.495 | -4.699 | 0.007 |
| candidate_presidential_overperformance | Republican incumbency | 16.839 | 4.243 | 8.524 | 25.155 | 0.000 |
| candidate_presidential_overperformance | Democratic incumbency | 6.244 | 4.119 | -1.829 | 14.316 | 0.130 |
| candidate_presidential_overperformance | Democratic-minus-Republican incumbency | -10.595 | 5.427 | -21.233 | 0.042 | 0.051 |

For each outcome, `incumbent_i` is the Republican incumbency estimate and `democratic_x_incumbency` is the additional Democratic effect. Failure to reject the interaction is not proof of equality, but it tests whether the one-sided pattern is statistically required by this selected Shor sample.

## Common incumbency plus absolute ideology

| outcome | contrast | coefficient | cluster_se | ci_low | ci_high | p_value |
|---|---|---|---|---|---|---|
| candidate_cmo | Republican absolute-ideology slope | -4.168 | 6.172 | -16.265 | 7.928 | 0.499 |
| candidate_cmo | Democratic absolute-ideology slope | 15.512 | 2.981 | 9.669 | 21.354 | 0.000 |
| candidate_cmo | Democratic-minus-Republican ideology slope | 19.680 | 6.992 | 5.975 | 33.385 | 0.005 |
| candidate_statewide_overperformance | Republican absolute-ideology slope | -3.882 | 6.256 | -16.143 | 8.379 | 0.535 |
| candidate_statewide_overperformance | Democratic absolute-ideology slope | 15.530 | 3.036 | 9.579 | 21.480 | 0.000 |
| candidate_statewide_overperformance | Democratic-minus-Republican ideology slope | 19.412 | 7.093 | 5.509 | 33.315 | 0.006 |
| candidate_federal_overperformance | Republican absolute-ideology slope | 0.988 | 7.745 | -14.193 | 16.169 | 0.899 |
| candidate_federal_overperformance | Democratic absolute-ideology slope | 14.112 | 5.903 | 2.542 | 25.682 | 0.017 |
| candidate_federal_overperformance | Democratic-minus-Republican ideology slope | 13.124 | 10.231 | -6.928 | 33.177 | 0.200 |
| candidate_presidential_overperformance | Republican absolute-ideology slope | -0.175 | 10.690 | -21.128 | 20.778 | 0.987 |
| candidate_presidential_overperformance | Democratic absolute-ideology slope | 12.546 | 4.842 | 3.056 | 22.037 | 0.010 |
| candidate_presidential_overperformance | Democratic-minus-Republican ideology slope | 12.721 | 11.917 | -10.635 | 36.078 | 0.286 |

## Cross-party moderation

Higher moderation means a Democrat moves right or a Republican moves left on the same absolute scale.

| outcome | specification | contrast | coefficient | cluster_se | ci_low | ci_high | p_value |
|---|---|---|---|---|---|---|---|
| candidate_cmo | common_cross_party_moderation | Republican movement toward center | 11.963 | 2.815 | 6.445 | 17.481 | 0.000 |
| candidate_cmo | common_cross_party_moderation | Democratic movement toward center | 11.963 | 2.815 | 6.445 | 17.481 | 0.000 |
| candidate_cmo | party_specific_cross_party_moderation | Republican movement toward center | 4.168 | 6.172 | -7.928 | 16.265 | 0.499 |
| candidate_cmo | party_specific_cross_party_moderation | Democratic movement toward center | 15.512 | 2.981 | 9.669 | 21.354 | 0.000 |
| candidate_cmo | party_specific_cross_party_moderation | Democratic-minus-Republican moderation slope | 11.343 | 6.713 | -1.814 | 24.500 | 0.091 |
| candidate_cmo | party_specific_moderation_plus_finance | Republican movement toward center | 2.483 | 5.553 | -8.400 | 13.366 | 0.655 |
| candidate_cmo | party_specific_moderation_plus_finance | Democratic movement toward center | 15.543 | 3.187 | 9.296 | 21.790 | 0.000 |
| candidate_cmo | party_specific_moderation_plus_finance | Democratic-minus-Republican moderation slope | 13.061 | 6.351 | 0.612 | 25.509 | 0.040 |
| candidate_statewide_overperformance | common_cross_party_moderation | Republican movement toward center | 11.886 | 2.860 | 6.281 | 17.491 | 0.000 |
| candidate_statewide_overperformance | common_cross_party_moderation | Democratic movement toward center | 11.886 | 2.860 | 6.281 | 17.491 | 0.000 |
| candidate_statewide_overperformance | party_specific_cross_party_moderation | Republican movement toward center | 3.882 | 6.256 | -8.379 | 16.143 | 0.535 |
| candidate_statewide_overperformance | party_specific_cross_party_moderation | Democratic movement toward center | 15.530 | 3.036 | 9.579 | 21.480 | 0.000 |
| candidate_statewide_overperformance | party_specific_cross_party_moderation | Democratic-minus-Republican moderation slope | 11.648 | 6.811 | -1.701 | 24.997 | 0.087 |
| candidate_statewide_overperformance | party_specific_moderation_plus_finance | Republican movement toward center | 2.461 | 5.615 | -8.545 | 13.467 | 0.661 |
| candidate_statewide_overperformance | party_specific_moderation_plus_finance | Democratic movement toward center | 15.631 | 3.233 | 9.295 | 21.968 | 0.000 |
| candidate_statewide_overperformance | party_specific_moderation_plus_finance | Democratic-minus-Republican moderation slope | 13.170 | 6.437 | 0.553 | 25.787 | 0.041 |
| candidate_federal_overperformance | common_cross_party_moderation | Republican movement toward center | 9.511 | 4.966 | -0.222 | 19.245 | 0.055 |
| candidate_federal_overperformance | common_cross_party_moderation | Democratic movement toward center | 9.511 | 4.966 | -0.222 | 19.245 | 0.055 |
| candidate_federal_overperformance | party_specific_cross_party_moderation | Republican movement toward center | -0.988 | 7.745 | -16.169 | 14.193 | 0.899 |
| candidate_federal_overperformance | party_specific_cross_party_moderation | Democratic movement toward center | 14.112 | 5.903 | 2.542 | 25.682 | 0.017 |
| candidate_federal_overperformance | party_specific_cross_party_moderation | Democratic-minus-Republican moderation slope | 15.100 | 9.220 | -2.971 | 33.171 | 0.101 |
| candidate_federal_overperformance | party_specific_moderation_plus_finance | Republican movement toward center | -7.614 | 6.845 | -21.031 | 5.802 | 0.266 |
| candidate_federal_overperformance | party_specific_moderation_plus_finance | Democratic movement toward center | 17.049 | 6.123 | 5.047 | 29.051 | 0.005 |
| candidate_federal_overperformance | party_specific_moderation_plus_finance | Democratic-minus-Republican moderation slope | 24.664 | 8.389 | 8.221 | 41.106 | 0.003 |
| candidate_presidential_overperformance | common_cross_party_moderation | Republican movement toward center | 8.595 | 4.715 | -0.647 | 17.837 | 0.068 |
| candidate_presidential_overperformance | common_cross_party_moderation | Democratic movement toward center | 8.595 | 4.715 | -0.647 | 17.837 | 0.068 |
| candidate_presidential_overperformance | party_specific_cross_party_moderation | Republican movement toward center | 0.175 | 10.690 | -20.778 | 21.128 | 0.987 |
| candidate_presidential_overperformance | party_specific_cross_party_moderation | Democratic movement toward center | 12.546 | 4.842 | 3.056 | 22.037 | 0.010 |
| candidate_presidential_overperformance | party_specific_cross_party_moderation | Democratic-minus-Republican moderation slope | 12.371 | 11.552 | -10.271 | 35.014 | 0.284 |
| candidate_presidential_overperformance | party_specific_moderation_plus_finance | Republican movement toward center | -1.735 | 8.688 | -18.764 | 15.294 | 0.842 |
| candidate_presidential_overperformance | party_specific_moderation_plus_finance | Democratic movement toward center | 8.579 | 5.326 | -1.859 | 19.017 | 0.107 |
| candidate_presidential_overperformance | party_specific_moderation_plus_finance | Democratic-minus-Republican moderation slope | 10.314 | 9.997 | -9.280 | 29.909 | 0.302 |

## Proximity to the absolute midpoint

| outcome | specification | contrast | coefficient | cluster_se | ci_low | ci_high | p_value |
|---|---|---|---|---|---|---|---|
| candidate_cmo | common_center_proximity | Republican center proximity | 8.468 | 3.683 | 1.250 | 15.687 | 0.021 |
| candidate_cmo | common_center_proximity | Democratic center proximity | 8.468 | 3.683 | 1.250 | 15.687 | 0.021 |
| candidate_cmo | party_specific_center_proximity | Republican center proximity | 3.931 | 6.200 | -8.221 | 16.083 | 0.526 |
| candidate_cmo | party_specific_center_proximity | Democratic center proximity | 12.330 | 4.229 | 4.042 | 20.618 | 0.004 |
| candidate_statewide_overperformance | common_center_proximity | Republican center proximity | 8.213 | 3.743 | 0.876 | 15.550 | 0.028 |
| candidate_statewide_overperformance | common_center_proximity | Democratic center proximity | 8.213 | 3.743 | 0.876 | 15.550 | 0.028 |
| candidate_statewide_overperformance | party_specific_center_proximity | Republican center proximity | 3.624 | 6.288 | -8.702 | 15.949 | 0.564 |
| candidate_statewide_overperformance | party_specific_center_proximity | Democratic center proximity | 12.119 | 4.300 | 3.691 | 20.546 | 0.005 |
| candidate_federal_overperformance | common_center_proximity | Republican center proximity | -0.373 | 5.343 | -10.846 | 10.100 | 0.944 |
| candidate_federal_overperformance | common_center_proximity | Democratic center proximity | -0.373 | 5.343 | -10.846 | 10.100 | 0.944 |
| candidate_federal_overperformance | party_specific_center_proximity | Republican center proximity | -2.068 | 7.782 | -17.320 | 13.184 | 0.790 |
| candidate_federal_overperformance | party_specific_center_proximity | Democratic center proximity | 1.014 | 6.612 | -11.944 | 13.973 | 0.878 |
| candidate_presidential_overperformance | common_center_proximity | Republican center proximity | 2.376 | 6.214 | -9.804 | 14.555 | 0.702 |
| candidate_presidential_overperformance | common_center_proximity | Democratic center proximity | 2.376 | 6.214 | -9.804 | 14.555 | 0.702 |
| candidate_presidential_overperformance | party_specific_center_proximity | Republican center proximity | -0.500 | 10.775 | -21.620 | 20.619 | 0.963 |
| candidate_presidential_overperformance | party_specific_center_proximity | Democratic center proximity | 4.971 | 6.032 | -6.853 | 16.795 | 0.410 |

## Does moderation matter more in electorally hostile districts?

| sample | outcome | term | coefficient | cluster_se | ci_low | ci_high | p_value |
|---|---|---|---|---|---|---|---|
| D | candidate_cmo | cross_party_moderation | 10.368 | 4.155 | 2.224 | 18.511 | 0.014 |
| D | candidate_cmo | moderation_x_hostility | 0.618 | 3.592 | -6.422 | 7.659 | 0.864 |
| D | candidate_statewide_overperformance | cross_party_moderation | 10.303 | 4.205 | 2.061 | 18.546 | 0.016 |
| D | candidate_statewide_overperformance | moderation_x_hostility | 0.698 | 3.641 | -6.439 | 7.834 | 0.848 |
| D | candidate_federal_overperformance | cross_party_moderation | 4.978 | 3.332 | -1.553 | 11.509 | 0.138 |
| D | candidate_federal_overperformance | moderation_x_hostility | 1.844 | 3.887 | -5.775 | 9.463 | 0.636 |
| D | candidate_presidential_overperformance | cross_party_moderation | 6.025 | 5.161 | -4.091 | 16.141 | 0.246 |
| D | candidate_presidential_overperformance | moderation_x_hostility | 3.299 | 4.306 | -5.142 | 11.739 | 0.445 |
| R | candidate_cmo | cross_party_moderation | -5.384 | 8.314 | -21.679 | 10.911 | 0.519 |
| R | candidate_cmo | moderation_x_hostility | -13.043 | 6.959 | -26.684 | 0.598 | 0.063 |
| R | candidate_statewide_overperformance | cross_party_moderation | -5.343 | 8.372 | -21.753 | 11.067 | 0.525 |
| R | candidate_statewide_overperformance | moderation_x_hostility | -12.986 | 7.040 | -26.784 | 0.813 | 0.068 |
| R | candidate_federal_overperformance | cross_party_moderation | -12.665 | 11.530 | -35.263 | 9.934 | 0.274 |
| R | candidate_federal_overperformance | moderation_x_hostility | -17.663 | 10.587 | -38.413 | 3.087 | 0.098 |
| R | candidate_presidential_overperformance | cross_party_moderation | -6.547 | 11.869 | -29.811 | 16.716 | 0.582 |
| R | candidate_presidential_overperformance | moderation_x_hostility | -18.832 | 10.176 | -38.777 | 1.113 | 0.067 |

The hostility interactions do not support the proposed mechanism that moderation becomes more valuable as the candidate's federal baseline becomes harder. For Democrats the interaction estimates are small and imprecise. For Republicans they point in the opposite direction and remain marginal rather than conclusive. This does not negate a crossover mechanism; it means this selected legislator sample cannot locate it through this district-hostility interaction.

## Republican-calibrated incumbency

| outcome | republican_incumbency_coefficient | democratic_ideology_after_common_incumbency | cluster_se | p_value | democratic_n | republican_n |
|---|---|---|---|---|---|---|
| candidate_cmo | 4.519 | 13.076 | 2.890 | 0.000 | 209.000 | 198.000 |
| candidate_statewide_overperformance | 5.594 | 13.080 | 2.931 | 0.000 | 209.000 | 198.000 |
| candidate_federal_overperformance | 10.691 | 18.928 | 5.355 | 0.001 | 187.000 | 173.000 |
| candidate_presidential_overperformance | 9.116 | 10.981 | 3.979 | 0.007 | 199.000 | 190.000 |

## Interpretation

Absolute ideology materially changes the conclusion. Moving right on the national scale is strongly associated with Democratic overperformance on corrected CMO, statewide-ticket, federal, and presidential outcomes. The analogous estimate for Republicans moving left is not distinguishable from zero. A pooled cross-party moderation coefficient therefore should not be described as a symmetric finding: it is primarily a Democratic result. The Democratic relationship survives imposing the Republican incumbency coefficient, which is consistent with ideology contributing to the durable advantage that helped conservative Democrats become and remain incumbents rather than incumbency explaining the whole pattern.

## Limits

- Shor–McCarty coverage is conditional on legislative service and therefore strongly selects incumbents and winners.
- The absolute score is nationally bridged but career-level; it is not a contemporaneous campaign-position measure.
- A common incumbency coefficient is a transparent identifying assumption, not an established fact.
- Finance and incumbency are possible mediators of ideological fit, so controlled estimates answer a narrower question than total overperformance.
