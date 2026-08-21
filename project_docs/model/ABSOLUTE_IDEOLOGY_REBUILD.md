# Absolute ideology rebuild

## Estimand

The outcome is always ideology-blind: actual candidate margin minus an expected statewide, federal, presidential, or cross-fitted CMO baseline. Positive values mean that the candidate of either party ran ahead. Ideology is analyzed afterward and is never included in the construction of expected performance.

`total_context` controls for district demographics, cycle, and chamber but deliberately omits incumbency and finance. `mediator_adjusted` adds those variables and therefore estimates a narrower direct association rather than the total electoral pathway.

## Current reading

- Absolute Shor–McCarty position produces a clear asymmetric result. More conservative Democrats run substantially ahead of every baseline. The Republican point estimates generally favor less conservative candidates, but they are too imprecise to establish a Republican moderation effect.
- Among winners only, less conservative Republicans do have a significant corrected-CMO advantage, consistent with the proposed crossover story, but that result does not carry through to federal-relative performance or the prior-service-only sample. It is suggestive rather than a symmetric counterpart to the Democratic result.
- A common incumbency effect is compatible with corrected CMO and statewide-ticket performance: the party-specific Democratic-minus-Republican increment is not distinguishable from zero. Federal-relative performance is different, with a larger Republican incumbency association in this selected sample. Consequently the common-incumbency result is a sensitivity analysis, not a universal fact.
- Adding incumbency and finance does not remove the Democratic Shor relationship for CMO or federal-relative performance. Presidential-relative performance attenuates, partly because finance-complete cases are a smaller selected subset.
- Primitive issue measures recover the substantive coalition more clearly than broad families. Democratic overperformance is associated with market autonomy, gun access, restrictive civil-social positions, and religion-state accommodation, while welfare generosity remains favorable in the opposite economic direction. This is closer to a culturally conservative, economically mixed or populist bundle than to one universal left-right axis.
- The tax-burden signal remains unsuitable for interpretation as generic fiscal conservatism. It does not identify who bears a tax, and its direction conflicts with a simple low-tax story. Tax burden and tax distribution must remain separate.
- District-congruence findings are exploratory. Several nominal interactions appear, but coverage and multiple comparisons are limiting; they should guide case research rather than enter a forecast.

## Coverage

| measure | party | candidate_cycles | people | cycles |
|---|---|---|---|---|
| shor_absolute | D | 209.000 | 179.000 | 1998,2002,2006,2010,2014,2018 |
| environment_resources | D | 20.000 | 20.000 | 2002,2010,2014,2018 |
| institutional_reform | D | 4.000 | 4.000 | 2014,2018 |
| labor_capital | D | 17.000 | 17.000 | 2018,2022 |
| market_government_direction | D | 9.000 | 9.000 | 2006,2010 |
| material_support | D | 70.000 | 69.000 | 1998,2002,2006,2010,2014,2018,2022 |
| order_justice | D | 14.000 | 14.000 | 2006,2010 |
| social_liberty_equality | D | 99.000 | 98.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:gun_access | D | 214.000 | 196.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:gun_purchase_regulation | D | 52.000 | 50.000 | 2002,2006,2010,2014,2018,2022 |
| primitive:abortion_access | D | 70.000 | 67.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:marriage_equality | D | 56.000 | 56.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:civil_social_liberty | D | 87.000 | 84.000 | 1998,2002,2006,2010,2018,2022 |
| primitive:christian_sexual_morality | D | 2.000 | 2.000 | 2018 |
| primitive:racial_civil_rights | D | 13.000 | 13.000 | 2002,2006,2018 |
| primitive:anti_discrimination | D | 74.000 | 74.000 | 1994,1998,2002,2006,2010,2014,2018,2022 |
| primitive:religion_state | D | 77.000 | 76.000 | 1998,2002,2006,2014,2018,2022 |
| primitive:criminal_punishment | D | 127.000 | 115.000 | 1994,1998,2002,2006,2010,2014,2018 |
| primitive:drug_criminalization | D | 17.000 | 17.000 | 2006,2010,2014,2022 |
| primitive:due_process | D | 0.000 | 0.000 |  |
| primitive:market_governance | D | 133.000 | 126.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:tax_burden | D | 75.000 | 74.000 | 1994,1998,2002,2006,2010,2014,2018,2022 |
| primitive:tax_distribution | D | 14.000 | 14.000 | 1994,2010,2014,2018,2022 |
| primitive:public_spending | D | 32.000 | 32.000 | 1998,2006,2014,2018 |
| primitive:deficit_discipline | D | 24.000 | 24.000 | 1998,2006 |
| primitive:welfare_generosity | D | 52.000 | 52.000 | 1994,1998,2002,2006,2010,2014,2022 |
| primitive:welfare_conditionality | D | 63.000 | 63.000 | 1998,2002,2006,2018 |
| primitive:labor_capital_alignment | D | 82.000 | 82.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:labor_rights | D | 52.000 | 52.000 | 2018,2022 |
| primitive:public_employee_compensation | D | 103.000 | 97.000 | 1998,2002,2006,2010,2014,2018 |
| primitive:education_public_funding | D | 131.000 | 123.000 | 1994,1998,2002,2006,2010,2014,2018,2022 |
| primitive:education_market_choice | D | 71.000 | 70.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:environmental_protection | D | 63.000 | 63.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:resource_development | D | 17.000 | 17.000 | 2006,2010,2014 |
| primitive:conservation_preservation | D | 22.000 | 22.000 | 2002,2010,2014,2018 |
| primitive:immigration_access | D | 26.000 | 26.000 | 2006,2010,2014,2018,2022 |
| primitive:immigration_enforcement | D | 12.000 | 11.000 | 2010,2014,2022 |
| primitive:healthcare_access | D | 155.000 | 147.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:government_ethics_transparency | D | 50.000 | 43.000 | 1994,2006,2010,2014,2018,2022 |
| primitive:voting_access | D | 63.000 | 63.000 | 1998,2002,2006,2010,2014,2018,2022 |
| shor_absolute | R | 198.000 | 154.000 | 1998,2002,2006,2010,2014,2018 |
| environment_resources | R | 22.000 | 22.000 | 2002,2010,2014 |
| institutional_reform | R | 2.000 | 2.000 | 2014,2018 |
| labor_capital | R | 0.000 | 0.000 |  |
| market_government_direction | R | 9.000 | 9.000 | 2010 |
| material_support | R | 92.000 | 91.000 | 1998,2002,2006,2010,2014,2018 |
| order_justice | R | 12.000 | 12.000 | 2006,2010,2014 |
| social_liberty_equality | R | 137.000 | 135.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:gun_access | R | 248.000 | 216.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:gun_purchase_regulation | R | 64.000 | 59.000 | 2002,2006,2010,2014,2018,2022 |
| primitive:abortion_access | R | 102.000 | 96.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:marriage_equality | R | 92.000 | 91.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:civil_social_liberty | R | 81.000 | 79.000 | 1998,2002,2006,2010,2018,2022 |
| primitive:christian_sexual_morality | R | 22.000 | 22.000 | 2018 |
| primitive:racial_civil_rights | R | 34.000 | 34.000 | 2002,2006,2018 |
| primitive:anti_discrimination | R | 90.000 | 89.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:religion_state | R | 93.000 | 93.000 | 1998,2002,2006,2010,2014,2018 |
| primitive:criminal_punishment | R | 152.000 | 140.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:drug_criminalization | R | 17.000 | 17.000 | 2006,2010,2014,2018,2022 |
| primitive:due_process | R | 9.000 | 8.000 | 2014,2018 |
| primitive:market_governance | R | 160.000 | 143.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:tax_burden | R | 72.000 | 69.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:tax_distribution | R | 1.000 | 1.000 | 2022 |
| primitive:public_spending | R | 59.000 | 58.000 | 1998,2010,2014,2018,2022 |
| primitive:deficit_discipline | R | 43.000 | 41.000 | 1994,1998,2010,2014,2018,2022 |
| primitive:welfare_generosity | R | 72.000 | 72.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:welfare_conditionality | R | 74.000 | 73.000 | 1998,2002,2006,2010,2014,2018 |
| primitive:labor_capital_alignment | R | 53.000 | 53.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:labor_rights | R | 6.000 | 6.000 | 2014,2018 |
| primitive:public_employee_compensation | R | 87.000 | 74.000 | 1998,2002,2006,2010,2014,2018 |
| primitive:education_public_funding | R | 132.000 | 122.000 | 1994,1998,2002,2006,2010,2014,2018,2022 |
| primitive:education_market_choice | R | 103.000 | 93.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:environmental_protection | R | 64.000 | 63.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:resource_development | R | 39.000 | 39.000 | 2006,2010,2014,2018,2022 |
| primitive:conservation_preservation | R | 21.000 | 21.000 | 2002,2010,2014 |
| primitive:immigration_access | R | 11.000 | 11.000 | 2010,2014,2018 |
| primitive:immigration_enforcement | R | 21.000 | 21.000 | 2010,2014,2022 |
| primitive:healthcare_access | R | 121.000 | 112.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:government_ethics_transparency | R | 65.000 | 51.000 | 2002,2006,2010,2014,2018 |
| primitive:voting_access | R | 77.000 | 76.000 | 1998,2002,2010,2014,2018,2022 |

