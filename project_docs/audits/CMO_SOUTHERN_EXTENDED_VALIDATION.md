# Extended historical Southern CMO tournament validation

**Verdict: PASS for experimental comparative use**

The Arkansas-extended tournament independently rebuilds, preserves strict temporal and state isolation, applies the declared one-point forward guardrail correctly, and produces complete symmetric candidate residuals. All published metrics, effects, comparison claims, hashes, and counts reconcile.

## Reproduction and tests

```powershell
python scripts/run_historical_southern_cmo_tournament.py `
  --panel "C:\Users\User\Documents\GitHub\alabama-state-house-and-state-senate-model\data\processed\forecast_calibration\historical_southern_extended_panel.csv" `
  --panel-manifest "C:\Users\User\Documents\GitHub\alabama-state-house-and-state-senate-model\data\processed\forecast_calibration\historical_southern_extended_manifest.json" `
  --output "C:\Users\User\Documents\GitHub\alabama-state-house-and-state-senate-model\.validation_tmp\cmo_southern_extended"
python -m pytest scripts/tests/test_historical_southern_cmo_tournament.py scripts/tests/test_extended_historical_southern_cmo.py -q
```

The rebuild reports exactly 2,383 strict input rows, 31,934 prediction rows, and 4,766 candidate residual rows. All six CSV outputs are byte-identical to the release candidate. Two consecutive builds to the same path produced the same manifest SHA-256, `71a53be2e27279960d6399c0f058dcef56b9682830d9287bdd8ae1aa68151e62`.

The contracted shared and extended tests pass:

```text
5 passed in 1.27s
```

## Fold isolation and prediction coverage

I independently reconstructed the expected membership and training-row count for every model/fold pair.

- Forward-year folds are 2002, 2004, 2006, 2008, 2010, 2012, and 2016.
- Every forward prediction tests only its named year.
- Every forward training count equals the number of strict rows with `year < test year`.
- Each forward fold has at least two distinct prior training cycles and at least 200 training rows.
- Leave-state-out folds are AL, AR, FL, GA, KY, MO, NC, OK, SC, TN, and TX.
- Every LOSO prediction tests only the named state, and every recorded training count equals all strict rows outside that state.
- All seven specifications cover every eligible row in every applicable fold.
- There are no duplicate model/fold/race prediction keys.

Thus Arkansas rows cannot train their Arkansas LOSO predictions, and no future cycle trains an earlier forward-year prediction.

## Metrics and selection

I recomputed fold-level MAE, RMSE, bias, winner accuracy, whole-precinct RMSE, and the unweighted mean across folds. Published values reproduce within `3.56e-15` floating-point precision.

| Model | Forward RMSE | LOSO RMSE | Whole-precinct LOSO RMSE | Guardrail | Selected |
|---|---:|---:|---:|---|---|
| portable temporal | 14.277671 | 15.084043 | 14.063935 | pass | yes |
| full temporal | 13.876470 | 16.588902 | 14.594645 | pass | no |
| state/chamber/incumbency | 14.757278 | 18.847978 | 17.532960 | pass | no |
| symmetric incumbency | 15.060649 | 18.791238 | 18.144787 | fail | no |
| state/chamber lag | 16.361765 | 20.444138 | 20.505284 | fail | no |
| pooled lag | 17.017356 | 20.503411 | 21.305099 | fail | no |
| baseline only | 17.852471 | 22.736686 | 24.338844 | fail | no |

The best forward RMSE is `13.876470`, so the declared threshold is `14.876470`. Portable-temporal is 0.401201 points behind the forward leader and passes. Among passing models, it has the lowest LOSO RMSE, so it is correctly selected before the whole-precinct and simplicity tie-breakers are needed. Both the ranking and manifest select `portable_temporal` exactly once.

## Candidate residuals

- The candidate file has exactly two rows for each of the 2,383 race keys: one Democratic and one Republican.
- Its 4,766 state/year/chamber/district/party keys are unique and complete.
- Democratic and Republican candidate-quality residuals sum to zero for every race, with zero numerical discrepancy.
- Rejoining to the selected-model LOSO predictions confirms `D residual = race residual` and `R residual = -race residual` for every row.
- Candidate actual and expected margins use the same symmetric party orientation.

These are cross-validated residuals, not causal or persistent candidate effects.

## Selected-model effects and report claims

The fully fitted selected model yields:

- Democratic incumbent effect: `+13.916041` margin points;
- Republican incumbent effect: `-13.916041` margin points;
- average two-year time effect: `+0.409397` points; and
- ten-point Democratic-baseline effect on the gap: `-2.923681` points.

The report's rounded 13.916, +0.409, and -2.924 values are accurate and appropriately labeled descriptive rather than causal.

The benchmark comparison also reconciles:

- the 2,273-row run selected `full_temporal`;
- its portable-temporal forward RMSE was 15.964066 versus 14.277671 now;
- its portable-temporal LOSO RMSE was 15.253875 versus 15.084043 now;
- relative to the extended baseline-only model, portable-temporal improves forward RMSE by 3.574800 and LOSO RMSE by 7.652643; and
- the text's rounded 0.401, 3.575, and 7.653 comparisons are correct.

## Provenance and output integrity

The manifest's panel hash matches the current validated 2,383-row panel: `6fcc43c63224af67ed73168daaeb2f8a6dc027c5e76ff6594a9eca678ebb6493`. Its panel-manifest hash also matches: `b33b9175358d18b13299e3da05eabbef5c0aa775b9d1f6315723941e39777eb4`.

Output hashes independently reproduce:

- predictions: `dd36964d986940b0de45fb7ab554ae0b1537851aee75fd3ca2b86c4077d5c7f2`
- metrics: `6cbc42a1519a3ed3e5868d2f6b37ad7f316b3d07ea8d89bf5b8f19cce0f179b9`
- summary: `5dc9819b6fac62f60de6a264027a8f063a23284e4bb2a0606e3629a7c396d48a`
- ranking: `e5221e632c2a64b4117fbb7cc83e780617fcd6aa06049c4edbb5682219206219`
- candidate residuals: `1655d89c8734696b3f066955ddf54cd769dbb627733bf8752c557b27658279cb`
- selected effects: `4774064c0ff3bc4870f193c362358aa436cfbedcab8329a800d56b3b74107e2d`

Each generated byte count and hash agrees with the manifest. The deterministic build ID is `ca4433d67ebea2fee0a5`.

## Approval and caveats

This run is approved as an **experimental historical model comparison and candidate-residual diagnostic**. It does not by itself authorize promotion into the Alabama production forecast.

The portability result is sensitive to represented states and cycles: 110 additions come solely from Arkansas before 2000, while the underlying context footprint is uneven. Fold metrics are means across folds rather than row-weighted national performance. The incumbent and time coefficients are descriptive fitted contrasts, and the LOSO candidate residual is still a one-election error term rather than proof of durable candidate quality.
