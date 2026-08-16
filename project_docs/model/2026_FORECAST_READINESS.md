# 2026 prospective CMO readiness

> **August 15 methodology revision:** The release-candidate forecast is now
> baseline-first. The selected headline margin is the poll-adjusted direct
> presidential baseline because every fitted residual layer failed the declared
> mean-and-latest forward-MAE gate. The former full-margin ridge output is archived
> as `2026_prospective_features_and_forecast_legacy_core_20260815.csv`. See
> `project_docs/methodology/FORECAST_METHODOLOGY.md` and `2026_forecast_decomposition.csv`.

The 2026 model must be frozen using information available by a declared cutoff. It cannot use same-cycle Governor or Attorney General returns. Historical CMO remains a retrospective product.

## Available now

- Certified Democratic and Republican nominee rosters OCR-parsed from the
  supplied party certification PDFs. These identify 185 nominees and 47
  contested D-R legislative races. Wikipedia is retained as a reconciliation
  source; 18 rows require name or roster review.
- Candidate expenditure totals through **2026-08-14**, using a full cycle beginning 2025-01-01 and latest-filing transaction semantics.
- A district-level checklist in `2026_feature_readiness.csv`.
- Official 2024 precinct presidential returns and precinct shapefiles are present locally.
- The supplied 2025 TIGER SLD files contain all 105 House and 35 Senate
  districts and report legislative session year 2024. A 2020 Census
  block-population crosswalk projects the official 2024 presidential results
  onto those districts and exactly preserves the statewide two-party totals.
- Prospective demographic features reuse the 2022 ACS estimates because the
  supplied plan is the reinstated original 2021 plan. A block-assignment audit
  found only eight House and one Senate centroid disagreements against the 2022
  block equivalency files, attributable to split/boundary blocks.
- A provisional incumbency table combines 2022 winners with saved-page
  annotations. Lower-confidence or source-disagreeing matches are separately
  queued for review.

## Still required before scoring

1. Manually review the 18 certification/Wikipedia differences and the 2026 finance match queues.
2. Choose and freeze a later finance cutoff. Transaction-expenditure matching
   is complete for both candidates in 31 of the 47 certified contested races.
3. Review the small number of split/boundary-block assignments if an official 2026 block-equivalency file becomes available.
4. Freeze the model, eligibility rules, feature transformations, missing-data policy, benchmarks, and interval method before reading 2026 legislative outcomes.

Missing rows in the 2026 state fundraising summary are **not treated as zero**.
The transaction extract shows positive expenditures for 80 certified nominees
who have no matched summary-page entry; 22 more have neither source matched and
remain unknown. A zero-dollar interpretation is retained only as a sensitivity
field, never as the primary value.

An experimental direct legislative-margin model now scores the 45 provisionally
contested races in `2026_prospective_features_and_forecast.csv`. It is not a
release forecast: forward MAE is 19.0 points even in the latest 2022 holdout,
and the empirical 80% interval radius is about 37 points.

The readiness manifest intentionally reports `forecast_ready = false` until all required components exist. Wikipedia is a secondary roster source, not an official ballot certification.

## Current uncertainty evidence

Expanding-window split-conformal diagnostics are written to `cmo_forward_interval_calibration.csv`. Empirical coverage is conservative, but the intervals are not practically sharp: the 80% radii are 38.8 points for the 2018 test and 36.6 points for 2022; 95% radii are 91.8 and 53.5 points. This confirms that the present historical model is not ready to publish precise 2026 forecasts even after the missing feature pipeline is completed.