## Absolute-scale overlap

| party | candidate_cycles | people | mean | sd | minimum | p10 | median | p90 | maximum | common_support_low | common_support_high | inside_common_support |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D | 209.000 | 179.000 | -0.216 | 0.383 | -1.500 | -0.700 | -0.166 | 0.214 | 0.619 | 0.155 | 0.619 | 25.000 |
| R | 198.000 | 154.000 | 1.002 | 0.239 | 0.155 | 0.725 | 1.038 | 1.274 | 1.805 | 0.155 | 0.619 | 12.000 |

The parties have limited common support on the absolute scale. Republican moderation estimates therefore rely on a narrow tail of the Republican distribution and should not be treated as a mirror-image test with equal power.

## Selection into Shor–McCarty coverage

| party | shor_observed | candidate_cycles | people | winner_share | incumbent_share | mean_cmo | mean_federal_overperformance |
|---|---|---|---|---|---|---|---|
| D | False | 300.000 | 283.000 | 0.213 | 0.017 | -7.686 | 7.364 |
| D | True | 209.000 | 179.000 | 0.837 | 0.220 | 9.959 | 34.975 |
| R | False | 311.000 | 302.000 | 0.273 | 0.013 | -5.733 | -24.860 |
| R | True | 198.000 | 154.000 | 0.934 | 0.364 | 10.139 | -9.296 |

Shor coverage is a selected officeholder sample. Differences between observed and unobserved candidates quantify why these estimates describe successful legislative candidates rather than all people who ran.

### Selection sensitivities

| sample | outcome | specification | n | people | coefficient | cluster_se | p_value | status |
|---|---|---|---|---|---|---|---|---|
| D | candidate_cmo | party_winners_only | 175.000 | 160.000 | 13.378 | 2.946 | 0.000 | estimated |
| D | candidate_cmo | party_prior_service_only | 177.000 | 152.000 | 15.807 | 2.958 | 0.000 | estimated |
| R | candidate_cmo | party_winners_only | 185.000 | 145.000 | -8.831 | 5.844 | 0.133 | estimated |
| R | candidate_cmo | party_prior_service_only | 136.000 | 110.000 | -4.994 | 7.206 | 0.490 | estimated |
| D | candidate_federal_overperformance | party_winners_only | 159.000 | 148.000 | 17.423 | 5.688 | 0.003 | estimated |
| D | candidate_federal_overperformance | party_prior_service_only | 157.000 | 145.000 | 17.975 | 5.646 | 0.002 | estimated |
| R | candidate_federal_overperformance | party_winners_only | 160.000 | 136.000 | -3.797 | 7.993 | 0.636 | estimated |
| R | candidate_federal_overperformance | party_prior_service_only | 119.000 | 103.000 | -1.701 | 9.307 | 0.855 | estimated |

## Absolute Shor–McCarty results

| sample | outcome | n | people | coefficient | cluster_se | ci_low | ci_high | p_value | status |
|---|---|---|---|---|---|---|---|---|---|
| D | candidate_cmo | 209.000 | 179.000 | 14.593 | 2.860 | 8.988 | 20.199 | 0.000 | estimated |
| R | candidate_cmo | 198.000 | 154.000 | -7.316 | 5.959 | -18.996 | 4.365 | 0.221 | estimated |
| D | candidate_federal_overperformance | 187.000 | 171.000 | 18.768 | 5.245 | 8.488 | 29.047 | 0.000 | estimated |
| R | candidate_federal_overperformance | 173.000 | 146.000 | -5.310 | 7.424 | -19.861 | 9.241 | 0.476 | estimated |
| D | candidate_presidential_overperformance | 199.000 | 170.000 | 10.746 | 3.565 | 3.759 | 17.733 | 0.003 | estimated |
| R | candidate_presidential_overperformance | 190.000 | 149.000 | -12.203 | 8.795 | -29.441 | 5.035 | 0.167 | estimated |

Positive coefficients mean moving right helps; negative coefficients mean moving left helps. The Democratic coefficients are positive across all primary outcomes. Republican coefficients generally point toward an advantage for moving left but remain imprecise.

## Symmetric-incumbency sensitivity

