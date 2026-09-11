# Strategic social moderation and Democratic CMO

## Design

The analysis contains **99 Democratic contested candidate-cycles** with adjudicated ontology-v3 social positions. Positive social scores indicate liberty/equality or more progressive positioning; negative scores indicate traditional/restrictive positioning. Selection-aware out-of-fold Total CMO is the candidate-strength outcome. Incumbency, prior candidate performance, and campaign finance are not primary controls because they can be downstream of candidate strength.

The primary models use HC3 heteroskedasticity-robust uncertainty. Every observed candidate in this social-position sample is unique, so candidate-clustered errors would be identical to clustering on singleton groups. Missing ideology is never coded as moderation. All 71 social-family profiles in the analysis contain same-cycle candidate-questionnaire evidence; none depends on post-election legislative-roll-call evidence.

## Results

In the cycle-and-chamber-adjusted primary model, moving one full unit toward social progressivism is associated with **-15.88 CMO points** (95% CI -24.95 to -6.82; p=0.001; n=99).

The direct moderate-versus-strong-progressive comparison estimates the strong-progressive penalty at **-3.04 CMO points** relative to moderates (95% CI -23.62 to 17.54; p=0.772; n=50).

The social-position by prior-presidential-margin interaction is **0.15** (95% CI -0.28 to 0.59; p=0.487). A positive interaction would mean progressivism is less costly in more Democratic districts.

These are observational estimates. They test whether the evidence is consistent with the strategic-moderation hypothesis; they do not by themselves prove that changing a candidate's position would cause the estimated vote change.

## Social-position bands

| social_band | candidate_cycles | mean_cmo | median_cmo | mean_social_score |
| --- | --- | --- | --- | --- |
| moderate | 25.000 | 13.295 | 14.930 | -0.074 |
| progressive | 13.000 | 0.244 | -7.659 | 0.385 |
| strong_progressive | 25.000 | 1.093 | -0.133 | 0.868 |
| traditional | 36.000 | 25.985 | 30.521 | -0.590 |

## Progressive-threshold sensitivity

| progressive_cutoff | moderate_n | progressive_n | n | estimate | std_error | p_value | ci_low | ci_high |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.350 | 26.000 | 33.000 | 59.000 | -8.956 | 8.120 | 0.270 | -24.871 | 6.958 |
| 0.400 | 26.000 | 29.000 | 55.000 | -6.803 | 9.593 | 0.478 | -25.606 | 11.999 |
| 0.500 | 26.000 | 25.000 | 51.000 | -2.171 | 10.520 | 0.837 | -22.790 | 18.449 |
| 0.600 | 26.000 | 21.000 | 47.000 | -14.694 | 10.023 | 0.143 | -34.339 | 4.951 |
| 0.750 | 26.000 | 17.000 | 43.000 | -12.880 | 11.587 | 0.266 | -35.590 | 9.830 |

## Issue-specific exploratory models

| primitive_axis | n | estimate | std_error | p_value | ci_low | ci_high | bh_q_value |
| --- | --- | --- | --- | --- | --- | --- | --- |
| civil_social_liberty | 110.000 | -12.551 | 2.873 | 0.000 | -18.182 | -6.920 | 0.000 |
| abortion_access | 108.000 | -13.927 | 3.876 | 0.000 | -21.525 | -6.330 | 0.001 |
| marriage_equality | 58.000 | -19.545 | 6.722 | 0.004 | -32.720 | -6.369 | 0.005 |
| anti_discrimination | 79.000 | -5.687 | 4.201 | 0.176 | -13.922 | 2.548 | 0.176 |

Issue-specific models use every Democratic CMO candidate with that exact-cycle issue score; unlike the broad composite, they do not require a second social issue. P-values are accompanied by Benjamini-Hochberg false-discovery-rate q-values and should not be read as independent confirmatory tests.

## Model inventory

| model | formula | n | r_squared | adjusted_r_squared | covariance |
| --- | --- | --- | --- | --- | --- |
| linear_unadjusted | cmo ~ social_progressivism | 99.000 | 0.182 | 0.174 | HC3 |
| linear_cycle_chamber | cmo ~ social_progressivism + C(year) + C(chamber) | 99.000 | 0.320 | 0.259 | HC3 |
| nonlinear_cycle_chamber | cmo ~ social_progressivism + social_progressivism_sq + C(year) + C(chamber) | 99.000 | 0.323 | 0.255 | HC3 |
| linear_context | cmo ~ social_progressivism + prior_pres_dem_margin + nonwhite_share + white_college_share + C(era) + C(chamber) | 65.000 | 0.277 | 0.216 | HC3 |
| nonlinear_context | cmo ~ social_progressivism + social_progressivism_sq + prior_pres_dem_margin + nonwhite_share + white_college_share + C(era) + C(chamber) | 65.000 | 0.317 | 0.246 | HC3 |
| district_congruence | cmo ~ social_progressivism + prior_pres_dem_margin + social_x_prior_pres + nonwhite_share + white_college_share + C(era) + C(chamber) | 65.000 | 0.282 | 0.208 | HC3 |
| measurement_sensitivity | cmo ~ social_progressivism + prior_pres_dem_margin + nonwhite_share + white_college_share + log_evidence_records + ideology_v3_max_conflict_ratio + C(era) + C(chamber) | 65.000 | 0.286 | 0.199 | HC3 |
| material_support_sensitivity | cmo ~ social_progressivism + ideology_v3_material_support + prior_pres_dem_margin + nonwhite_share + white_college_share + C(era) + C(chamber) | 47.000 | 0.289 | 0.182 | HC3 |
| moderate_vs_strong_progressive | cmo ~ strong_progressive + C(era) + C(chamber) | 50.000 | 0.295 | 0.233 | HC3 |
