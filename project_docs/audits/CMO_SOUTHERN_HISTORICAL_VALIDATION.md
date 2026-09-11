# Historical Southern CMO tournament validation

**Task:** `VALIDATE-CMO-SOUTHERN-HISTORICAL-001`  
**Date:** 2026-08-22  
**Verdict:** **PASS for experimental analytical use.**

## Independent rebuild

I rebuilt the tournament into a new absolute temporary directory and repeated
the build at the same path.

```powershell
python scripts/run_historical_southern_cmo_tournament.py --output <absolute-temp>
python -m pytest scripts/tests/test_historical_southern_cmo_tournament.py scripts/tests/test_historical_southern_legislative_panel.py -q
```

All six CSV outputs are byte-identical to the release candidate. The manifest
is deterministic when rebuilt at the same path; a temporary manifest naturally
differs from the release manifest in its recorded output paths. Focused tests:
**7 passed**.

## Input sample

- The input panel contains 2,141 permissive rows and 1,805 strict rows.
- The tournament reads exactly the **1,805** rows with `model_eligible = True`.
- No input row is `partial_unresolved`.
- Tournament predictions contain 21,224 rows across all seven registered model
  specifications. Prediction keys `(fold_type, fold, model, state, year,
  chamber, district)` have zero duplicates.

## Fold isolation

Forward-year folds are 2006, 2008, 2010, and 2012. For every model and fold:

- test rows have exactly the named fold year;
- the recorded training-row count equals the number of strict rows with an
  earlier year; and
- every training year is strictly less than the test year.

The leave-state-out evaluation contains ten held-out states. For every state
and model:

- test rows contain only the named held-out state;
- the recorded training-row count equals all strict rows outside that state;
  and
- the held-out state has zero training observations.

An independent rerun of `cross_validated_predictions` reproduced every key and
all predicted gaps, margins, and residuals to floating-point precision (maximum
observed numerical difference `1.42e-14`).

## Metrics and selection

I recomputed fold rows, MAE, RMSE, bias, winner accuracy, and whole-precinct
RMSE from the published predictions. Every value matches the metrics output.
The summary and ranking recomputation independently selects
`portable_temporal`.

| Model | Forward RMSE | LOSO RMSE | LOSO whole-precinct RMSE | Forward guardrail |
|---|---:|---:|---:|---|
| portable_temporal | 15.548 | 15.219 | 14.027 | pass |
| full_temporal | 15.360 | 15.964 | 14.608 | pass |
| state_chamber_incumbency | 15.469 | 18.379 | 17.517 | pass |
| symmetric_incumbency | 15.510 | 18.391 | 17.884 | pass |
| state_chamber_lag | 17.378 | 20.202 | 20.387 | fail |
| pooled_lag | 17.486 | 20.268 | 20.850 | fail |
| baseline_only | 19.655 | 23.364 | 24.339 | fail |

The best forward RMSE is 15.360. Four models fall within the required
one-point guardrail; `portable_temporal` has the lowest leave-state-out RMSE
among them, so its selection follows the documented rule. Whole-precinct LOSO
error and simplicity are not needed to break this result but are present.

## Candidate construction and effects

The candidate file contains exactly 3,610 rows, two for every strict race, from
the selected model's leave-state-out predictions only. Keys `(state, year,
chamber, district, party)` are unique. Within every race:

- Democratic and Republican quality residuals are exact sign reversals;
- actual candidate margins are exact sign reversals; and
- expected candidate margins are exact sign reversals.

Recomputing the candidate file independently reproduces all quality residuals.

The selected-effect output also reproduces exactly:

| Effect | Margin points |
|---|---:|
| Democratic incumbent | +13.828680 |
| Republican incumbent | -13.828680 |
| two-year time change | +0.595487 |
| ten-point baseline shift on gap | -3.110564 |

The equal and opposite incumbency effects follow from the symmetric balance
construction. They remain descriptive model contrasts, not causal estimates.

## Manifest

The expected build ID recomputed from the current panel-manifest and tournament
script hashes is `e681e1cc341a62f66226`, exactly matching the release manifest.
The manifest's panel CSV hash, panel-manifest hash, selected model, configuration,
and row counts (1,805 input, 21,224 predictions, 3,610 candidate residuals) all
match. Every one of its six output sizes and SHA-256 hashes reconciles to disk.

## Disposition

The tournament is approved for the documented exploratory cross-state
historical analysis. It does not replace Alabama CMO or the production
forecast. Selection rests on four forward folds across six available cycles,
state errors remain substantial, and the candidate residuals must not be
described as causal candidate effects.