| outcome | specification | term | n | coefficient | cluster_se | p_value | status |
|---|---|---|---|---|---|---|---|
| candidate_cmo | common_incumbency | incumbent_i | 407.000 | 5.695 | 2.244 | 0.012 | estimated |
| candidate_cmo | party_specific_incumbency | incumbent_i | 407.000 | 6.744 | 2.853 | 0.019 | estimated |
| candidate_cmo | party_specific_incumbency | democratic_x_incumbency | 407.000 | -2.327 | 3.829 | 0.544 | estimated |
| candidate_statewide_overperformance | common_incumbency | incumbent_i | 407.000 | 6.138 | 2.424 | 0.012 | estimated |
| candidate_statewide_overperformance | party_specific_incumbency | incumbent_i | 407.000 | 7.944 | 3.073 | 0.010 | estimated |
| candidate_statewide_overperformance | party_specific_incumbency | democratic_x_incumbency | 407.000 | -4.002 | 3.986 | 0.316 | estimated |
| candidate_federal_overperformance | common_incumbency | incumbent_i | 360.000 | 5.720 | 3.959 | 0.149 | estimated |
| candidate_federal_overperformance | party_specific_incumbency | incumbent_i | 360.000 | 13.774 | 5.049 | 0.007 | estimated |
| candidate_federal_overperformance | party_specific_incumbency | democratic_x_incumbency | 360.000 | -17.097 | 6.147 | 0.006 | estimated |
| candidate_presidential_overperformance | common_incumbency | incumbent_i | 389.000 | 12.076 | 3.136 | 0.000 | estimated |
| candidate_presidential_overperformance | party_specific_incumbency | incumbent_i | 389.000 | 16.839 | 4.266 | 0.000 | estimated |
| candidate_presidential_overperformance | party_specific_incumbency | democratic_x_incumbency | 389.000 | -10.595 | 5.390 | 0.050 | estimated |

## Total association versus mediator adjustment

| sample | outcome | specification | n | coefficient | cluster_se | p_value | status |
|---|---|---|---|---|---|---|---|
| D | candidate_cmo | party_total_context | 209.000 | 14.593 | 2.860 | 0.000 | estimated |
| D | candidate_cmo | party_mediator_adjusted | 158.000 | 13.652 | 3.222 | 0.000 | estimated |
| R | candidate_cmo | party_total_context | 198.000 | -7.316 | 5.959 | 0.221 | estimated |
| R | candidate_cmo | party_mediator_adjusted | 169.000 | -0.297 | 5.467 | 0.957 | estimated |
| D | candidate_federal_overperformance | party_total_context | 187.000 | 18.768 | 5.245 | 0.000 | estimated |
| D | candidate_federal_overperformance | party_mediator_adjusted | 139.000 | 21.450 | 5.954 | 0.000 | estimated |
| R | candidate_federal_overperformance | party_total_context | 173.000 | -5.310 | 7.424 | 0.476 | estimated |
| R | candidate_federal_overperformance | party_mediator_adjusted | 145.000 | 1.767 | 7.227 | 0.807 | estimated |

## Issue-position results

Positive coefficients mean that a more conservative absolute position is associated with greater candidate-directional overperformance. These estimates use only temporally eligible ideology-v3 evidence.

