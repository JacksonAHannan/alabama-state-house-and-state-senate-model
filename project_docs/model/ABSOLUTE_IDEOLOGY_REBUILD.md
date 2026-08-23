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
| social_liberty_equality | D | 102.000 | 101.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:gun_access | D | 205.000 | 190.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:gun_purchase_regulation | D | 60.000 | 58.000 | 2002,2006,2010,2014,2018,2022 |
| primitive:abortion_access | D | 74.000 | 71.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:marriage_equality | D | 56.000 | 56.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:civil_social_liberty | D | 80.000 | 78.000 | 1998,2002,2006,2010,2018,2022 |
| primitive:christian_sexual_morality | D | 9.000 | 9.000 | 2018,2022 |
| primitive:racial_civil_rights | D | 15.000 | 15.000 | 2002,2006,2018 |
| primitive:anti_discrimination | D | 74.000 | 74.000 | 1994,1998,2002,2006,2010,2014,2018,2022 |
| primitive:religion_state | D | 73.000 | 73.000 | 1998,2002,2006,2014,2018,2022 |
| primitive:criminal_punishment | D | 124.000 | 117.000 | 1994,1998,2002,2006,2010,2014,2018,2022 |
| primitive:drug_criminalization | D | 17.000 | 17.000 | 2006,2010,2014,2022 |
| primitive:due_process | D | 3.000 | 3.000 | 2014,2022 |
| primitive:market_governance | D | 133.000 | 127.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:tax_burden | D | 70.000 | 69.000 | 1994,1998,2002,2006,2010,2014,2018,2022 |
| primitive:tax_distribution | D | 14.000 | 14.000 | 1994,2010,2014,2018,2022 |
| primitive:public_spending | D | 38.000 | 38.000 | 1998,2006,2014,2018,2022 |
| primitive:deficit_discipline | D | 24.000 | 24.000 | 1998,2006 |
| primitive:welfare_generosity | D | 54.000 | 53.000 | 1994,1998,2002,2006,2010,2014,2022 |
| primitive:welfare_conditionality | D | 63.000 | 63.000 | 1998,2002,2006,2018 |
| primitive:labor_capital_alignment | D | 82.000 | 82.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:labor_rights | D | 54.000 | 54.000 | 2014,2018,2022 |
| primitive:public_employee_compensation | D | 84.000 | 81.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:education_public_funding | D | 130.000 | 123.000 | 1994,1998,2002,2006,2010,2014,2018,2022 |
| primitive:education_market_choice | D | 75.000 | 74.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:environmental_protection | D | 65.000 | 65.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:resource_development | D | 17.000 | 17.000 | 2006,2010,2014 |
| primitive:conservation_preservation | D | 22.000 | 22.000 | 2002,2010,2014,2018 |
| primitive:immigration_access | D | 26.000 | 26.000 | 2006,2010,2014,2018,2022 |
| primitive:immigration_enforcement | D | 15.000 | 15.000 | 2014,2022 |
| primitive:healthcare_access | D | 132.000 | 130.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:government_ethics_transparency | D | 58.000 | 50.000 | 1994,2006,2010,2014,2018,2022 |
| primitive:voting_access | D | 64.000 | 64.000 | 1998,2002,2006,2010,2014,2018,2022 |
| shor_absolute | R | 198.000 | 154.000 | 1998,2002,2006,2010,2014,2018 |
| environment_resources | R | 22.000 | 22.000 | 2002,2010,2014 |
| institutional_reform | R | 2.000 | 2.000 | 2014,2018 |
| labor_capital | R | 0.000 | 0.000 |  |
| market_government_direction | R | 9.000 | 9.000 | 2010 |
| material_support | R | 92.000 | 91.000 | 1998,2002,2006,2010,2014,2018 |
| order_justice | R | 15.000 | 15.000 | 2006,2010,2014,2022 |
| social_liberty_equality | R | 143.000 | 141.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:gun_access | R | 240.000 | 210.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:gun_purchase_regulation | R | 72.000 | 67.000 | 2002,2006,2010,2014,2018,2022 |
| primitive:abortion_access | R | 109.000 | 103.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:marriage_equality | R | 92.000 | 91.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:civil_social_liberty | R | 86.000 | 84.000 | 1998,2002,2006,2010,2018,2022 |
| primitive:christian_sexual_morality | R | 35.000 | 35.000 | 2018,2022 |
| primitive:racial_civil_rights | R | 41.000 | 41.000 | 2002,2006,2018 |
| primitive:anti_discrimination | R | 90.000 | 89.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:religion_state | R | 98.000 | 98.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:criminal_punishment | R | 174.000 | 161.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:drug_criminalization | R | 17.000 | 17.000 | 2006,2010,2014,2018,2022 |
| primitive:due_process | R | 17.000 | 14.000 | 2014,2018,2022 |
| primitive:market_governance | R | 156.000 | 140.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:tax_burden | R | 68.000 | 66.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:tax_distribution | R | 1.000 | 1.000 | 2022 |
| primitive:public_spending | R | 65.000 | 64.000 | 1998,2010,2014,2018,2022 |
| primitive:deficit_discipline | R | 43.000 | 41.000 | 1994,1998,2010,2014,2018,2022 |
| primitive:welfare_generosity | R | 75.000 | 74.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:welfare_conditionality | R | 74.000 | 73.000 | 1998,2002,2006,2010,2014,2018 |
| primitive:labor_capital_alignment | R | 53.000 | 53.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:labor_rights | R | 10.000 | 10.000 | 2014,2018 |
| primitive:public_employee_compensation | R | 95.000 | 83.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:education_public_funding | R | 151.000 | 139.000 | 1994,1998,2002,2006,2010,2014,2018,2022 |
| primitive:education_market_choice | R | 115.000 | 105.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:environmental_protection | R | 68.000 | 66.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:resource_development | R | 39.000 | 39.000 | 2006,2010,2014,2018,2022 |
| primitive:conservation_preservation | R | 21.000 | 21.000 | 2002,2010,2014 |
| primitive:immigration_access | R | 11.000 | 11.000 | 2010,2014,2018 |
| primitive:immigration_enforcement | R | 20.000 | 20.000 | 2010,2014,2022 |
| primitive:healthcare_access | R | 111.000 | 107.000 | 1998,2002,2006,2010,2014,2018,2022 |
| primitive:government_ethics_transparency | R | 84.000 | 67.000 | 2002,2006,2010,2014,2018 |
| primitive:voting_access | R | 78.000 | 77.000 | 1998,2002,2014,2018,2022 |

