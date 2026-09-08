# Southern regime-aware forecast rebuild validation

**Verdict: PASS as a research tournament; baseline-only selection is valid.**

The review candidate combines the historical and recent Southern panels without altering source-era definitions, preserves unknown 2024 incumbency, uses strictly earlier training years, and correctly finds that no adjustment model clears the prespecified recent-era guardrails. Both 2026 research views therefore equal the current environment baseline.

## Independent rebuild and tests

I redirected the module-level output directory to an isolated workspace and invoked the unchanged implementation:

```powershell
$env:VALIDATION_REGIME_OUT = "C:\Users\User\Documents\GitHub\alabama-state-house-and-state-senate-model\.validation_tmp\forecast_regime_v1"
@'
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path("scripts").resolve()))
import run_southern_regime_forecast_rebuild as model
model.WAR = Path(os.environ["VALIDATION_REGIME_OUT"]).resolve()
model.main()
'@ | python -X utf8 -

python -m pytest scripts/tests/test_southern_regime_forecast_rebuild.py -q
```

Two isolated rebuilds are deterministic. The path-local manifest SHA-256 remains `032d81a69508a894d90e1cab7bd9c66b280e5208840f17108db21c4746465d16`; all five CSV outputs byte-match the release candidate. Focused tests pass 5/5.

## Source panel and keys

- Historical source: 2,402 rows, all explicitly eligible.
- Recent source: 1,319 rows, of which 1,188 pass `primary_calibration_eligible`.
- Normalized panel: 3,590 unique state-year-chamber-district rows—2,402 labeled `historical_1994_2016` and 1,188 labeled `recent_2018_2024`.
- No normalized race key is duplicated.
- All 335 observations from 2024 retain missing `incumbency_balance`; every non-2024 row has a nonmissing value. The model does not use incumbency, and no missing label is converted to an open seat or zero.

## Temporal isolation

The output contains 6,562 unique model/contest predictions for six prespecified models over 2018, 2020, 2022, and 2024.

- For every model-year fold, the recorded training count exactly equals the independently selected rows with year strictly less than the test year.
- Every nonempty fold has `train_max_year < test year`.
- `pooled_recent` and `ridge_recent_only` use no pre-2018 data; their minimum training year is 2018 in every estimable 2020–2024 fold.
- No temporal membership, minimum-year, maximum-year, or training-count violation was found.

Selection correctly excludes 2018, the first post-break cycle, and uses only 2020, 2022, and 2024.

## Independently reproduced cycle metrics

Cycle MAEs reproduce to at most `1.78e-15`:

| Model | 2020 | 2022 | 2024 | Mean |
|---|---:|---:|---:|---:|
| baseline only | 6.307678 | 4.290765 | 3.619969 | 4.739471 |
| recent-only ridge | 6.525046 | 4.602822 | 3.741807 | 4.956559 |
| recent pooled gap | 6.540526 | 4.784600 | 3.626919 | 4.984015 |
| four-year half-life ridge | 8.513360 | 5.595833 | 4.408501 | 6.172565 |
| eight-year half-life ridge | 9.721075 | 7.163292 | 6.088796 | 7.657721 |
| all-era ridge | 10.857422 | 8.891981 | 8.531993 | 9.427132 |

Independent error aggregation also reproduces every RMSE, bias, race count, latest-cycle delta, worst-cycle delta, and mean delta in the ranking file.

## Guardrails and selection

A challenger must improve mean MAE and 2024 MAE, improve at least two cycles, and never lose by more than two points. No challenger improves even one of the three cycles:

- recent-only ridge mean delta: `+0.217088`; 2024 delta `+0.121839`;
- recent pooled gap: `+0.244545`; 2024 delta `+0.006950`;
- four-year ridge: `+1.433094`; worst-cycle delta `+2.205682`;
- eight-year ridge: `+2.918250`; worst-cycle delta `+3.413397`;
- all-era ridge: `+4.687661`; worst-cycle delta `+4.912024`.

All challenger guardrails are therefore false, and `baseline_only` is selected exactly once. This is a supported negative result rather than a failed model build.

## Prospective 2026 output

The research forecast contains 96 unique view/chamber/district rows:

- 48 Basic rows: 33 House and 15 Senate;
- 48 Fundamentals+ rows: 33 House and 15 Senate.

The declared weights remain 0.2 and 1.0 respectively. Because the selected baseline-only model has a zero full expected gap:

```text
full_expected_gap       = 0
applied_gap_adjustment  = weight × 0 = 0
predicted_dem_margin    = environment_baseline_margin
```

Every row satisfies the arithmetic exactly, and the two views are identical for every district. The implementation does not fabricate differentiation when validation provides no support for an adjustment.

## Provenance and scope

The production manifest is labeled `research_candidate`, selects `baseline_only`, and records selection years `[2020, 2022, 2024]`. Both input hashes and all five output hashes/counts reproduce: 3,590 panel rows, 6,562 predictions, 18 metric rows, six ranking rows, and 96 prospective rows. Production build ID is `d7202b9dee4b95641bff`.

This PASS validates the research tournament and its no-adjustment conclusion. Production promotion, probability recalibration, and website changes remain separate decisions. The result does not license filling missing incumbency or applying the rejected pre-2016 Southern lag to 2026.