| sample | outcome | specification | n | people | coefficient | cluster_se | p_value | primary_bh_q_value | status |
|---|---|---|---|---|---|---|---|---|---|
| D | candidate_federal_overperformance | issue_total:primitive:gun_access | 194.000 | 185.000 | 7.182 | 3.636 | 0.050 | 0.130 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:gun_access | 204.000 | 187.000 | 9.896 | 2.336 | 0.000 | 0.001 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:gun_access | 226.000 | 206.000 | -0.304 | 2.069 | 0.883 | 0.892 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:gun_access | 243.000 | 212.000 | 4.976 | 2.241 | 0.027 | 0.140 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:gun_purchase_regulation | 45.000 | 44.000 | 5.597 | 5.727 | 0.334 | 0.588 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:gun_purchase_regulation | 48.000 | 46.000 | 1.293 | 4.306 | 0.765 | 0.898 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:gun_purchase_regulation | 49.000 | 48.000 | -8.615 | 4.219 | 0.047 | 0.166 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:gun_purchase_regulation | 62.000 | 57.000 | -8.952 | 6.078 | 0.146 | 0.303 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:abortion_access | 58.000 | 56.000 | 8.575 | 4.083 | 0.040 | 0.127 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:abortion_access | 65.000 | 62.000 | 10.223 | 5.001 | 0.045 | 0.130 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:abortion_access | 88.000 | 85.000 | 7.759 | 5.032 | 0.127 | 0.279 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:abortion_access | 98.000 | 93.000 | 10.994 | 5.958 | 0.068 | 0.200 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:marriage_equality | 53.000 | 53.000 | 7.928 | 5.894 | 0.184 | 0.369 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:marriage_equality | 53.000 | 53.000 | 3.499 | 8.874 | 0.695 | 0.872 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:marriage_equality | 83.000 | 82.000 | -3.384 | 2.630 | 0.202 | 0.353 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:marriage_equality | 91.000 | 90.000 | 8.935 | 2.866 | 0.002 | 0.036 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:civil_social_liberty | 77.000 | 74.000 | 9.696 | 2.799 | 0.001 | 0.007 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:civil_social_liberty | 82.000 | 79.000 | 10.771 | 2.589 | 0.000 | 0.001 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:civil_social_liberty | 72.000 | 71.000 | 6.890 | 4.753 | 0.152 | 0.303 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:civil_social_liberty | 80.000 | 78.000 | 7.905 | 4.479 | 0.082 | 0.224 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:christian_sexual_morality | 2.000 | 2.000 |  |  |  |  | underpowered |
| D | candidate_presidential_overperformance | issue_total:primitive:christian_sexual_morality | 2.000 | 2.000 |  |  |  |  | underpowered |
| R | candidate_federal_overperformance | issue_total:primitive:christian_sexual_morality | 22.000 | 22.000 |  |  |  |  | no_variation |
| R | candidate_presidential_overperformance | issue_total:primitive:christian_sexual_morality | 22.000 | 22.000 |  |  |  |  | no_variation |
| D | candidate_federal_overperformance | issue_total:primitive:racial_civil_rights | 12.000 | 12.000 |  |  |  |  | underpowered |
| D | candidate_presidential_overperformance | issue_total:primitive:racial_civil_rights | 12.000 | 12.000 |  |  |  |  | underpowered |
| R | candidate_federal_overperformance | issue_total:primitive:racial_civil_rights | 34.000 | 34.000 |  |  |  |  | no_variation |
| R | candidate_presidential_overperformance | issue_total:primitive:racial_civil_rights | 33.000 | 33.000 |  |  |  |  | no_variation |
| D | candidate_federal_overperformance | issue_total:primitive:anti_discrimination | 70.000 | 70.000 | 3.389 | 4.411 | 0.445 | 0.753 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:anti_discrimination | 71.000 | 71.000 | 1.975 | 3.878 | 0.612 | 0.869 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:anti_discrimination | 81.000 | 80.000 | 3.046 | 2.636 | 0.251 | 0.409 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:anti_discrimination | 89.000 | 88.000 | -1.021 | 5.982 | 0.865 | 0.892 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:religion_state | 69.000 | 68.000 | 5.805 | 1.721 | 0.001 | 0.007 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:religion_state | 74.000 | 73.000 | -2.921 | 2.093 | 0.167 | 0.350 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:religion_state | 80.000 | 80.000 |  |  |  |  | no_variation |
| R | candidate_presidential_overperformance | issue_total:primitive:religion_state | 89.000 | 89.000 |  |  |  |  | no_variation |
| D | candidate_federal_overperformance | issue_total:primitive:criminal_punishment | 117.000 | 109.000 | 6.946 | 4.340 | 0.112 | 0.260 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:criminal_punishment | 122.000 | 110.000 | 1.960 | 6.867 | 0.776 | 0.898 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:criminal_punishment | 135.000 | 129.000 | 19.206 | 12.065 | 0.114 | 0.264 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:criminal_punishment | 148.000 | 136.000 | 20.204 | 12.638 | 0.112 | 0.264 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:drug_criminalization | 15.000 | 15.000 |  |  |  |  | underpowered |
| D | candidate_presidential_overperformance | issue_total:primitive:drug_criminalization | 16.000 | 16.000 |  |  |  |  | underpowered |
| R | candidate_federal_overperformance | issue_total:primitive:drug_criminalization | 14.000 | 14.000 |  |  |  |  | underpowered |
| R | candidate_presidential_overperformance | issue_total:primitive:drug_criminalization | 17.000 | 17.000 |  |  |  |  | underpowered |
| D | candidate_federal_overperformance | issue_total:primitive:due_process | 0.000 | 0.000 |  |  |  |  | underpowered |
| D | candidate_presidential_overperformance | issue_total:primitive:due_process | 0.000 | 0.000 |  |  |  |  | underpowered |
| R | candidate_federal_overperformance | issue_total:primitive:due_process | 7.000 | 6.000 |  |  |  |  | underpowered |
| R | candidate_presidential_overperformance | issue_total:primitive:due_process | 9.000 | 8.000 |  |  |  |  | underpowered |
| D | candidate_federal_overperformance | issue_total:primitive:market_governance | 119.000 | 115.000 | 11.312 | 2.703 | 0.000 | 0.001 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:market_governance | 127.000 | 121.000 | 14.863 | 2.689 | 0.000 | 0.000 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:market_governance | 145.000 | 133.000 | 8.003 | 2.942 | 0.007 | 0.064 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:market_governance | 156.000 | 140.000 | 11.684 | 3.533 | 0.001 | 0.035 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:tax_burden | 69.000 | 68.000 | -12.792 | 5.014 | 0.013 | 0.052 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:tax_burden | 74.000 | 73.000 | -9.919 | 5.046 | 0.053 | 0.130 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:tax_burden | 69.000 | 67.000 | -10.358 | 5.040 | 0.044 | 0.166 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:tax_burden | 70.000 | 67.000 | -15.138 | 5.599 | 0.009 | 0.064 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:tax_distribution | 14.000 | 14.000 |  |  |  |  | underpowered |
| D | candidate_presidential_overperformance | issue_total:primitive:tax_distribution | 14.000 | 14.000 |  |  |  |  | underpowered |
| R | candidate_federal_overperformance | issue_total:primitive:tax_distribution | 1.000 | 1.000 |  |  |  |  | underpowered |
| R | candidate_presidential_overperformance | issue_total:primitive:tax_distribution | 1.000 | 1.000 |  |  |  |  | underpowered |
| D | candidate_federal_overperformance | issue_total:primitive:public_spending | 31.000 | 31.000 |  |  |  |  | no_variation |
| D | candidate_presidential_overperformance | issue_total:primitive:public_spending | 32.000 | 32.000 |  |  |  |  | no_variation |
| R | candidate_federal_overperformance | issue_total:primitive:public_spending | 58.000 | 57.000 | 2.142 | 2.364 | 0.369 | 0.541 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:public_spending | 58.000 | 57.000 | 1.704 | 3.021 | 0.575 | 0.723 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:deficit_discipline | 24.000 | 24.000 | 3.380 | 5.823 | 0.567 | 0.861 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:deficit_discipline | 24.000 | 24.000 | 1.226 | 5.877 | 0.837 | 0.920 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:deficit_discipline | 43.000 | 41.000 | 2.786 | 4.046 | 0.495 | 0.667 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:deficit_discipline | 43.000 | 41.000 | 3.050 | 4.484 | 0.500 | 0.667 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:welfare_generosity | 49.000 | 49.000 | -8.888 | 4.448 | 0.051 | 0.130 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:welfare_generosity | 50.000 | 50.000 | -15.497 | 4.011 | 0.000 | 0.003 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:welfare_generosity | 65.000 | 65.000 | -7.443 | 3.324 | 0.029 | 0.140 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:welfare_generosity | 71.000 | 71.000 | -8.201 | 4.128 | 0.051 | 0.166 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:welfare_conditionality | 60.000 | 60.000 | -2.559 | 4.152 | 0.540 | 0.861 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:welfare_conditionality | 61.000 | 61.000 | -10.690 | 3.114 | 0.001 | 0.007 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:welfare_conditionality | 65.000 | 64.000 |  |  |  |  | no_variation |
| R | candidate_presidential_overperformance | issue_total:primitive:welfare_conditionality | 73.000 | 72.000 |  |  |  |  | no_variation |
| D | candidate_federal_overperformance | issue_total:primitive:labor_capital_alignment | 75.000 | 75.000 | 11.898 | 9.327 | 0.206 | 0.378 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:labor_capital_alignment | 80.000 | 80.000 | 14.656 | 5.430 | 0.009 | 0.037 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:labor_capital_alignment | 50.000 | 50.000 | 2.020 | 4.901 | 0.682 | 0.811 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:labor_capital_alignment | 53.000 | 53.000 | 1.407 | 4.548 | 0.758 | 0.836 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:labor_rights | 52.000 | 52.000 |  |  |  |  | no_variation |
| D | candidate_presidential_overperformance | issue_total:primitive:labor_rights | 52.000 | 52.000 |  |  |  |  | no_variation |
| R | candidate_federal_overperformance | issue_total:primitive:labor_rights | 4.000 | 4.000 |  |  |  |  | underpowered |
| R | candidate_presidential_overperformance | issue_total:primitive:labor_rights | 6.000 | 6.000 |  |  |  |  | underpowered |
| D | candidate_federal_overperformance | issue_total:primitive:public_employee_compensation | 95.000 | 93.000 |  |  |  |  | no_variation |
| D | candidate_presidential_overperformance | issue_total:primitive:public_employee_compensation | 100.000 | 94.000 |  |  |  |  | no_variation |
| R | candidate_federal_overperformance | issue_total:primitive:public_employee_compensation | 73.000 | 69.000 | -9.853 | 4.997 | 0.053 | 0.166 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:public_employee_compensation | 83.000 | 71.000 | -5.849 | 5.414 | 0.284 | 0.446 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:education_public_funding | 119.000 | 114.000 | -14.560 | 6.413 | 0.025 | 0.089 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:education_public_funding | 124.000 | 116.000 | -14.043 | 10.028 | 0.164 | 0.350 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:education_public_funding | 115.000 | 111.000 | 2.150 | 10.232 | 0.834 | 0.892 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:education_public_funding | 131.000 | 121.000 | 1.655 | 12.154 | 0.892 | 0.892 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:education_market_choice | 66.000 | 65.000 | 1.849 | 3.558 | 0.605 | 0.869 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:education_market_choice | 68.000 | 67.000 | 1.497 | 3.309 | 0.653 | 0.872 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:education_market_choice | 88.000 | 84.000 | 3.041 | 4.216 | 0.473 | 0.667 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:education_market_choice | 99.000 | 90.000 | 12.105 | 5.575 | 0.033 | 0.143 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:environmental_protection | 59.000 | 59.000 | 19.099 | 6.998 | 0.008 | 0.037 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:environmental_protection | 59.000 | 59.000 | 16.287 | 7.150 | 0.026 | 0.089 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:environmental_protection | 59.000 | 58.000 | -1.339 | 4.368 | 0.760 | 0.836 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:environmental_protection | 63.000 | 62.000 | -5.405 | 3.858 | 0.166 | 0.318 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:resource_development | 16.000 | 16.000 |  |  |  |  | underpowered |
| D | candidate_presidential_overperformance | issue_total:primitive:resource_development | 16.000 | 16.000 |  |  |  |  | underpowered |
| R | candidate_federal_overperformance | issue_total:primitive:resource_development | 30.000 | 30.000 | 4.179 | 7.851 | 0.599 | 0.732 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:resource_development | 39.000 | 39.000 | -4.504 | 7.345 | 0.543 | 0.703 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:conservation_preservation | 22.000 | 22.000 | 5.931 | 9.903 | 0.556 | 0.861 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:conservation_preservation | 21.000 | 21.000 | -2.206 | 9.168 | 0.812 | 0.916 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:conservation_preservation | 21.000 | 21.000 | -4.130 | 3.953 | 0.309 | 0.468 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:conservation_preservation | 20.000 | 20.000 | 1.438 | 3.890 | 0.716 | 0.829 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:immigration_access | 25.000 | 25.000 | -8.013 | 6.078 | 0.200 | 0.378 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:immigration_access | 25.000 | 25.000 | 0.519 | 6.929 | 0.941 | 0.941 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:immigration_access | 11.000 | 11.000 |  |  |  |  | underpowered |
| R | candidate_presidential_overperformance | issue_total:primitive:immigration_access | 11.000 | 11.000 |  |  |  |  | underpowered |
| D | candidate_federal_overperformance | issue_total:primitive:immigration_enforcement | 8.000 | 7.000 |  |  |  |  | underpowered |
| D | candidate_presidential_overperformance | issue_total:primitive:immigration_enforcement | 10.000 | 9.000 |  |  |  |  | underpowered |
| R | candidate_federal_overperformance | issue_total:primitive:immigration_enforcement | 14.000 | 14.000 |  |  |  |  | underpowered |
| R | candidate_presidential_overperformance | issue_total:primitive:immigration_enforcement | 21.000 | 21.000 |  |  |  |  | no_variation |
| D | candidate_federal_overperformance | issue_total:primitive:healthcare_access | 143.000 | 140.000 | 1.118 | 7.433 | 0.881 | 0.922 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:healthcare_access | 150.000 | 142.000 | -3.484 | 8.908 | 0.696 | 0.872 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:healthcare_access | 107.000 | 102.000 | -8.890 | 3.155 | 0.006 | 0.064 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:healthcare_access | 118.000 | 109.000 | -10.149 | 3.136 | 0.002 | 0.035 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:government_ethics_transparency | 41.000 | 38.000 | 2.342 | 6.231 | 0.709 | 0.872 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:government_ethics_transparency | 48.000 | 41.000 | -1.848 | 4.999 | 0.714 | 0.872 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:government_ethics_transparency | 49.000 | 43.000 | 7.827 | 5.688 | 0.176 | 0.323 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:government_ethics_transparency | 64.000 | 50.000 | 7.021 | 3.084 | 0.027 | 0.140 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:voting_access | 62.000 | 62.000 | 0.362 | 2.887 | 0.901 | 0.922 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:voting_access | 62.000 | 62.000 | -0.479 | 2.931 | 0.871 | 0.922 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:voting_access | 77.000 | 76.000 | -6.838 | 4.234 | 0.110 | 0.264 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:voting_access | 75.000 | 74.000 | -7.712 | 6.079 | 0.209 | 0.353 | estimated |