## Absolute-scale overlap

| party | candidate_cycles | people | mean | sd | minimum | p10 | median | p90 | maximum | common_support_low | common_support_high | inside_common_support |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D | 209.000 | 179.000 | -0.216 | 0.383 | -1.500 | -0.700 | -0.166 | 0.214 | 0.619 | 0.155 | 0.619 | 25.000 |
| R | 198.000 | 154.000 | 1.002 | 0.239 | 0.155 | 0.725 | 1.038 | 1.274 | 1.805 | 0.155 | 0.619 | 12.000 |

The parties have limited common support on the absolute scale. Republican moderation estimates therefore rely on a narrow tail of the Republican distribution and should not be treated as a mirror-image test with equal power.

## Selection into Shor–McCarty coverage

| party | shor_observed | candidate_cycles | people | winner_share | incumbent_share | mean_cmo | mean_federal_overperformance |
|---|---|---|---|---|---|---|---|
| D | False | 300.000 | 283.000 | 0.213 | 0.017 | -4.690 | 7.364 |
| D | True | 209.000 | 179.000 | 0.837 | 0.220 | 5.812 | 34.975 |
| R | False | 311.000 | 302.000 | 0.273 | 0.013 | -1.345 | -24.860 |
| R | True | 198.000 | 154.000 | 0.934 | 0.364 | 3.084 | -9.296 |

Shor coverage is a selected officeholder sample. Differences between observed and unobserved candidates quantify why these estimates describe successful legislative candidates rather than all people who ran.

### Selection sensitivities

| sample | outcome | specification | n | people | coefficient | cluster_se | p_value | status |
|---|---|---|---|---|---|---|---|---|
| D | candidate_cmo | party_winners_only | 175.000 | 160.000 | 13.795 | 4.299 | 0.002 | estimated |
| D | candidate_cmo | party_prior_service_only | 177.000 | 152.000 | 17.941 | 4.314 | 0.000 | estimated |
| R | candidate_cmo | party_winners_only | 185.000 | 145.000 | -4.175 | 6.986 | 0.551 | estimated |
| R | candidate_cmo | party_prior_service_only | 136.000 | 110.000 | -3.720 | 9.364 | 0.692 | estimated |
| D | candidate_federal_overperformance | party_winners_only | 159.000 | 148.000 | 17.423 | 5.688 | 0.003 | estimated |
| D | candidate_federal_overperformance | party_prior_service_only | 157.000 | 145.000 | 17.975 | 5.646 | 0.002 | estimated |
| R | candidate_federal_overperformance | party_winners_only | 160.000 | 136.000 | -3.797 | 7.993 | 0.636 | estimated |
| R | candidate_federal_overperformance | party_prior_service_only | 119.000 | 103.000 | -1.701 | 9.307 | 0.855 | estimated |

## Absolute Shor–McCarty results

| sample | outcome | n | people | coefficient | cluster_se | ci_low | ci_high | p_value | status |
|---|---|---|---|---|---|---|---|---|---|
| D | candidate_cmo | 209.000 | 179.000 | 15.326 | 4.098 | 7.294 | 23.358 | 0.000 | estimated |
| R | candidate_cmo | 198.000 | 154.000 | 0.048 | 6.751 | -13.184 | 13.279 | 0.994 | estimated |
| D | candidate_federal_overperformance | 187.000 | 171.000 | 18.768 | 5.245 | 8.488 | 29.047 | 0.000 | estimated |
| R | candidate_federal_overperformance | 173.000 | 146.000 | -5.310 | 7.424 | -19.861 | 9.241 | 0.476 | estimated |
| D | candidate_presidential_overperformance | 199.000 | 170.000 | 10.746 | 3.565 | 3.759 | 17.733 | 0.003 | estimated |
| R | candidate_presidential_overperformance | 190.000 | 149.000 | -12.203 | 8.795 | -29.441 | 5.035 | 0.167 | estimated |

Positive coefficients mean moving right helps; negative coefficients mean moving left helps. The Democratic coefficients are positive across all primary outcomes. Republican coefficients generally point toward an advantage for moving left but remain imprecise.

## Symmetric-incumbency sensitivity

