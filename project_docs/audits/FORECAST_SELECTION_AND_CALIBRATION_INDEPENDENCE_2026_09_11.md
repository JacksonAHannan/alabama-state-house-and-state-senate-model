# Forecast structural selection and calibration independence — 2026-09-11

Checklist `forecast-07` (structural-model selection against evidence),
`forecast-08` (calibration and evaluation independence) and evidence toward
`forecast-09` (uncertainty diagnostics). Read-only audit of the published
bundle `368bb272a990ff436e56` (`data/processed/forecast_calibration/`) and its
producer `scripts/run_alabama_war_generic_forecast.py`. Nothing was rebuilt or
published by this audit.

## forecast-07 — structural selection

- Manifest: `selection_reason = owner_required_war_structural_expectation_with_generic_ballot_environment`,
  `structural_selection_policy = owner_selected; forward validation retained as advisory`,
  `structural_applied = true`, `war_structural_specification = decaying_lag`, ridge alpha 100.
- Sole direct Alabama holdout (`alabama_war_forecast_v1_forward_metrics.csv`):
  train 2,039 post-2016 Southern races before 2022, test 33 Alabama 2022 races.
  Generic-ballot baseline MAE 7.072 / RMSE 9.265; owner-required structural
  specification MAE 7.651 / RMSE 9.187 (MAE worse by 0.58, RMSE better by 0.08,
  winner accuracy 0.970 vs 1.000).
- Disposition: the selection is recorded as an owner override, not as
  validation-selected, on the page, the methodology, the field contract and the
  generated validation audit (E1/E8 edits, 2026-09-11). Its limitation (single
  33-race holdout, only 4 races within 10 points) is stated. Accepted as
  "approved selection recorded with limitations".

## forecast-08 — calibration and evaluation independence

Implemented procedure (`run_alabama_war_generic_forecast.py::forward_test`,
`probability_scale`): the point forecast for the 2022 holdout is out-of-sample
(structural fit on races before 2022). The probability layer is **not**: the
Student-t(5) scale is chosen by minimising the Brier score of the structural
prediction **on the same 33 holdout races**, then reported Brier (0.0051) is
the in-sample optimum of that search. The `df = 5` is fixed by choice, not
selected. No second Alabama holdout exists; the historical panel's other cycles
(2018) fall inside the WAR training window, so no independent probability
evaluation can be constructed from Alabama data alone.

### Finding: the selected scale is the search-grid boundary and is overconfident

- The grid is 2.0–15.0 in 0.25 steps (53 values); Brier is monotone increasing
  in scale on this holdout because all 33 winners are correctly ordered by the
  point forecast (winner accuracy 1.000) and only 4 races were decided by fewer
  than 10 points. The optimum is therefore the **lower bound, 2.0**.
- Holdout residual RMSE is 9.19 (SD 9.33). At scale 2.0 the nominal 80%
  Student-t(5) interval has half-width 3.0 points and covers **18%** of holdout
  residuals; at scale 5.0, 58%; at scale ≈ RMSE (9.19), 88%.
- Effect on the 2026 headline (48 modeled races): with scale 2.0 no race carries a
  Democratic win probability between 0.10 and 0.90 and the expected Democratic
  seat count is 12.1; at scale 9.19 four races would be in that band and the
  expectation is 12.4. Chamber seat distributions are simulated from separate
  national/state/chamber/district error components
  (`robust_forecast_v1_error_components.csv`) and are not driven by this scale;
  the per-district probabilities, intervals and rating labels on the public page
  are.

The public page and methodology currently describe probabilities as
"Student-t(5) with a 2.00-point scale chosen on that single holdout; that
limited probability sample is a material uncertainty" — true, but they do not
state that the scale sits at the grid boundary or that the implied intervals
under-cover by this margin.

### Options for the owner (no change made)

1. **Select the scale on margin residuals, not binary outcomes**: choose the
   Student-t(5) scale that maximises the likelihood of the 33 holdout residuals
   (or matches the 80% empirical coverage); this yields a scale near 9 and is
   still a single-holdout estimate, but it is identified by the residual spread
   rather than by the absence of close races. Requires a producer change, a
   forecast rebuild, updated methodology text and republication.
2. **Fix the scale to the forward RMSE by contract** (9.19 for this build):
   simplest, transparent, no optimisation on the holdout at all.
3. **Keep 2.0 and disclose** the boundary and coverage numbers on the page and
   in the field contract; district probabilities remain sharp.

Options 1 and 2 change published probabilities and ratings for the 4 competitive
2026 races and widen displayed intervals everywhere; seat expectations are
essentially unchanged.

## forecast-09 evidence collected here

- Interval coverage at the selected scale: 18% (nominal 80%) on the only holdout.
- Time-forward margin error: MAE 7.65 / RMSE 9.19 on 33 races.
- Shared-error assumptions: national SD 2.20 and state/chamber/district
  components from `robust_forecast_v1_error_components.csv` (legacy-named live
  input; provenance flagged in `FORECAST_POLLING_SNAPSHOT_POLICY_2026_09_11.md`).
- 50,000 draws are a computational choice, not additional evidence.

## Not established

Any out-of-sample evaluation of the probability layer; Alabama-specific validity
of the national-to-Alabama transfer; the effect of options 1–2 on ratings until
rebuilt.