## District congruence

A positive congruence coefficient means conservative positioning becomes more favorable as the district federal baseline becomes more Republican, and liberal positioning becomes more favorable as it becomes more Democratic.

| sample | specification | n | people | coefficient | cluster_se | p_value | congruence_bh_q_value | status |
|---|---|---|---|---|---|---|---|---|
| D | issue_district_congruence:family:environment_resources | 20.000 | 20.000 | -53.541 | 20.666 | 0.018 |  | estimated |
| R | issue_district_congruence:family:environment_resources | 22.000 | 22.000 | 32.499 | 9.417 | 0.002 |  | estimated |
| D | issue_district_congruence:family:institutional_reform | 4.000 | 4.000 |  |  |  |  | underpowered |
| R | issue_district_congruence:family:institutional_reform | 2.000 | 2.000 |  |  |  |  | underpowered |
| D | issue_district_congruence:family:labor_capital | 17.000 | 17.000 |  |  |  |  | underpowered |
| R | issue_district_congruence:family:labor_capital | 0.000 | 0.000 |  |  |  |  | underpowered |
| D | issue_district_congruence:family:market_government_direction | 9.000 | 9.000 |  |  |  |  | underpowered |
| R | issue_district_congruence:family:market_government_direction | 9.000 | 9.000 |  |  |  |  | underpowered |
| D | issue_district_congruence:family:material_support | 65.000 | 65.000 | 2.943 | 9.492 | 0.758 |  | estimated |
| R | issue_district_congruence:family:material_support | 83.000 | 82.000 | -3.066 | 4.931 | 0.536 |  | estimated |
| D | issue_district_congruence:family:order_justice | 12.000 | 12.000 |  |  |  |  | underpowered |
| R | issue_district_congruence:family:order_justice | 9.000 | 9.000 |  |  |  |  | underpowered |
| D | issue_district_congruence:family:social_liberty_equality | 89.000 | 88.000 | -1.370 | 3.941 | 0.729 |  | estimated |
| R | issue_district_congruence:family:social_liberty_equality | 124.000 | 123.000 | -10.181 | 5.224 | 0.054 |  | estimated |

## Era heterogeneity

