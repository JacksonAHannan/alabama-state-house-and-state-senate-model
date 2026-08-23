# Robust forecast V1 website validation

**Verdict: PASS.**

The rebuilt publication is numerically faithful to validated robust-forecast build `b5c625a6edb0a7c238fb`, deterministic, responsive, and functional. The stale publication-consistency assertions identified in the first review have been replaced with robust-v1 requirements, and the complete test suite now passes.

## Independent clean rebuild

The builder was imported with only its publication destinations redirected to a new temporary directory; all production inputs remained read-only.

```powershell
$tmp = Join-Path $env:TEMP ('robust_web_validate_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tmp | Out-Null
$env:ROBUST_WEB_VALIDATE_TMP = $tmp
python -c "import os; from pathlib import Path; import scripts.build_2026_forecast_dashboard as b; t=Path(os.environ['ROBUST_WEB_VALIDATE_TMP']); b.OUTPUT=t/'artifact.html'; b.SITE=t/'docs'; b.main()"
```

The temporary artifact, temporary `docs/index.html`, checked-in artifact, and checked-in `docs/index.html` all have SHA-256 `66f9872f6ed90d09ce4172a6433e349ec4ea786157135763ad356c092fd7eea5`. The temporary methodology and all copied downloads were produced without reading an existing `docs/` file. Static inspection finds no builder read operation whose source is `docs/`.

## Payload and chamber reconciliation

- Payload version is exactly `b5c625a6edb0a7c238fb`.
- The payload has all 105 House and 35 Senate districts, 48 modeled D-R contests (33 House, 15 Senate), and zero unmodeled districts.
- All 192 source scenario rows reconcile by chamber/district/scenario. Rounded embedded margins and Democratic win probabilities have zero mismatches against `robust_forecast_v1_2026_scenarios.csv`.
- The headline chamber distributions byte-for-value match the correlated 50,000-draw modeled-seat distributions after adding fixed Democratic seats: 20 House and 6 Senate. Their probability sums are `0.9999999999999999` and `1.0`; supports are 25-34 and 6-11 Democratic seats.
- Single-major-party seats are held fixed. Complete chamber accounting consists of 33 modeled plus 20 fixed-D plus 52 fixed-R House seats, and 15 modeled plus 6 fixed-D plus 14 fixed-R Senate seats.
- The full-uncertainty source has 48 rows, 50,000 draws on every row, and bounded probabilities.

## Public downloads and methodology

All nine versioned robust-v1 files copied by the builder byte-match their canonical sources:

```text
robust_forecast_v1_2026_scenarios.csv
robust_forecast_v1_2026_full_uncertainty.csv
robust_forecast_v1_2026_modeled_seats.csv
robust_forecast_v1_metrics.csv
robust_forecast_v1_ranking.csv
robust_forecast_v1_probability_families.csv
robust_forecast_v1_error_components.csv
robust_forecast_v1_subgroup_audit.csv
robust_forecast_v1_manifest.json
```

Generated forecast and methodology pages contain none of `Fundamentals+`, `six-point normal`, `20% of the CMO`, `Basic model`, or `Basic and Fundamentals+`. The methodology instead reports the 893 common forward contests, selected Student-t(5)/5.75 calibration, three forward cycles, shared-error 50,000-draw chamber simulation, fixed-seat rule, and explicit non-headline scenario status.

## Browser, accessibility, and interaction checks

Chrome 151 headless was exercised against the isolated build. At exact `document.documentElement.clientWidth == 497`, `scrollWidth == clientWidth == 497`; there is no horizontal overflow. Leaflet initialized, the error fallback was absent, and the browser console contained no error-level entries.

The four forecast-view controls render and update the URL/model state. House/Senate switching updates `aria-pressed`; Senate exposes statewide plus 35 district options. Selecting SD-25 renders its district detail and close control. Map-mode switching updates pressed state. Static HTML checks confirm labeled search/filter controls, live district detail, chamber and map pressed-state controls, source ledger, internal site navigation, and embedded JavaScript parses with `node --check`.

## Tests

```powershell
python -m pytest scripts/tests/test_forecast_dashboard.py scripts/tests/test_robust_forecast_pipeline.py scripts/tests/test_published_site_consistency.py scripts/tests/test_site_brand.py -q
# 30 passed

python scripts/validate_agent_workflow.py
# Agent workflow validation passed.

python -m pytest -q
# 467 passed
```

The repaired publication-consistency test now asserts the validated baseline headline, 893 common OOS contests, Student-t calibration, correlated 50,000-draw chamber simulation, and explicit scenario status while rejecting the retired forecast vocabulary. No release blocker remains.
