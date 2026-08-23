# Current method release validation

Date: 2026-08-22
**Verdict: PASS.**

The reconciled CMO v6 historical decomposition, robust forecast v1, versioned publication exports, methodology labels, and themed public pages satisfy the release contract.

## Commands

    python -m pytest scripts/tests/test_cmo_southern_prior_v6.py scripts/tests/test_robust_forecast_pipeline.py scripts/tests/test_southern_2024_incumbency.py scripts/tests/test_forecast_dashboard.py scripts/tests/test_cmo_war_analogue.py scripts/tests/test_published_site_consistency.py scripts/tests/test_site_brand.py -q
    # 47 passed

    python -m pytest -q
    # 476 passed, 11 warnings

    python scripts/validate_agent_workflow.py
    # Agent workflow validation passed.

Independent rebuilds redirected v6 and robust-v1 output roots into unique validation temporary directories. Robust-v1 was built twice. V6 was rebuilt twice at one fixed output path after its two required v5 inputs were copied into that path.

## CMO v6 historical decomposition

- All 509 v5 race keys join one-to-one to the 509 v6 race keys.
- Direct CMO is invariant: maximum v5/v6 difference is 3.55e-15, below the 1e-12 contract tolerance.
- Independently recomputed decomposition identities have maximum error 7.11e-15:
  - Southern residual quality = Direct CMO minus Southern expected gap.
  - Generic incumbency gap = inclusive expected gap minus incumbent-neutral expected gap.
- Candidate output contains 1,018 unique candidate-party rows, exactly two for each of 509 races.
- Both same-path v6 rebuilds are byte-deterministic. All five rebuilt CSVs byte-match the release outputs.
- The production manifest build is c2f7098efb4b5f188733. All four data-input hashes, three code-input hashes, and five output hashes match current files.
- The public labels consistently describe v6 as a historical Southern-prior decomposition. They explicitly state that its 2018–2022 validation failure prevents direct use as a 2026 adjustment.
- Direct CMO remains the observed legislative margin relative to the selected same-district ticket; the Southern expectation, residual quality, and generic incumbency component are separately labeled.

The manifest build identifier changes when the validation output directory changes because copied v5 input paths are included in its provenance. At a fixed build path, the complete manifest and outputs are deterministic. This path-sensitive but explicit provenance is not a release blocker.

## Robust forecast v1

- Two complete temporary rebuilds are byte-identical to one another and all 13 release files, including the manifest.
- The production build is 315df6dcc3c8dccd1585.
- The manifest's 14 data inputs, four code inputs, and 12 output hashes all match current files.
- Baseline is the sole selected margin model. The selected probability family is Student-t with scale 5.75 and 5 degrees of freedom.
- The scenario table contains exactly 144 unique rows: 48 each for headline, environment_dem_favorable, and environment_rep_favorable.
- No historical_cmo scenario is present.
- Every headline margin equals its environment baseline exactly.
- Democratic- and Republican-environment margins equal headline plus or minus national_sd, with maximum reconciliation error below 8.0e-15.
- Scenario probabilities reproduce the selected Student-t curve to 1.11e-16 and remain within [0,1].
- Full uncertainty contains 48 modeled districts with 50,000 draws each. Probabilities are bounded, intervals are nested, and modeled-seat distributions sum to one within each chamber.

## Publication and methodology

All five contracted CMO files and all nine contracted robust-forecast files under docs/data byte-match their versioned processed sources.

The public forecast exposes exactly three views: Headline, Democratic environment, and Republican environment. Historical CMO is discussed only to explain why it is not a forecast tab. The public methodology agrees with the versioned model documents on:

- the poll-adjusted 2024 presidential headline;
- failed promotion of demographic, incumbency, and prior-quality challengers;
- the Student-t(5), 5.75-point probability calibration;
- 50,000 correlated simulations;
- exclusion of finance for lack of comparable cross-state coverage;
- historical-only scope of the Southern-prior decomposition.

No legacy 80/20 or Fundamentals+ view is rendered in the current public candidate.

## Browser validation

Chrome exercised all three forecast tabs. The forecast, CMO, forecast-methodology, and CMO-methodology pages loaded at desktop, exact 497px, and exact 390px widths.

| Page group | Desktop overflow | 497px overflow | 390px overflow | Severe console errors |
|---|---:|---:|---:|---:|
| Forecast | 0px | 0px | 0px | 0 |
| CMO | 0px | 0px | 0px | 0 |
| Forecast methodology | 0px | 0px | 0px | 0 |
| CMO methodology | 0px | 0px | 0px | 0 |

The forecast tab list contains exactly the three current view identifiers at every width. No runtime, responsive-layout, numerical-fidelity, provenance, or labeling blocker remains.

## Non-blocking caveats

- V6 is approved only as a historical decomposition; its Southern expectation fails the modern-era forecast promotion gate.
- The robust tournament has three forward holdout cycles and four Southern calibration states.
- The full suite emits existing deprecation, dtype, and pandas future warnings, but no test failures.