| outcome | specification | term | n | coefficient | cluster_se | p_value | status |
|---|---|---|---|---|---|---|---|
| candidate_cmo | common_incumbency | incumbent_i | 407.000 | -8.192 | 2.687 | 0.002 | estimated |
| candidate_cmo | party_specific_incumbency | incumbent_i | 407.000 | -3.511 | 3.545 | 0.323 | estimated |
| candidate_cmo | party_specific_incumbency | democratic_x_incumbency | 407.000 | -10.377 | 4.339 | 0.017 | estimated |
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
| D | candidate_cmo | party_total_context | 209.000 | 15.326 | 4.098 | 0.000 | estimated |
| D | candidate_cmo | party_mediator_adjusted | 158.000 | 13.402 | 5.343 | 0.013 | estimated |
| R | candidate_cmo | party_total_context | 198.000 | 0.048 | 6.751 | 0.994 | estimated |
| R | candidate_cmo | party_mediator_adjusted | 169.000 | 4.206 | 6.565 | 0.523 | estimated |
| D | candidate_federal_overperformance | party_total_context | 187.000 | 18.768 | 5.245 | 0.000 | estimated |
| D | candidate_federal_overperformance | party_mediator_adjusted | 139.000 | 21.450 | 5.954 | 0.000 | estimated |
| R | candidate_federal_overperformance | party_total_context | 173.000 | -5.310 | 7.424 | 0.476 | estimated |
| R | candidate_federal_overperformance | party_mediator_adjusted | 145.000 | 1.767 | 7.227 | 0.807 | estimated |

## Issue-position results

Positive coefficients mean that a more conservative absolute position is associated with greater candidate-directional overperformance. These estimates use only temporally eligible ideology-v3 evidence.