| sample | outcome | n | coefficient | cluster_se | p_value | status |
|---|---|---|---|---|---|---|
| D:2008_2014 | candidate_cmo | 61.000 | 7.290 | 5.260 | 0.172 | estimated |
| D:post_2016 | candidate_cmo | 5.000 |  |  |  | underpowered |
| D:pre_2008 | candidate_cmo | 143.000 | 16.428 | 4.445 | 0.000 | estimated |
| R:2008_2014 | candidate_cmo | 83.000 | -5.583 | 10.650 | 0.602 | estimated |
| R:post_2016 | candidate_cmo | 35.000 | -6.918 | 10.135 | 0.499 | estimated |
| R:pre_2008 | candidate_cmo | 80.000 | 1.743 | 9.230 | 0.851 | estimated |
| D:2008_2014 | candidate_federal_overperformance | 51.000 | -2.504 | 10.241 | 0.808 | estimated |
| D:post_2016 | candidate_federal_overperformance | 5.000 |  |  |  | underpowered |
| D:pre_2008 | candidate_federal_overperformance | 131.000 | 22.167 | 6.746 | 0.001 | estimated |
| R:2008_2014 | candidate_federal_overperformance | 66.000 | 10.722 | 18.736 | 0.569 | estimated |
| R:post_2016 | candidate_federal_overperformance | 35.000 | -18.876 | 11.684 | 0.115 | estimated |
| R:pre_2008 | candidate_federal_overperformance | 72.000 | -3.167 | 11.289 | 0.780 | estimated |

## Democratic leave-one-cycle-out stability

| sample | outcome | n | coefficient | cluster_se | p_value | status |
|---|---|---|---|---|---|---|
| D:omit_1998 | candidate_cmo | 151.000 | 16.784 | 3.403 | 0.000 | estimated |
| D:omit_2002 | candidate_cmo | 159.000 | 13.976 | 3.275 | 0.000 | estimated |
| D:omit_2006 | candidate_cmo | 174.000 | 11.651 | 3.179 | 0.000 | estimated |
| D:omit_2010 | candidate_cmo | 172.000 | 15.743 | 3.176 | 0.000 | estimated |
| D:omit_2014 | candidate_cmo | 185.000 | 14.660 | 2.895 | 0.000 | estimated |
| D:omit_2018 | candidate_cmo | 204.000 | 14.722 | 2.878 | 0.000 | estimated |
| D:omit_1998 | candidate_federal_overperformance | 129.000 | 21.981 | 6.850 | 0.002 | estimated |
| D:omit_2002 | candidate_federal_overperformance | 137.000 | 17.103 | 6.021 | 0.005 | estimated |
| D:omit_2006 | candidate_federal_overperformance | 164.000 | 13.224 | 5.296 | 0.014 | estimated |
| D:omit_2010 | candidate_federal_overperformance | 150.000 | 21.445 | 6.070 | 0.001 | estimated |
| D:omit_2014 | candidate_federal_overperformance | 173.000 | 20.651 | 5.096 | 0.000 | estimated |
| D:omit_2018 | candidate_federal_overperformance | 182.000 | 18.623 | 5.292 | 0.001 | estimated |

## Durable repeat-candidate evidence

