# Candidate-history carry-forward in the 2026 forecast

Evidence for the owner decision of 2026-09-15 to carry each nominee's own
demonstrated WAR into the 2026 forecast, and for checklist item `forecast-04`
(polling snapshot refresh).

- Builder: `scripts/build_forecast_candidate_history.py`
- Forecast build: `5c29c71e4ffacc6fa2b5`
- Persistence source: `post2016_southern_war_v3/candidate_cycle_war.csv`
- Outputs: `data/processed/forecast_calibration/alabama_forecast_candidate_history*.{csv,json}`

## Why the original specification could not be implemented

The agreed Q16(a) wording was that a candidate's most recent raw gap would enter
"through v3's fitted decaying-lag coefficient." That is not possible: v3's
decaying lag is the **prior-presidential district lag**
(`prior_pres_margin`, `lag_current_ticket_change`, `lag_change_x_years`). The
model contains no candidate-history term at all, so there is no fitted
coefficient for a candidate's own prior performance. The owner selected the
alternative of estimating persistence on the Southern panel's repeat candidates.

## Estimated persistence

Consecutive appearances of one candidate identity (state × party × normalized
name, excluding same-cycle name collisions) in the v3 frame:

| Quantity | Value |
|---|---|
| Pairs / distinct candidates | 1,576 / 1,186 |
| Persistence of prior WAR | **0.432** (SE 0.076, t 5.70) |
| Years-elapsed interaction | −0.008 (SE 0.043, t −0.19) — **not supported, not applied** |
| R² | 0.266 |
| Observed gaps | 2, 4 and 6 years |
| Pre-2022 refit (holdout) | 0.341 (SE 0.056, t 6.03) on 580 pairs |

Standard errors are clustered by candidate identity because the same person
appears in several pairs. The decay term is estimated but withheld: with t =
−0.19 there is no measurable decay across 2–6 years, and applying an
insignificant coefficient would manufacture precision. A single-gap training
window (the pre-2022 holdout is all 2018→2020) cannot identify the interaction
at all, and the builder reports it as `decay_estimable: false` rather than
dividing by a zero standard error.

## Applying it to 2026

- **Matching (Q15b).** Verified prior-winner crosswalk first (23 roster rows),
  then exact unique normalized name (37). Ambiguous names are left unmatched.
  129 of 189 roster rows have no prior Alabama race and are evaluated
  generically.
- **Staleness limit.** Persistence is measured over 2-to-6-year gaps, so the
  carry limit is 8 years — one cycle beyond the observed range. 48 roster rows
  carry an adjustment; 12 matched rows whose last race was 2014 or earlier keep
  their recorded history but enter as zero
  (`history_older_than_carry_limit_encoded_as_zero`). Carrying a 2006 result
  into 2026 at full strength would not be defensible.
- **Rematch.** Two nominees' prior WAR values are exact negatives when they last
  faced each other, so a rematch would double-count one race residual. One such
  race exists in 2026 (HD40); it contributes the single Democratic-oriented
  value.
- **Coverage.** 23 of the 48 modeled races carry a candidate adjustment; mean
  absolute adjustment 2.4 margin points, maximum 16.5.

## Holdout comparison (published, not hidden)

Trained on eligible post-2016 Southern races before 2022, tested on the 33
Alabama races of 2022. Candidate history for the holdout is estimated and
applied using only pre-2022 evidence; 6 of the 33 races had a matched prior
result.

| Specification | MAE | RMSE | Winner accuracy | Brier |
|---|---|---|---|---|
| Generic-ballot baseline | **7.07** | 9.26 | 97.0% | 0.0231 |
| WAR structural expected gap | 7.65 | 9.19 | 100.0% | 0.0171 |
| **WAR structure + candidate history (published)** | 7.46 | **8.94** | 100.0% | **0.0165** |

Carrying candidate history improves the structural model on every metric and
still trails the generic-ballot benchmark on MAE. The published model is the
owner-selected estimand; the comparison and that reasoning appear on the public
methodology page rather than being suppressed.

A defect found and fixed during this work: the holdout join initially matched
nothing because 2022 canonical rows carry stub person identifiers
(`ALPERSON-GSL003DTHO`) that do not link to earlier cycles, and a second join
silently matched nothing because the forecast panel says `lower`/`upper` while
the historical export says `house`/`senate`. Both now fail loudly instead of
returning a zero adjustment.

## Polling refresh (`forecast-04`)

Refreshed from the same VoteHub/Silver-grade pipeline, metadata only:

```powershell
.venv/Scripts/python.exe scripts/build_votehub_crosstab_source_inventory.py --from-date 2026-07-16
.venv/Scripts/python.exe scripts/build_silver_pollster_quality_gate.py
.venv/Scripts/python.exe scripts/build_silver_bplus_polling_environment.py
.venv/Scripts/python.exe scripts/build_2026_poll_adjusted_baseline.py
```

| | Previous | Refreshed |
|---|---|---|
| As-of date | 2026-08-17 | **2026-09-08** |
| Staleness at build | 28 days | 6 days |
| Generic-ballot D two-party margin | +7.55 | **+10.02** |
| Contributing B+ pollsters | 6 | 6 |

The uniform national-to-Alabama transfer assumption is unchanged; only the
snapshot moved.

## Verification

```powershell
.venv/Scripts/python.exe scripts/build_forecast_candidate_history.py
.venv/Scripts/python.exe scripts/run_alabama_war_generic_forecast.py
.venv/Scripts/python.exe scripts/build_2026_forecast_dashboard.py --artifact-only
.venv/Scripts/python.exe -m pytest -p no:cacheprovider scripts/tests/test_forecast_candidate_history.py scripts/tests/test_alabama_war_generic_forecast.py scripts/tests/test_forecast_dashboard.py scripts/tests/test_forecast_roster_universe.py -q
```

46 passed, 1 xfailed (the published-site methodology assertion, which is marked
`xfail(strict=True)` until the single republish). The dashboard artifact was
opened in a browser at 1280 px: polling chip reads 2026-09-08 (6 days old), 105
House rows render, no horizontal overflow, no console errors.

## Limits

- One direct Alabama forward holdout, with only 6 carry-eligible races in it.
- 2018 results reach 2026 as a one-cycle extrapolation beyond the observed gap
  range; 2026 gaps of 12–20 years are excluded entirely.
- Identity matching below the verified crosswalk is exact-name based; a renamed
  or differently spelled candidate is treated as having no history.
- Persistence is estimated across the whole Southern panel, not Alabama alone.