| sample | outcome | specification | n | people | coefficient | cluster_se | p_value | primary_bh_q_value | status |
|---|---|---|---|---|---|---|---|---|---|
| D | candidate_federal_overperformance | issue_total:primitive:gun_access | 185.000 | 178.000 | 4.298 | 3.283 | 0.192 | 0.416 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:gun_access | 195.000 | 181.000 | 8.351 | 2.222 | 0.000 | 0.003 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:gun_access | 218.000 | 200.000 | -0.163 | 2.059 | 0.937 | 0.937 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:gun_access | 235.000 | 205.000 | 4.714 | 2.184 | 0.032 | 0.120 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:gun_purchase_regulation | 52.000 | 51.000 | 5.276 | 5.251 | 0.320 | 0.514 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:gun_purchase_regulation | 56.000 | 54.000 | 5.317 | 4.577 | 0.251 | 0.435 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:gun_purchase_regulation | 56.000 | 55.000 | -8.171 | 4.133 | 0.053 | 0.136 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:gun_purchase_regulation | 70.000 | 65.000 | -8.487 | 5.699 | 0.141 | 0.285 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:abortion_access | 62.000 | 60.000 | 9.287 | 3.975 | 0.023 | 0.094 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:abortion_access | 69.000 | 66.000 | 10.563 | 4.355 | 0.018 | 0.081 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:abortion_access | 95.000 | 91.000 | 7.373 | 4.986 | 0.143 | 0.285 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:abortion_access | 105.000 | 100.000 | 13.161 | 5.833 | 0.026 | 0.110 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:marriage_equality | 53.000 | 53.000 | 7.928 | 5.894 | 0.184 | 0.416 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:marriage_equality | 53.000 | 53.000 | 3.499 | 8.874 | 0.695 | 0.823 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:marriage_equality | 83.000 | 82.000 | -3.384 | 2.630 | 0.202 | 0.370 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:marriage_equality | 91.000 | 90.000 | 8.935 | 2.866 | 0.002 | 0.052 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:civil_social_liberty | 70.000 | 68.000 | 9.399 | 2.892 | 0.002 | 0.014 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:civil_social_liberty | 76.000 | 74.000 | 11.354 | 2.712 | 0.000 | 0.001 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:civil_social_liberty | 77.000 | 76.000 | 6.075 | 4.794 | 0.209 | 0.370 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:civil_social_liberty | 85.000 | 83.000 | 6.773 | 4.517 | 0.138 | 0.285 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:christian_sexual_morality | 9.000 | 9.000 |  |  |  |  | underpowered |
| D | candidate_presidential_overperformance | issue_total:primitive:christian_sexual_morality | 9.000 | 9.000 |  |  |  |  | underpowered |
| R | candidate_federal_overperformance | issue_total:primitive:christian_sexual_morality | 35.000 | 35.000 |  |  |  |  | no_variation |
| R | candidate_presidential_overperformance | issue_total:primitive:christian_sexual_morality | 35.000 | 35.000 |  |  |  |  | no_variation |
| D | candidate_federal_overperformance | issue_total:primitive:racial_civil_rights | 14.000 | 14.000 |  |  |  |  | underpowered |
| D | candidate_presidential_overperformance | issue_total:primitive:racial_civil_rights | 14.000 | 14.000 |  |  |  |  | underpowered |
| R | candidate_federal_overperformance | issue_total:primitive:racial_civil_rights | 41.000 | 41.000 | -0.626 | 5.447 | 0.909 | 0.929 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:racial_civil_rights | 40.000 | 40.000 | -1.342 | 8.169 | 0.870 | 0.929 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:anti_discrimination | 70.000 | 70.000 | 3.389 | 4.411 | 0.445 | 0.690 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:anti_discrimination | 71.000 | 71.000 | 1.975 | 3.878 | 0.612 | 0.775 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:anti_discrimination | 81.000 | 80.000 | 3.046 | 2.636 | 0.251 | 0.428 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:anti_discrimination | 89.000 | 88.000 | -1.021 | 5.982 | 0.865 | 0.929 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:religion_state | 65.000 | 65.000 | 2.496 | 3.392 | 0.465 | 0.697 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:religion_state | 71.000 | 71.000 | -0.193 | 4.137 | 0.963 | 0.992 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:religion_state | 85.000 | 85.000 |  |  |  |  | no_variation |
| R | candidate_presidential_overperformance | issue_total:primitive:religion_state | 94.000 | 94.000 |  |  |  |  | no_variation |
| D | candidate_federal_overperformance | issue_total:primitive:criminal_punishment | 113.000 | 109.000 | 7.719 | 4.058 | 0.060 | 0.179 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:criminal_punishment | 120.000 | 113.000 | 3.881 | 6.072 | 0.524 | 0.751 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:criminal_punishment | 156.000 | 149.000 | 24.527 | 9.531 | 0.011 | 0.085 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:criminal_punishment | 170.000 | 157.000 | 27.558 | 11.628 | 0.019 | 0.104 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:drug_criminalization | 15.000 | 15.000 |  |  |  |  | underpowered |
| D | candidate_presidential_overperformance | issue_total:primitive:drug_criminalization | 16.000 | 16.000 |  |  |  |  | underpowered |
| R | candidate_federal_overperformance | issue_total:primitive:drug_criminalization | 14.000 | 14.000 |  |  |  |  | underpowered |
| R | candidate_presidential_overperformance | issue_total:primitive:drug_criminalization | 17.000 | 17.000 |  |  |  |  | underpowered |
| D | candidate_federal_overperformance | issue_total:primitive:due_process | 3.000 | 3.000 |  |  |  |  | underpowered |
| D | candidate_presidential_overperformance | issue_total:primitive:due_process | 3.000 | 3.000 |  |  |  |  | underpowered |
| R | candidate_federal_overperformance | issue_total:primitive:due_process | 14.000 | 11.000 |  |  |  |  | underpowered |
| R | candidate_presidential_overperformance | issue_total:primitive:due_process | 17.000 | 14.000 |  |  |  |  | underpowered |
| D | candidate_federal_overperformance | issue_total:primitive:market_governance | 120.000 | 116.000 | 13.082 | 2.684 | 0.000 | 0.000 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:market_governance | 127.000 | 122.000 | 15.710 | 2.656 | 0.000 | 0.000 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:market_governance | 141.000 | 130.000 | 7.855 | 2.982 | 0.009 | 0.085 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:market_governance | 152.000 | 137.000 | 11.421 | 3.572 | 0.002 | 0.052 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:tax_burden | 64.000 | 63.000 | -9.795 | 6.455 | 0.134 | 0.336 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:tax_burden | 70.000 | 69.000 | -7.296 | 5.976 | 0.226 | 0.424 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:tax_burden | 65.000 | 63.000 | -14.010 | 5.646 | 0.016 | 0.104 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:tax_burden | 66.000 | 64.000 | -17.722 | 6.474 | 0.008 | 0.085 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:tax_distribution | 14.000 | 14.000 |  |  |  |  | underpowered |
| D | candidate_presidential_overperformance | issue_total:primitive:tax_distribution | 14.000 | 14.000 |  |  |  |  | underpowered |
| R | candidate_federal_overperformance | issue_total:primitive:tax_distribution | 1.000 | 1.000 |  |  |  |  | underpowered |
| R | candidate_presidential_overperformance | issue_total:primitive:tax_distribution | 1.000 | 1.000 |  |  |  |  | underpowered |
| D | candidate_federal_overperformance | issue_total:primitive:public_spending | 37.000 | 37.000 |  |  |  |  | no_variation |
| D | candidate_presidential_overperformance | issue_total:primitive:public_spending | 38.000 | 38.000 |  |  |  |  | no_variation |
| R | candidate_federal_overperformance | issue_total:primitive:public_spending | 64.000 | 63.000 | 1.502 | 2.162 | 0.490 | 0.719 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:public_spending | 64.000 | 63.000 | 1.443 | 2.742 | 0.601 | 0.790 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:deficit_discipline | 24.000 | 24.000 | 3.380 | 5.823 | 0.567 | 0.751 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:deficit_discipline | 24.000 | 24.000 | 1.226 | 5.877 | 0.837 | 0.918 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:deficit_discipline | 43.000 | 41.000 | 2.786 | 4.046 | 0.495 | 0.719 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:deficit_discipline | 43.000 | 41.000 | 3.050 | 4.484 | 0.500 | 0.719 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:welfare_generosity | 50.000 | 50.000 | -7.240 | 3.857 | 0.066 | 0.187 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:welfare_generosity | 52.000 | 51.000 | -9.874 | 5.085 | 0.058 | 0.179 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:welfare_generosity | 67.000 | 67.000 | -8.175 | 3.437 | 0.020 | 0.104 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:welfare_generosity | 74.000 | 73.000 | -8.103 | 4.119 | 0.053 | 0.136 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:welfare_conditionality | 60.000 | 60.000 | -2.559 | 4.152 | 0.540 | 0.751 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:welfare_conditionality | 61.000 | 61.000 | -10.690 | 3.114 | 0.001 | 0.010 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:welfare_conditionality | 65.000 | 64.000 |  |  |  |  | no_variation |
| R | candidate_presidential_overperformance | issue_total:primitive:welfare_conditionality | 73.000 | 72.000 |  |  |  |  | no_variation |
| D | candidate_federal_overperformance | issue_total:primitive:labor_capital_alignment | 75.000 | 75.000 | 11.898 | 9.327 | 0.206 | 0.416 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:labor_capital_alignment | 80.000 | 80.000 | 14.656 | 5.430 | 0.009 | 0.052 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:labor_capital_alignment | 50.000 | 50.000 | 2.020 | 4.901 | 0.682 | 0.872 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:labor_capital_alignment | 53.000 | 53.000 | 1.407 | 4.548 | 0.758 | 0.889 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:labor_rights | 53.000 | 53.000 |  |  |  |  | no_variation |
| D | candidate_presidential_overperformance | issue_total:primitive:labor_rights | 54.000 | 54.000 |  |  |  |  | no_variation |
| R | candidate_federal_overperformance | issue_total:primitive:labor_rights | 7.000 | 7.000 |  |  |  |  | underpowered |
| R | candidate_presidential_overperformance | issue_total:primitive:labor_rights | 10.000 | 10.000 |  |  |  |  | underpowered |
| D | candidate_federal_overperformance | issue_total:primitive:public_employee_compensation | 75.000 | 73.000 |  |  |  |  | no_variation |
| D | candidate_presidential_overperformance | issue_total:primitive:public_employee_compensation | 82.000 | 79.000 | 5.931 | 5.133 | 0.251 | 0.435 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:public_employee_compensation | 80.000 | 75.000 | -6.548 | 5.021 | 0.196 | 0.370 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:public_employee_compensation | 91.000 | 80.000 | 0.745 | 3.918 | 0.850 | 0.929 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:education_public_funding | 119.000 | 115.000 | -14.925 | 6.872 | 0.032 | 0.120 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:education_public_funding | 124.000 | 117.000 | -12.683 | 10.118 | 0.213 | 0.416 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:education_public_funding | 133.000 | 126.000 | 1.179 | 9.171 | 0.898 | 0.929 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:education_public_funding | 150.000 | 138.000 | 2.673 | 8.332 | 0.749 | 0.889 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:education_market_choice | 70.000 | 69.000 | 1.563 | 3.973 | 0.695 | 0.823 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:education_market_choice | 72.000 | 71.000 | 1.621 | 3.252 | 0.620 | 0.775 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:education_market_choice | 100.000 | 95.000 | 4.121 | 4.360 | 0.347 | 0.550 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:education_market_choice | 111.000 | 102.000 | 11.593 | 5.900 | 0.052 | 0.136 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:environmental_protection | 60.000 | 60.000 | 18.664 | 6.931 | 0.009 | 0.052 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:environmental_protection | 61.000 | 61.000 | 14.732 | 7.011 | 0.040 | 0.138 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:environmental_protection | 62.000 | 61.000 | -1.162 | 4.017 | 0.773 | 0.889 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:environmental_protection | 67.000 | 65.000 | -5.900 | 3.847 | 0.130 | 0.285 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:resource_development | 16.000 | 16.000 |  |  |  |  | underpowered |
| D | candidate_presidential_overperformance | issue_total:primitive:resource_development | 16.000 | 16.000 |  |  |  |  | underpowered |
| R | candidate_federal_overperformance | issue_total:primitive:resource_development | 30.000 | 30.000 | 4.179 | 7.851 | 0.599 | 0.790 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:resource_development | 39.000 | 39.000 | -4.504 | 7.345 | 0.543 | 0.757 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:conservation_preservation | 22.000 | 22.000 | 5.931 | 9.903 | 0.556 | 0.751 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:conservation_preservation | 21.000 | 21.000 | -2.206 | 9.168 | 0.812 | 0.918 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:conservation_preservation | 21.000 | 21.000 | -4.130 | 3.953 | 0.309 | 0.507 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:conservation_preservation | 20.000 | 20.000 | 1.438 | 3.890 | 0.716 | 0.889 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:immigration_access | 25.000 | 25.000 | -8.013 | 6.078 | 0.200 | 0.416 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:immigration_access | 25.000 | 25.000 | 0.519 | 6.929 | 0.941 | 0.992 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:immigration_access | 11.000 | 11.000 |  |  |  |  | underpowered |
| R | candidate_presidential_overperformance | issue_total:primitive:immigration_access | 11.000 | 11.000 |  |  |  |  | underpowered |
| D | candidate_federal_overperformance | issue_total:primitive:immigration_enforcement | 10.000 | 10.000 |  |  |  |  | underpowered |
| D | candidate_presidential_overperformance | issue_total:primitive:immigration_enforcement | 13.000 | 13.000 |  |  |  |  | underpowered |
| R | candidate_federal_overperformance | issue_total:primitive:immigration_enforcement | 13.000 | 13.000 |  |  |  |  | underpowered |
| R | candidate_presidential_overperformance | issue_total:primitive:immigration_enforcement | 20.000 | 20.000 |  |  |  |  | no_variation |
| D | candidate_federal_overperformance | issue_total:primitive:healthcare_access | 120.000 | 119.000 | 6.806 | 6.535 | 0.300 | 0.500 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:healthcare_access | 128.000 | 126.000 | -0.368 | 9.754 | 0.970 | 0.992 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:healthcare_access | 97.000 | 95.000 | -8.510 | 3.733 | 0.025 | 0.110 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:healthcare_access | 108.000 | 104.000 | -11.006 | 3.666 | 0.003 | 0.052 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:government_ethics_transparency | 47.000 | 42.000 | 13.058 | 4.884 | 0.011 | 0.054 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:government_ethics_transparency | 56.000 | 48.000 | 7.134 | 4.683 | 0.134 | 0.336 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:government_ethics_transparency | 67.000 | 58.000 | 5.356 | 3.310 | 0.111 | 0.269 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:government_ethics_transparency | 83.000 | 66.000 | 5.564 | 2.567 | 0.034 | 0.120 | estimated |
| D | candidate_federal_overperformance | issue_total:primitive:voting_access | 63.000 | 63.000 | 0.653 | 2.819 | 0.818 | 0.918 | estimated |
| D | candidate_presidential_overperformance | issue_total:primitive:voting_access | 63.000 | 63.000 | -0.006 | 2.872 | 0.998 | 0.998 | estimated |
| R | candidate_federal_overperformance | issue_total:primitive:voting_access | 78.000 | 77.000 | -7.391 | 3.689 | 0.049 | 0.136 | estimated |
| R | candidate_presidential_overperformance | issue_total:primitive:voting_access | 76.000 | 75.000 | -9.679 | 4.850 | 0.050 | 0.136 | estimated |

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
| D | issue_district_congruence:family:material_support | 65.000 | 65.000 | -0.596 | 7.463 | 0.937 |  | estimated |
| R | issue_district_congruence:family:material_support | 83.000 | 82.000 | -3.006 | 4.937 | 0.544 |  | estimated |
| D | issue_district_congruence:family:order_justice | 12.000 | 12.000 |  |  |  |  | underpowered |
| R | issue_district_congruence:family:order_justice | 12.000 | 12.000 |  |  |  |  | underpowered |
| D | issue_district_congruence:family:social_liberty_equality | 92.000 | 91.000 | -0.634 | 3.699 | 0.864 |  | estimated |
| R | issue_district_congruence:family:social_liberty_equality | 130.000 | 129.000 | -9.928 | 5.421 | 0.069 |  | estimated |

