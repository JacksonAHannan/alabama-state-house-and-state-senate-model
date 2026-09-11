# Combined Southern historical CMO validation

**Task:** `VALIDATE-CMO-SOUTHERN-COMBINED-001`  
**Date:** 2026-08-22  
**Verdict:** **PASS for experimental analytical use, with portability caveats.**

## Independent rebuild and tests

I rebuilt the existing tournament implementation against the combined panel
and its manifest in a new absolute temporary directory, then repeated the
build at the same path.

```powershell
python scripts/run_historical_southern_cmo_tournament.py `
  --panel data/processed/forecast_calibration/historical_southern_combined_panel.csv `
  --panel-manifest data/processed/forecast_calibration/historical_southern_combined_manifest.json `
  --output <absolute-temp>

python -m pytest scripts/tests/test_combined_historical_southern_cmo.py scripts/tests/test_historical_southern_cmo_tournament.py -q
```

All six CSV outputs are byte-identical to the release candidate. The manifest
is byte-identical on a repeated same-path build. Focused/shared tests:
**5 passed**.

## Sample and output cardinality

- Strict combined input rows: **2,273**.
- HEDA-source input rows: 1,805.
- Additive OpenElections-source input rows: 468 (Missouri 425, Georgia 43).
- Input key duplicates: 0.
- `partial_unresolved` input rows: 0.
- Cross-validated prediction rows: **28,770**.
- Prediction key duplicates across fold/model/race: 0.
- Candidate residual rows: **4,546**, exactly two per input race.
- Candidate key duplicates `(state, year, chamber, district, party)`: 0.

## Fold isolation

Forward-year folds are 2004, 2006, 2008, 2010, 2012, and 2016. For every
model/fold combination, the test rows contain exactly the named year, the
recorded training count equals all strict rows from earlier years, and no
current or future observation enters training.

The leave-state-out evaluation contains ten held-out states. Every test fold
contains only its named state, its training count equals all rows outside that
state, and the held-out state has zero training observations.

An independent rerun of all folds reproduces every prediction key and all
predicted gaps, margins, and residuals to floating-point precision. The maximum
observed numerical difference is `1.42e-14`.

## Metrics and declared selection rule

I recomputed fold rows, MAE, RMSE, bias, winner accuracy, and whole-precinct
RMSE from the prediction file. Every published metric matches. Recomputing the
summary and ranking independently selects `full_temporal`.

| Model | Forward RMSE | LOSO RMSE | Whole-precinct LOSO RMSE | Guardrail | Selected |
|---|---:|---:|---:|---|---|
| full_temporal | 15.574 | 16.090 | 14.750 | pass | yes |
| state_chamber_incumbency | 14.725 | 18.504 | 17.444 | pass | no |
| symmetric_incumbency | 15.124 | 18.694 | 17.980 | pass | no |
| portable_temporal | 15.964 | 15.254 | 14.080 | fail | no |
| state_chamber_lag | 16.328 | 20.433 | 20.425 | fail | no |
| pooled_lag | 17.213 | 20.794 | 21.227 | fail | no |
| baseline_only | 18.142 | 23.592 | 24.339 | fail | no |

The best forward RMSE is 14.724820, making the one-point threshold 15.724820.
`portable_temporal` misses it by 0.239246 despite having the best LOSO RMSE.
Among the three qualifying models, `full_temporal` has the lowest LOSO RMSE.
The stored selection therefore follows the declared rule exactly; no
sensitivity or complexity tiebreak is needed.

## Candidate symmetry and fitted contrasts

Candidate residuals use only `full_temporal` leave-state-out predictions.
Within every race, D and R candidate-quality residuals, actual margins, and
expected margins are exact sign reversals. Recomputing the complete candidate
file independently reproduces all residuals.

The selected-effect file also reproduces exactly:

| Descriptive contrast | Margin points |
|---|---:|
| Democratic incumbent | +12.964744 |
| Republican incumbent | -12.964744 |
| two-year time change | -0.448105 |
| ten-point baseline shift on downballot gap | -2.231575 |

These are fitted model contrasts, not causal candidate or incumbency effects.

## Methodology comparison claims

The model note's numerical claims reconcile:

- `full_temporal` mean winner accuracy is 85.576% forward and 84.093% LOSO,
  supporting the displayed 85.6% and 84.1%.
- Relative to `baseline_only`, it reduces forward RMSE by 2.567 points and LOSO
  RMSE by 7.503 points (the note's 2.568 forward difference reflects rounding
  displayed component values rather than the unrounded subtraction).
- The HEDA-only run's `portable_temporal` forward RMSE is 15.547956 versus
  15.964066 here, a 0.416110-point deterioration.
- Its LOSO change is only about +0.035 points; `full_temporal` changes by about
  +0.126 points, consistent with the note's “changes little” description.
- All 468 additions are Missouri or Georgia rows, and 425 (90.8%) are Missouri,
  substantiating the concentration warning.
- Strict combined coverage begins in 2000 and still lacks 1994–1998.

The note appropriately characterizes the model-selection change as cycle-mix
sensitivity, not proof that state effects transport to Alabama.

## Manifest

The expected build ID from the current combined-panel manifest and current
tournament script is `105a8ed0bd6caffac3e2`, exactly matching the release
manifest. Panel and panel-manifest input hashes reconcile. The selected model
and row counts (2,273 input, 28,770 predictions, 4,546 candidate residuals)
match. All six output byte sizes and SHA-256 hashes reconcile.

## Disposition and caveats

The combined tournament is approved for exploratory historical analysis. It
does not replace Alabama CMO or the production forecast. Important limits
remain:

- all outcomes/baselines are derived from secondary-source inputs;
- the 468 additions are geographically unbalanced toward Missouri;
- only six forward test folds are available, with a gap between 2012 and 2016;
- the selected state-aware model cannot learn a held-out state's state effect
  in LOSO evaluation and may not transport to Alabama 2026; and
- candidate residuals are descriptive cross-fitted errors, not standalone
  causal measures of candidate quality.
