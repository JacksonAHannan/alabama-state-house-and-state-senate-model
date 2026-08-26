# CMO methodology v5: observed overperformance and candidate WAR

## Two estimands

**Direct CMO** is the candidate-oriented legislative margin minus the selected same-cycle ticket margin. It is observed overperformance and is never residualized for incumbency, fundraising, demographics, or candidate history.

**Wins Above Replacement (WAR)** is the public name for the partial-pooled candidate effect from the direct gap after cycle/chamber/source replacement levels and the selected predetermined structural specification (`cycle_centered`). The candidate ridge penalty is 1. The internal `candidate_quality_index` field is retained as a stable compatibility column; it does not denote a second public measure.

## Downballot lag

Current same-cycle federal margin appears only in the ticket baseline. Lag features use prior presidential margins and presidential changes completed before the legislative election. The former `federal_t - presidential_t-1` predictor is prohibited because it algebraically reused the baseline inside the outcome.

## Incumbency

Total WAR retains officeholding as part of electoral value. An intrinsic sensitivity subtracts a prespecified 3-point generic officeholding effect before estimating candidate effects. Fundraising is not subtracted from either score.

## Identity and isolated races

Literal `Last, First` source names are reordered before model-local longitudinal linkage; surname-only records remain race-specific. A disconnected race containing two one-time candidates identifies only their differential. Both candidates are marked `pair_differential_only` and `uncertain` rather than receiving directional quality labels.

## Mike Curtis audit

| cycle | chamber | district | candidate_direct_cmo | candidate_quality_index | candidate_quality_low | candidate_quality_high | quality_status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2010.000 | house | 2.000 | 19.531 | 3.626 | -12.455 | 19.708 | uncertain |
| 2014.000 | senate | 1.000 | 10.533 | 3.626 | -12.455 | 19.708 | uncertain |

## Interpretation

Direct CMO describes a candidate-cycle. CQI estimates a repeatable candidate component but cannot uniquely distinguish candidate strength from opponent weakness in a singleton race. Intervals and reliability are mandatory; `uncertain` is not a neutral-quality finding.