## Era heterogeneity

| sample | outcome | n | coefficient | cluster_se | p_value | status |
|---|---|---|---|---|---|---|
| D:2008_2014 | candidate_cmo | 61.000 | 2.311 | 6.665 | 0.730 | estimated |
| D:post_2016 | candidate_cmo | 5.000 |  |  |  | underpowered |
| D:pre_2008 | candidate_cmo | 143.000 | 17.307 | 5.165 | 0.001 | estimated |
| R:2008_2014 | candidate_cmo | 83.000 | 2.497 | 12.274 | 0.839 | estimated |
| R:post_2016 | candidate_cmo | 35.000 | -6.522 | 10.513 | 0.539 | estimated |
| R:pre_2008 | candidate_cmo | 80.000 | -2.420 | 12.237 | 0.844 | estimated |
| D:2008_2014 | candidate_federal_overperformance | 51.000 | -2.504 | 10.241 | 0.808 | estimated |
| D:post_2016 | candidate_federal_overperformance | 5.000 |  |  |  | underpowered |
| D:pre_2008 | candidate_federal_overperformance | 131.000 | 22.167 | 6.746 | 0.001 | estimated |
| R:2008_2014 | candidate_federal_overperformance | 66.000 | 10.722 | 18.736 | 0.569 | estimated |
| R:post_2016 | candidate_federal_overperformance | 35.000 | -18.876 | 11.684 | 0.115 | estimated |
| R:pre_2008 | candidate_federal_overperformance | 72.000 | -3.167 | 11.289 | 0.780 | estimated |

