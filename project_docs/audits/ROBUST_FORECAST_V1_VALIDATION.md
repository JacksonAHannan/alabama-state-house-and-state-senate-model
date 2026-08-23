# Robust forecast pipeline v1 validation

**Verdict: PASS as a research candidate.**

Current build `b5c625a6edb0a7c238fb` passes the complete release gate. The earlier prospective/scenario lineage failure is remediated: all direct and transitive data inputs, all four controlling code files, and the material run configuration are explicitly hashed or recorded.

## Independent rebuild and tests

```powershell
$env:VALIDATION_ROBUST_OUT = "C:\Users\User\Documents\GitHub\alabama-state-house-and-state-senate-model\.validation_tmp\robust_forecast_v1"
@'
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path("scripts").resolve()))
import run_robust_forecast_pipeline as pipeline
pipeline.CAL = Path(os.environ["VALIDATION_ROBUST_OUT"]).resolve()
pipeline.main()
'@ | python -X utf8 -

python -m pytest scripts/tests/test_robust_forecast_pipeline.py scripts/tests/test_southern_2024_incumbency.py -q
```

Two complete temporary builds are deterministic; temporary manifest SHA-256 remains `f7d076ee7f2e05efdcd4c1601ca985ea7db0079a2abf52fec93b65720733d4d5`. All twelve CSV outputs byte-match the release candidate. The combined focused suite passes 11/11.

## Candidate identities and temporal validity

- The panel contains 1,188 unique contests: 283 in 2018, 268 in 2020, 302 in 2022, and 335 in 2024.
- All 323 model-ready 2024 races are retained; the 12 unresolved races keep missing incumbency and are excluded from the common test set.
- Independent chronological reconstruction reproduces every prior-quality value and availability flag. No available row is supported only by a future identity.
- 2018 has no prior-quality signal, and every unavailable row carries zero plus an explicit availability flag.
- Candidate history is keyed to normalized state/chamber identity, not district. Sixty linked identities move across district numbers. Conversely, 136 seats with historical races but no returning identity correctly receive no seat fallback.
- The one observed cross-party identity continuity remains linked. Two duplicated Texas surnames in 2024 cannot affect V1 histories because same-cycle identities are batch-updated and there is no later panel cycle.

## Common forward tournament

All four models predict the same 893 contests: 268 in 2020, 302 in 2022, and 323 in 2024. Training counts are 283, 551, and 853, with maximum years 2018, 2020, and 2022. Every fold is strictly time-forward and all prediction keys are unique.

Independent aggregation reproduces all cycle MAE, RMSE, and bias values within `1.78e-15`:

| Model | Mean MAE | Delta vs baseline | Latest delta | Worst delta | Improved cycles |
|---|---:|---:|---:|---:|---:|
| baseline | 4.751298 | 0.000000 | 0.000000 | 0.000000 | 0 |
| demographics + incumbency | 5.590628 | +0.839330 | +0.349358 | +2.276855 | 1 |
| plus prior candidate quality | 5.629560 | +0.878261 | +0.259698 | +2.483311 | 1 |
| demographics | 6.030773 | +1.279475 | +0.483337 | +3.119026 | 0 |

No challenger clears the recorded average/latest/worst-cycle guardrails. Baseline is correctly selected exactly once.

## Probability and error calibration

- Probability selection uses only the selected model's 893 out-of-sample margins.
- Independent evaluation of all 225 recorded family candidates selects Student-t with scale `5.75` and df `5`.
- Brier score is `0.0297952632`; log loss is `0.0995466397`.
- Published probabilities reproduce to `1.11e-16` and remain bounded.

The shared-error row identity reconciles within `3.55e-15`. Recomputed standard deviations match the output: national `2.203850`, state `2.007252`, chamber `1.025061`, district `5.905698`, and total residual `6.251567`. Differently weighted grouping levels have a small descriptive quadrature difference (`6.321161` versus `6.251567`), but row errors and the simulation's recorded component use are internally consistent.

Every subgroup dimension partitions all 893 calibrated rows. Finance correctly remains ineligible with zero comparable cross-state cutoff coverage; missing finance is not zero-filled into a model feature.

## Scenarios and simulation

- The scenario output contains 192 unique rows: 48 each for headline, historical CMO, Democratic-favorable environment, and Republican-favorable environment.
- Headline margins equal the selected environment baseline. Environment scenarios shift by `±national_sd`; historical CMO remains separate and cannot affect selection.
- Scenario probabilities reproduce the selected Student-t curve.
- The full-uncertainty table contains 48 districts and 50,000 draws per district.
- A fresh run with seed `20260822` reproduces probabilities exactly and interval endpoints within `7.11e-15`.
- 80% intervals nest within 95% intervals. House and Senate modeled-seat distributions each sum to one.

These distributions cover 48 modeled contested seats only, not complete chambers.

## Provenance remediation

The manifest verifies 15 data inputs, including the historical-CMO source and all roster, presidential, demographic, incumbency, finance, polling, and national-demographic inputs used by the prospective stage.

It also hashes all four controlling code files:

```text
scripts/run_robust_forecast_pipeline.py
scripts/run_forecast_experiment_tournament.py
scripts/fit_2026_prospective_model.py
scripts/build_southern_2024_incumbency.py
```

All 15 source hashes, four code hashes, and twelve output hashes/counts independently match current files.

The configuration block explicitly records the seed, 50,000 draws, forward folds, common incumbency-ready gate, candidate shrinkage, ridge penalty, every margin feature set, selection guardrails, complete probability grids/ordering/clipping, error grouping, scenario formulas, and finance policy. This satisfies the repository requirement that data, code, and configuration identify the generated run.

## Scope

This PASS approves robust V1 for research handoff and a separately validated product-integration task. It does not itself authorize website publication, complete-chamber seat claims, finance promotion, or treating the three-cycle probability choice as settled beyond its stated uncertainty.