| measure | party | outcome | people | status | coefficient | standard_error | p_value | r_squared |
|---|---|---|---|---|---|---|---|---|
| shor_absolute | D | federal_mean | 60.000 | estimated | 14.042 | 7.695 | 0.073 | 0.054 |
| shor_absolute | D | presidential_mean | 60.000 | estimated |  |  |  |  |
| shor_absolute | R | federal_mean | 48.000 | estimated | -6.829 | 10.741 | 0.528 | 0.009 |
| shor_absolute | R | presidential_mean | 48.000 | estimated | -10.343 | 11.762 | 0.384 | 0.017 |
| family:environment_resources | D | federal_mean | 3.000 | underpowered |  |  |  |  |
| family:environment_resources | D | presidential_mean | 3.000 | underpowered |  |  |  |  |
| family:environment_resources | R | federal_mean | 2.000 | underpowered |  |  |  |  |
| family:environment_resources | R | presidential_mean | 2.000 | underpowered |  |  |  |  |
| family:institutional_reform | D | federal_mean | 0.000 | underpowered |  |  |  |  |
| family:institutional_reform | D | presidential_mean | 0.000 | underpowered |  |  |  |  |
| family:institutional_reform | R | federal_mean | 1.000 | underpowered |  |  |  |  |
| family:institutional_reform | R | presidential_mean | 1.000 | underpowered |  |  |  |  |
| family:labor_capital | D | federal_mean | 0.000 | underpowered |  |  |  |  |
| family:labor_capital | D | presidential_mean | 0.000 | underpowered |  |  |  |  |
| family:labor_capital | R | federal_mean | 0.000 | underpowered |  |  |  |  |
| family:labor_capital | R | presidential_mean | 0.000 | underpowered |  |  |  |  |
| family:market_government_direction | D | federal_mean | 3.000 | underpowered |  |  |  |  |
| family:market_government_direction | D | presidential_mean | 3.000 | underpowered |  |  |  |  |
| family:market_government_direction | R | federal_mean | 2.000 | underpowered |  |  |  |  |
| family:market_government_direction | R | presidential_mean | 2.000 | underpowered |  |  |  |  |
| family:material_support | D | federal_mean | 23.000 | estimated |  |  |  |  |
| family:material_support | D | presidential_mean | 23.000 | estimated | 2.882 | 11.889 | 0.811 | 0.003 |
| family:material_support | R | federal_mean | 16.000 | estimated |  |  |  |  |
| family:material_support | R | presidential_mean | 16.000 | estimated | -1.072 | 8.837 | 0.905 | 0.001 |
| family:order_justice | D | federal_mean | 3.000 | underpowered |  |  |  |  |
| family:order_justice | D | presidential_mean | 3.000 | underpowered |  |  |  |  |
| family:order_justice | R | federal_mean | 3.000 | underpowered |  |  |  |  |
| family:order_justice | R | presidential_mean | 3.000 | underpowered |  |  |  |  |
| family:social_liberty_equality | D | federal_mean | 27.000 | estimated |  |  |  |  |
| family:social_liberty_equality | D | presidential_mean | 27.000 | estimated | 4.728 | 11.494 | 0.684 | 0.007 |
| family:social_liberty_equality | R | federal_mean | 33.000 | estimated |  |  |  |  |
| family:social_liberty_equality | R | presidential_mean | 33.000 | estimated | -10.067 | 7.890 | 0.211 | 0.050 |
| primitive:gun_access | D | federal_mean | 51.000 | estimated |  |  |  |  |
| primitive:gun_access | D | presidential_mean | 51.000 | estimated |  |  |  |  |
| primitive:gun_access | R | federal_mean | 48.000 | estimated | 9.028 | 7.200 | 0.216 | 0.033 |
| primitive:gun_access | R | presidential_mean | 48.000 | estimated | 14.998 | 7.276 | 0.045 | 0.085 |
| primitive:gun_purchase_regulation | D | federal_mean | 9.000 | underpowered |  |  |  |  |
| primitive:gun_purchase_regulation | D | presidential_mean | 9.000 | underpowered |  |  |  |  |
| primitive:gun_purchase_regulation | R | federal_mean | 21.000 | estimated |  |  |  |  |
| primitive:gun_purchase_regulation | R | presidential_mean | 21.000 | estimated | 7.627 | 4.430 | 0.101 | 0.135 |
| primitive:abortion_access | D | federal_mean | 14.000 | estimated |  |  |  |  |
| primitive:abortion_access | D | presidential_mean | 14.000 | estimated | 9.360 | 13.742 | 0.509 | 0.037 |
| primitive:abortion_access | R | federal_mean | 21.000 | underpowered |  |  |  |  |
| primitive:abortion_access | R | presidential_mean | 21.000 | underpowered |  |  |  |  |
| primitive:marriage_equality | D | federal_mean | 20.000 | underpowered |  |  |  |  |
| primitive:marriage_equality | D | presidential_mean | 20.000 | underpowered |  |  |  |  |
| primitive:marriage_equality | R | federal_mean | 15.000 | underpowered |  |  |  |  |
| primitive:marriage_equality | R | presidential_mean | 15.000 | underpowered |  |  |  |  |
| primitive:civil_social_liberty | D | federal_mean | 30.000 | estimated |  |  |  |  |
| primitive:civil_social_liberty | D | presidential_mean | 30.000 | estimated |  |  |  |  |
| primitive:civil_social_liberty | R | federal_mean | 28.000 | estimated |  |  |  |  |
| primitive:civil_social_liberty | R | presidential_mean | 28.000 | estimated | -2.255 | 9.885 | 0.821 | 0.002 |
| primitive:christian_sexual_morality | D | federal_mean | 1.000 | underpowered |  |  |  |  |
| primitive:christian_sexual_morality | D | presidential_mean | 1.000 | underpowered |  |  |  |  |
| primitive:christian_sexual_morality | R | federal_mean | 11.000 | underpowered |  |  |  |  |
| primitive:christian_sexual_morality | R | presidential_mean | 11.000 | underpowered |  |  |  |  |
| primitive:racial_civil_rights | D | federal_mean | 3.000 | underpowered |  |  |  |  |
| primitive:racial_civil_rights | D | presidential_mean | 3.000 | underpowered |  |  |  |  |
| primitive:racial_civil_rights | R | federal_mean | 16.000 | underpowered |  |  |  |  |
| primitive:racial_civil_rights | R | presidential_mean | 16.000 | underpowered |  |  |  |  |
| primitive:anti_discrimination | D | federal_mean | 19.000 | estimated |  |  |  |  |
| primitive:anti_discrimination | D | presidential_mean | 19.000 | estimated | 6.298 | 6.067 | 0.314 | 0.060 |
| primitive:anti_discrimination | R | federal_mean | 14.000 | underpowered |  |  |  |  |
| primitive:anti_discrimination | R | presidential_mean | 14.000 | underpowered |  |  |  |  |
| primitive:religion_state | D | federal_mean | 28.000 | underpowered |  |  |  |  |
| primitive:religion_state | D | presidential_mean | 28.000 | underpowered |  |  |  |  |
| primitive:religion_state | R | federal_mean | 21.000 | underpowered |  |  |  |  |
| primitive:religion_state | R | presidential_mean | 21.000 | underpowered |  |  |  |  |
| primitive:criminal_punishment | D | federal_mean | 44.000 | estimated |  |  |  |  |
| primitive:criminal_punishment | D | presidential_mean | 44.000 | estimated |  |  |  |  |
| primitive:criminal_punishment | R | federal_mean | 39.000 | estimated |  |  |  |  |
| primitive:criminal_punishment | R | presidential_mean | 39.000 | estimated | -9.492 | 23.235 | 0.685 | 0.004 |
| primitive:drug_criminalization | D | federal_mean | 3.000 | underpowered |  |  |  |  |
| primitive:drug_criminalization | D | presidential_mean | 3.000 | underpowered |  |  |  |  |
| primitive:drug_criminalization | R | federal_mean | 3.000 | underpowered |  |  |  |  |
| primitive:drug_criminalization | R | presidential_mean | 3.000 | underpowered |  |  |  |  |
| primitive:due_process | D | federal_mean | 0.000 | underpowered |  |  |  |  |
| primitive:due_process | D | presidential_mean | 0.000 | underpowered |  |  |  |  |
| primitive:due_process | R | federal_mean | 7.000 | underpowered |  |  |  |  |
| primitive:due_process | R | presidential_mean | 7.000 | underpowered |  |  |  |  |
| primitive:market_governance | D | federal_mean | 38.000 | estimated |  |  |  |  |
| primitive:market_governance | D | presidential_mean | 38.000 | estimated |  |  |  |  |
| primitive:market_governance | R | federal_mean | 42.000 | estimated |  |  |  |  |
| primitive:market_governance | R | presidential_mean | 42.000 | estimated | 7.029 | 7.258 | 0.339 | 0.023 |
| primitive:tax_burden | D | federal_mean | 23.000 | estimated |  |  |  |  |
| primitive:tax_burden | D | presidential_mean | 23.000 | estimated |  |  |  |  |
| primitive:tax_burden | R | federal_mean | 19.000 | estimated |  |  |  |  |
| primitive:tax_burden | R | presidential_mean | 19.000 | estimated |  |  |  |  |
| primitive:tax_distribution | D | federal_mean | 3.000 | underpowered |  |  |  |  |
| primitive:tax_distribution | D | presidential_mean | 3.000 | underpowered |  |  |  |  |
| primitive:tax_distribution | R | federal_mean | 0.000 | underpowered |  |  |  |  |
| primitive:tax_distribution | R | presidential_mean | 0.000 | underpowered |  |  |  |  |
| primitive:public_spending | D | federal_mean | 19.000 | underpowered |  |  |  |  |
| primitive:public_spending | D | presidential_mean | 19.000 | underpowered |  |  |  |  |
| primitive:public_spending | R | federal_mean | 20.000 | estimated | 14.132 | 7.108 | 0.062 | 0.180 |
| primitive:public_spending | R | presidential_mean | 20.000 | estimated |  |  |  |  |
| primitive:deficit_discipline | D | federal_mean | 12.000 | underpowered |  |  |  |  |
| primitive:deficit_discipline | D | presidential_mean | 12.000 | underpowered |  |  |  |  |
| primitive:deficit_discipline | R | federal_mean | 11.000 | underpowered |  |  |  |  |
| primitive:deficit_discipline | R | presidential_mean | 11.000 | underpowered |  |  |  |  |
| primitive:welfare_generosity | D | federal_mean | 20.000 | estimated |  |  |  |  |
| primitive:welfare_generosity | D | presidential_mean | 20.000 | estimated | 1.458 | 14.311 | 0.920 | 0.001 |
| primitive:welfare_generosity | R | federal_mean | 14.000 | estimated |  |  |  |  |
| primitive:welfare_generosity | R | presidential_mean | 14.000 | estimated | -4.499 | 4.477 | 0.335 | 0.078 |
| primitive:welfare_conditionality | D | federal_mean | 18.000 | underpowered |  |  |  |  |
| primitive:welfare_conditionality | D | presidential_mean | 18.000 | underpowered |  |  |  |  |
| primitive:welfare_conditionality | R | federal_mean | 16.000 | underpowered |  |  |  |  |
| primitive:welfare_conditionality | R | presidential_mean | 16.000 | underpowered |  |  |  |  |
| primitive:labor_capital_alignment | D | federal_mean | 21.000 | underpowered |  |  |  |  |
| primitive:labor_capital_alignment | D | presidential_mean | 21.000 | underpowered |  |  |  |  |
| primitive:labor_capital_alignment | R | federal_mean | 11.000 | underpowered |  |  |  |  |
| primitive:labor_capital_alignment | R | presidential_mean | 11.000 | underpowered |  |  |  |  |
| primitive:labor_rights | D | federal_mean | 3.000 | underpowered |  |  |  |  |
| primitive:labor_rights | D | presidential_mean | 3.000 | underpowered |  |  |  |  |
| primitive:labor_rights | R | federal_mean | 5.000 | underpowered |  |  |  |  |
| primitive:labor_rights | R | presidential_mean | 5.000 | underpowered |  |  |  |  |
| primitive:public_employee_compensation | D | federal_mean | 34.000 | underpowered |  |  |  |  |
| primitive:public_employee_compensation | D | presidential_mean | 34.000 | underpowered |  |  |  |  |
| primitive:public_employee_compensation | R | federal_mean | 34.000 | underpowered |  |  |  |  |
| primitive:public_employee_compensation | R | presidential_mean | 34.000 | underpowered |  |  |  |  |
| primitive:education_public_funding | D | federal_mean | 38.000 | estimated |  |  |  |  |
| primitive:education_public_funding | D | presidential_mean | 38.000 | estimated |  |  |  |  |
| primitive:education_public_funding | R | federal_mean | 38.000 | estimated |  |  |  |  |
| primitive:education_public_funding | R | presidential_mean | 38.000 | estimated | -31.613 | 14.630 | 0.037 | 0.115 |
| primitive:education_market_choice | D | federal_mean | 13.000 | underpowered |  |  |  |  |
| primitive:education_market_choice | D | presidential_mean | 13.000 | underpowered |  |  |  |  |
| primitive:education_market_choice | R | federal_mean | 30.000 | estimated |  |  |  |  |
| primitive:education_market_choice | R | presidential_mean | 30.000 | estimated | 1.053 | 29.750 | 0.972 | 0.000 |
| primitive:environmental_protection | D | federal_mean | 12.000 | estimated |  |  |  |  |
| primitive:environmental_protection | D | presidential_mean | 12.000 | estimated | 1.303 | 12.386 | 0.918 | 0.001 |
| primitive:environmental_protection | R | federal_mean | 11.000 | underpowered |  |  |  |  |
| primitive:environmental_protection | R | presidential_mean | 11.000 | underpowered |  |  |  |  |
| primitive:resource_development | D | federal_mean | 7.000 | underpowered |  |  |  |  |
| primitive:resource_development | D | presidential_mean | 7.000 | underpowered |  |  |  |  |
| primitive:resource_development | R | federal_mean | 11.000 | underpowered |  |  |  |  |
| primitive:resource_development | R | presidential_mean | 11.000 | underpowered |  |  |  |  |
| primitive:conservation_preservation | D | federal_mean | 3.000 | underpowered |  |  |  |  |
| primitive:conservation_preservation | D | presidential_mean | 3.000 | underpowered |  |  |  |  |
| primitive:conservation_preservation | R | federal_mean | 1.000 | underpowered |  |  |  |  |
| primitive:conservation_preservation | R | presidential_mean | 1.000 | underpowered |  |  |  |  |
| primitive:immigration_access | D | federal_mean | 4.000 | underpowered |  |  |  |  |
| primitive:immigration_access | D | presidential_mean | 4.000 | underpowered |  |  |  |  |
| primitive:immigration_access | R | federal_mean | 3.000 | underpowered |  |  |  |  |
| primitive:immigration_access | R | presidential_mean | 3.000 | underpowered |  |  |  |  |
| primitive:immigration_enforcement | D | federal_mean | 5.000 | underpowered |  |  |  |  |
| primitive:immigration_enforcement | D | presidential_mean | 5.000 | underpowered |  |  |  |  |
| primitive:immigration_enforcement | R | federal_mean | 13.000 | underpowered |  |  |  |  |
| primitive:immigration_enforcement | R | presidential_mean | 13.000 | underpowered |  |  |  |  |
| primitive:healthcare_access | D | federal_mean | 42.000 | estimated |  |  |  |  |
| primitive:healthcare_access | D | presidential_mean | 42.000 | estimated |  |  |  |  |
| primitive:healthcare_access | R | federal_mean | 27.000 | estimated |  |  |  |  |
| primitive:healthcare_access | R | presidential_mean | 27.000 | estimated | -9.201 | 6.370 | 0.161 | 0.077 |
| primitive:government_ethics_transparency | D | federal_mean | 20.000 | estimated |  |  |  |  |
| primitive:government_ethics_transparency | D | presidential_mean | 20.000 | estimated | 4.242 | 6.449 | 0.519 | 0.023 |
| primitive:government_ethics_transparency | R | federal_mean | 27.000 | estimated |  |  |  |  |
| primitive:government_ethics_transparency | R | presidential_mean | 27.000 | estimated | 7.326 | 4.178 | 0.092 | 0.110 |
| primitive:voting_access | D | federal_mean | 15.000 | underpowered |  |  |  |  |
| primitive:voting_access | D | presidential_mean | 15.000 | underpowered |  |  |  |  |
| primitive:voting_access | R | federal_mean | 13.000 | underpowered |  |  |  |  |
| primitive:voting_access | R | presidential_mean | 13.000 | underpowered |  |  |  |  |

## Interpretation rules

- Party-specific estimates are primary; pooled convergence is descriptive only.
- Federal and presidential outcomes are the primary durability tests.
- Incumbency and finance are reported both as mechanisms and controls, never silently absorbed into expected performance.
- Sparse issue families and era cells remain underpowered even when point estimates are large.
- Shor scores are absolute and nationally bridged, but are career scores observed only for people who served.
- No estimate in this report is automatically eligible for the production forecast.
- Candidate margins already encode the arithmetic behind the crossover intuition: moving one voter from the opponent changes the two-party margin twice as much as adding one same-party voter. Aggregate results cannot identify whether an observed margin gain actually came from persuasion or differential turnout.
