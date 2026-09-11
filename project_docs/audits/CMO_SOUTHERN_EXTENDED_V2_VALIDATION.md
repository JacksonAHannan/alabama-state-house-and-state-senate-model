# Tennessee-extended Southern CMO tournament validation

**Verdict: PASS for experimental cross-state calibration.**

The review candidate deterministically applies the unchanged seven-model tournament to the validated 2,402-row Tennessee-extended panel. Fold isolation, selection, metrics, effects, candidate symmetry, Tennessee propagation, and provenance all reconcile independently.

## Independent commands

```powershell
python scripts/run_historical_southern_cmo_tournament.py `
  --panel "C:\Users\User\Documents\GitHub\alabama-state-house-and-state-senate-model\data\processed\forecast_calibration\historical_southern_extended_v2_panel.csv" `
  --panel-manifest "C:\Users\User\Documents\GitHub\alabama-state-house-and-state-senate-model\data\processed\forecast_calibration\historical_southern_extended_v2_manifest.json" `
  --output "C:\Users\User\Documents\GitHub\alabama-state-house-and-state-senate-model\.validation_tmp\cmo_southern_extended_v2"

python -m pytest `
  scripts/tests/test_extended_v2_historical_southern_cmo.py `
  scripts/tests/test_historical_southern_cmo_tournament.py -q
```

The focused and generic suites pass 6/6. Two complete temporary rebuilds produce identical files and manifest SHA-256 `45f81b856475c35a1ca8d5bba45f185b0269da7e0501f85d32820a9ab5939645`. Build ID is `7046318246201891028d`.

## Counts, keys, and Tennessee propagation

- Strict input contests: 2,402.
- Fold predictions: 32,067.
- Candidate residual observations: 4,804.
- Prediction keys are unique by model, fold type, fold, and contest.
- Candidate keys are unique by state, year, chamber, district, and party.
- All 19 admitted Tennessee 1998 contests reach selected-model output as exactly 38 candidate rows: 15 House and four Senate contests, each represented once for D and once for R.
- For every contest, `candidate_quality_residual_D = -candidate_quality_residual_R`; maximum symmetry error is exactly zero.

## Fold isolation

The output contains seven valid forward-year folds and eleven leave-state-out folds for each of the seven declared models.

- Every forward test row has the fold year, and its recorded training count equals the independently counted rows with `year < fold year`.
- Every leave-state-out test row has the held-out state, and its recorded training count equals the independently counted rows from all other states.
- No forward fold trains on its test or future year, and no leave-state-out fold trains on its held-out state.

There are no fold/train-count or test-membership violations.

## Ranking and unchanged selection rule

The manifest retains the same seven specifications and the declared rule: among models no more than one point worse than the best forward RMSE, choose the lowest leave-state-out RMSE, with whole-precinct LOSO and simplicity as tie-breakers.

| Model | Forward RMSE | LOSO RMSE | Whole-precinct LOSO RMSE | Guardrail |
|---|---:|---:|---:|---|
| portable temporal | 14.457228 | 15.326309 | 14.088031 | pass |
| full temporal | 14.369934 | 16.942768 | 14.567058 | pass |
| symmetric incumbency | 14.922803 | 18.926779 | 18.071148 | pass |
| state/chamber/incumbency | 14.952654 | 18.968249 | 17.493855 | pass |
| state/chamber lag | 16.651344 | 20.578158 | 20.481146 | fail |
| pooled lag | 16.969238 | 20.645432 | 21.247589 | fail |
| baseline only | 17.852471 | 22.941088 | 24.338844 | fail |

The best forward score is `14.369934`, making the guardrail ceiling `15.369934`. Portable temporal is only `0.087294` points behind and has the lowest LOSO RMSE among passing models, so it is correctly selected exactly once. Independent fold-level RMSE aggregation reproduces every displayed value.

The report's comparison with the prior validated 2,383-row run also reconciles: portable-temporal forward RMSE changes from `14.277671` to `14.457228`, and LOSO RMSE from `15.084043` to `15.326309`.

## Selected fitted effects

Independent reconstruction reproduces the selected portable-temporal effects:

- Democratic incumbent effect: `+14.258195`
- Republican incumbent effect: `-14.258195`
- Two-year time effect: `+0.147771`
- Ten-point baseline effect on gap: `-3.129685`

These are correctly described as descriptive fitted coefficients rather than causal estimates.

## Provenance

- The manifest input panel and panel-manifest hashes match the validated V2 inputs.
- All six output hashes and row counts reproduce.
- Every temporary CSV is byte-identical to the release candidate.
- Configuration records strict eligible-only filtering, all seven models, the two-prior-cycle forward requirement, and the unchanged selection rule.

This PASS authorizes experimental comparison and calibration only. It does not promote the tournament to the production Alabama forecast or erase the Tennessee OCR/context limitations documented upstream.