## Democratic leave-one-cycle-out stability

| sample | outcome | n | coefficient | cluster_se | p_value | status |
|---|---|---|---|---|---|---|
| D:omit_1998 | candidate_cmo | 151.000 | 16.978 | 5.104 | 0.001 | estimated |
| D:omit_2002 | candidate_cmo | 159.000 | 14.591 | 4.941 | 0.004 | estimated |
| D:omit_2006 | candidate_cmo | 174.000 | 11.775 | 3.877 | 0.003 | estimated |
| D:omit_2010 | candidate_cmo | 172.000 | 17.895 | 4.535 | 0.000 | estimated |
| D:omit_2014 | candidate_cmo | 185.000 | 15.187 | 4.303 | 0.001 | estimated |
| D:omit_2018 | candidate_cmo | 204.000 | 15.173 | 4.115 | 0.000 | estimated |
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
| family:material_support | D | federal_mean | 24.000 | estimated |  |  |  |  |
| family:material_support | D | presidential_mean | 24.000 | estimated | 2.988 | 10.316 | 0.775 | 0.004 |
| family:material_support | R | federal_mean | 16.000 | estimated |  |  |  |  |
| family:material_support | R | presidential_mean | 16.000 | estimated | -0.773 | 8.888 | 0.932 | 0.001 |
| family:order_justice | D | federal_mean | 3.000 | underpowered |  |  |  |  |
| family:order_justice | D | presidential_mean | 3.000 | underpowered |  |  |  |  |
| family:order_justice | R | federal_mean | 3.000 | underpowered |  |  |  |  |
| family:order_justice | R | presidential_mean | 3.000 | underpowered |  |  |  |  |
| family:social_liberty_equality | D | federal_mean | 28.000 | estimated |  |  |  |  |
| family:social_liberty_equality | D | presidential_mean | 28.000 | estimated | 5.295 | 11.391 | 0.646 | 0.008 |
| family:social_liberty_equality | R | federal_mean | 35.000 | estimated |  |  |  |  |
| family:social_liberty_equality | R | presidential_mean | 35.000 | estimated | -11.860 | 7.020 | 0.101 | 0.080 |
| primitive:gun_access | D | federal_mean | 46.000 | estimated |  |  |  |  |
| primitive:gun_access | D | presidential_mean | 46.000 | estimated |  |  |  |  |
| primitive:gun_access | R | federal_mean | 46.000 | estimated | 8.039 | 6.689 | 0.236 | 0.032 |
| primitive:gun_access | R | presidential_mean | 46.000 | estimated |  |  |  |  |
| primitive:gun_purchase_regulation | D | federal_mean | 13.000 | estimated |  |  |  |  |
| primitive:gun_purchase_regulation | D | presidential_mean | 13.000 | estimated | 1.091 | 9.794 | 0.913 | 0.001 |
| primitive:gun_purchase_regulation | R | federal_mean | 24.000 | estimated |  |  |  |  |
| primitive:gun_purchase_regulation | R | presidential_mean | 24.000 | estimated | 4.818 | 4.866 | 0.333 | 0.043 |
| primitive:abortion_access | D | federal_mean | 16.000 | estimated |  |  |  |  |
| primitive:abortion_access | D | presidential_mean | 16.000 | estimated | 6.446 | 8.831 | 0.477 | 0.037 |
| primitive:abortion_access | R | federal_mean | 23.000 | underpowered |  |  |  |  |
| primitive:abortion_access | R | presidential_mean | 23.000 | underpowered |  |  |  |  |
| primitive:marriage_equality | D | federal_mean | 20.000 | underpowered |  |  |  |  |
| primitive:marriage_equality | D | presidential_mean | 20.000 | underpowered |  |  |  |  |
| primitive:marriage_equality | R | federal_mean | 15.000 | underpowered |  |  |  |  |
| primitive:marriage_equality | R | presidential_mean | 15.000 | underpowered |  |  |  |  |
| primitive:civil_social_liberty | D | federal_mean | 26.000 | estimated |  |  |  |  |
| primitive:civil_social_liberty | D | presidential_mean | 26.000 | estimated | 6.999 | 6.183 | 0.269 | 0.051 |
| primitive:civil_social_liberty | R | federal_mean | 29.000 | estimated |  |  |  |  |
| primitive:civil_social_liberty | R | presidential_mean | 29.000 | estimated | -4.800 | 8.478 | 0.576 | 0.012 |
| primitive:christian_sexual_morality | D | federal_mean | 2.000 | underpowered |  |  |  |  |
| primitive:christian_sexual_morality | D | presidential_mean | 2.000 | underpowered |  |  |  |  |
| primitive:christian_sexual_morality | R | federal_mean | 11.000 | underpowered |  |  |  |  |
| primitive:christian_sexual_morality | R | presidential_mean | 11.000 | underpowered |  |  |  |  |
| primitive:racial_civil_rights | D | federal_mean | 3.000 | underpowered |  |  |  |  |
| primitive:racial_civil_rights | D | presidential_mean | 3.000 | underpowered |  |  |  |  |
| primitive:racial_civil_rights | R | federal_mean | 18.000 | underpowered |  |  |  |  |
| primitive:racial_civil_rights | R | presidential_mean | 18.000 | underpowered |  |  |  |  |
| primitive:anti_discrimination | D | federal_mean | 19.000 | estimated |  |  |  |  |
| primitive:anti_discrimination | D | presidential_mean | 19.000 | estimated | 6.298 | 6.067 | 0.314 | 0.060 |
| primitive:anti_discrimination | R | federal_mean | 14.000 | underpowered |  |  |  |  |
| primitive:anti_discrimination | R | presidential_mean | 14.000 | underpowered |  |  |  |  |
| primitive:religion_state | D | federal_mean | 23.000 | underpowered |  |  |  |  |
| primitive:religion_state | D | presidential_mean | 23.000 | underpowered |  |  |  |  |
| primitive:religion_state | R | federal_mean | 18.000 | underpowered |  |  |  |  |
| primitive:religion_state | R | presidential_mean | 18.000 | underpowered |  |  |  |  |
| primitive:criminal_punishment | D | federal_mean | 42.000 | estimated |  |  |  |  |
| primitive:criminal_punishment | D | presidential_mean | 42.000 | estimated | -15.880 | 15.264 | 0.304 | 0.026 |
| primitive:criminal_punishment | R | federal_mean | 43.000 | estimated |  |  |  |  |
| primitive:criminal_punishment | R | presidential_mean | 43.000 | estimated | 24.440 | 21.816 | 0.269 | 0.030 |
| primitive:drug_criminalization | D | federal_mean | 3.000 | underpowered |  |  |  |  |
| primitive:drug_criminalization | D | presidential_mean | 3.000 | underpowered |  |  |  |  |
| primitive:drug_criminalization | R | federal_mean | 3.000 | underpowered |  |  |  |  |
| primitive:drug_criminalization | R | presidential_mean | 3.000 | underpowered |  |  |  |  |
| primitive:due_process | D | federal_mean | 1.000 | underpowered |  |  |  |  |
| primitive:due_process | D | presidential_mean | 1.000 | underpowered |  |  |  |  |
| primitive:due_process | R | federal_mean | 10.000 | underpowered |  |  |  |  |
| primitive:due_process | R | presidential_mean | 10.000 | underpowered |  |  |  |  |
| primitive:market_governance | D | federal_mean | 40.000 | estimated |  |  |  |  |
| primitive:market_governance | D | presidential_mean | 40.000 | estimated |  |  |  |  |
| primitive:market_governance | R | federal_mean | 42.000 | estimated |  |  |  |  |
| primitive:market_governance | R | presidential_mean | 42.000 | estimated | 6.282 | 7.222 | 0.390 | 0.019 |
| primitive:tax_burden | D | federal_mean | 17.000 | estimated |  |  |  |  |
| primitive:tax_burden | D | presidential_mean | 17.000 | estimated | 13.735 | 12.052 | 0.272 | 0.080 |
| primitive:tax_burden | R | federal_mean | 15.000 | estimated |  |  |  |  |
| primitive:tax_burden | R | presidential_mean | 15.000 | estimated |  |  |  |  |
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
| primitive:welfare_generosity | D | federal_mean | 21.000 | estimated |  |  |  |  |
| primitive:welfare_generosity | D | presidential_mean | 21.000 | estimated | 3.787 | 10.383 | 0.719 | 0.007 |
| primitive:welfare_generosity | R | federal_mean | 15.000 | estimated |  |  |  |  |
| primitive:welfare_generosity | R | presidential_mean | 15.000 | estimated | -0.456 | 5.568 | 0.936 | 0.001 |
| primitive:welfare_conditionality | D | federal_mean | 18.000 | underpowered |  |  |  |  |
| primitive:welfare_conditionality | D | presidential_mean | 18.000 | underpowered |  |  |  |  |
| primitive:welfare_conditionality | R | federal_mean | 16.000 | underpowered |  |  |  |  |
| primitive:welfare_conditionality | R | presidential_mean | 16.000 | underpowered |  |  |  |  |
| primitive:labor_capital_alignment | D | federal_mean | 21.000 | underpowered |  |  |  |  |
| primitive:labor_capital_alignment | D | presidential_mean | 21.000 | underpowered |  |  |  |  |
| primitive:labor_capital_alignment | R | federal_mean | 11.000 | underpowered |  |  |  |  |
| primitive:labor_capital_alignment | R | presidential_mean | 11.000 | underpowered |  |  |  |  |
| primitive:labor_rights | D | federal_mean | 5.000 | underpowered |  |  |  |  |
| primitive:labor_rights | D | presidential_mean | 5.000 | underpowered |  |  |  |  |
| primitive:labor_rights | R | federal_mean | 8.000 | underpowered |  |  |  |  |
| primitive:labor_rights | R | presidential_mean | 8.000 | underpowered |  |  |  |  |
| primitive:public_employee_compensation | D | federal_mean | 22.000 | underpowered |  |  |  |  |
| primitive:public_employee_compensation | D | presidential_mean | 22.000 | underpowered |  |  |  |  |
| primitive:public_employee_compensation | R | federal_mean | 34.000 | underpowered |  |  |  |  |
| primitive:public_employee_compensation | R | presidential_mean | 34.000 | underpowered |  |  |  |  |
| primitive:education_public_funding | D | federal_mean | 33.000 | estimated |  |  |  |  |
| primitive:education_public_funding | D | presidential_mean | 33.000 | estimated | -9.194 | 21.240 | 0.668 | 0.006 |
| primitive:education_public_funding | R | federal_mean | 39.000 | estimated |  |  |  |  |
| primitive:education_public_funding | R | presidential_mean | 39.000 | estimated | -1.494 | 9.127 | 0.871 | 0.001 |
| primitive:education_market_choice | D | federal_mean | 13.000 | underpowered |  |  |  |  |
| primitive:education_market_choice | D | presidential_mean | 13.000 | underpowered |  |  |  |  |
| primitive:education_market_choice | R | federal_mean | 34.000 | estimated |  |  |  |  |
| primitive:education_market_choice | R | presidential_mean | 34.000 | estimated | -7.078 | 27.903 | 0.801 | 0.002 |
| primitive:environmental_protection | D | federal_mean | 14.000 | estimated |  |  |  |  |
| primitive:environmental_protection | D | presidential_mean | 14.000 | estimated | 0.140 | 8.183 | 0.987 | 0.000 |
| primitive:environmental_protection | R | federal_mean | 13.000 | estimated |  |  |  |  |
| primitive:environmental_protection | R | presidential_mean | 13.000 | estimated | -8.905 | 6.244 | 0.182 | 0.156 |
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
| primitive:immigration_enforcement | D | federal_mean | 7.000 | underpowered |  |  |  |  |
| primitive:immigration_enforcement | D | presidential_mean | 7.000 | underpowered |  |  |  |  |
| primitive:immigration_enforcement | R | federal_mean | 12.000 | underpowered |  |  |  |  |
| primitive:immigration_enforcement | R | presidential_mean | 12.000 | underpowered |  |  |  |  |
| primitive:healthcare_access | D | federal_mean | 32.000 | estimated |  |  |  |  |
| primitive:healthcare_access | D | presidential_mean | 32.000 | estimated | 14.682 | 6.943 | 0.043 | 0.130 |
| primitive:healthcare_access | R | federal_mean | 26.000 | estimated |  |  |  |  |
| primitive:healthcare_access | R | presidential_mean | 26.000 | estimated | -9.502 | 6.496 | 0.156 | 0.082 |
| primitive:government_ethics_transparency | D | federal_mean | 23.000 | estimated |  |  |  |  |
| primitive:government_ethics_transparency | D | presidential_mean | 23.000 | estimated | 3.579 | 3.998 | 0.381 | 0.037 |
| primitive:government_ethics_transparency | R | federal_mean | 32.000 | estimated |  |  |  |  |
| primitive:government_ethics_transparency | R | presidential_mean | 32.000 | estimated | 7.491 | 3.953 | 0.068 | 0.107 |
| primitive:voting_access | D | federal_mean | 14.000 | underpowered |  |  |  |  |
| primitive:voting_access | D | presidential_mean | 14.000 | underpowered |  |  |  |  |
| primitive:voting_access | R | federal_mean | 10.000 | underpowered |  |  |  |  |
| primitive:voting_access | R | presidential_mean | 10.000 | underpowered |  |  |  |  |

## Interpretation rules

- Party-specific estimates are primary; pooled convergence is descriptive only.
- Federal and presidential outcomes are the primary durability tests.
- Incumbency and finance are reported both as mechanisms and controls, never silently absorbed into expected performance.
- Sparse issue families and era cells remain underpowered even when point estimates are large.
- Shor scores are absolute and nationally bridged, but are career scores observed only for people who served.
- No estimate in this report is automatically eligible for the production forecast.
- Candidate margins already encode the arithmetic behind the crossover intuition: moving one voter from the opponent changes the two-party margin twice as much as adding one same-party voter. Aggregate results cannot identify whether an observed margin gain actually came from persuasion or differential turnout.
