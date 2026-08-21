# RDH 2024 demographic forecast rebuild

Run date: 2026-08-17

## Scope and leakage rule

The historical tournament continues to use only cycle-matched Census features.
The Redistricting Data Hub (RDH) 2024 CVAP, ACS, L2, and projection products are
not backfilled into historical holdouts. They are evaluated as prospective 2026
sensitivity scenarios only.

## Sources

Raw archives are preserved under `data/raw/rdh/`; hashes and retrieval metadata
are recorded in `data/raw/rdh/source_manifest.csv`. RDH documentation attributes
CVAP and ACS estimates to the U.S. Census Bureau. L2-derived registration and
turnout fields and RDH population projections remain experimental.

## Findings

- Direct 2024 CVAP nonwhite share averages about 3.1 percentage points below the
  existing 2022 total-population nonwhite share.
- In the public 80/20 ramp-plus-ridge forecast, substituting direct CVAP changes
  the average contested-race margin by 0.003 points and the largest by 0.009.
- Adding the 2024 education change to the CVAP scenario changes the average
  contested-race margin by 0.050 points in absolute terms and the largest by
  0.163 points. No predicted winner changes.
- The standalone demographic-response specification remains rejected: its 2022
  forward MAE is 35.86, versus 9.78 for the ramp and 9.58 for the public 80/20
  ensemble. Its lone scenario flip is therefore not decision-relevant.
- Flexible challengers show larger sensitivity (roughly 1 point maximum for the
  selected CVAP-plus-education scenario), but none changes a winner.

## Decision

Keep the validated 80/20 public forecast unchanged. Use direct district CVAP as
the authoritative racial-composition source in future feature engineering, but
do not interpret the tiny current forecast response as evidence that the old
total-population definition was correct. It reflects strong regularization and
the public ensemble's deliberately small demographic-model weight.

Historical CVAP files are required before CVAP can compete as a fitted feature
under expanding-window validation. L2 and projected VAP variants remain labeled
stress tests until comparable historical series and licensing review exist.

## Historical CVAP follow-up (2026-08-17)

RDH CVAP was subsequently assembled for 2010, 2014, 2018, and 2022. The 2010
and 2014 features allocate native 2010-geography block-group counts with Census
block population; 2018 and 2022 use direct Census/RDH SLD tabulations.

In a like-for-like 80/20 all-feature ridge comparison, a hybrid definition
(total-population nonwhite share before 2010, CVAP thereafter, plus an
availability indicator) slightly outperformed the original definition:

| Specification | 2014 MAE | 2018 MAE | 2022 MAE | Three-cycle mean |
| --- | ---: | ---: | ---: | ---: |
| Original total-population feature | 21.735 | 12.032 | 9.577 | 14.448 |
| Hybrid CVAP feature | 21.745 | 12.026 | 9.520 | 14.430 |

The improvement is only 0.018 points in cycle-balanced mean MAE. A stratified
race bootstrap of the paired error difference gives a 95% interval of roughly
-0.036 to +0.0003 points (negative favors hybrid), so the evidence is suggestive
but not decisive. Pure CVAP without the pre-2010 bridge performs worse than the
original feature. Refitting the prospective hybrid changes 2026 margins by only
0.024 points on average in absolute terms, at most 0.094 points, with no winner
changes. Keep CVAP experimental rather than silently changing the public model.

## Comprehensive model tournament

A subsequent grid evaluated 576 combinations across eight demographic feature
families, twelve algorithms/regularization settings, and four ramp blend
weights, using all seven expanding-window holdouts from 1998 through 2022.

The best stable demographic candidate was a full-strength elastic net using the
standard forecast inputs plus hybrid CVAP composition, with deterministic time
extrapolators removed. It recorded 16.02 all-cycle mean MAE, 10.92 post-2016
mean MAE, and 9.38 in 2022. Adding CVAP composition improved its matched stable
elastic-net version by 0.32 cycle-balanced MAE, but the paired stratified
bootstrap interval (-0.70, +0.07) still includes no gain.

The numerically strongest modern candidate was a low-penalty hybrid-CVAP ridge
(16.15 all-cycle mean, 7.85 in 2022), but it extrapolates beyond the historical
range on every 2026 observation for time-since-realignment and on many
national-environment interactions. Used directly it changes 2026 margins by up
to 23.47 points and flips two seats, so it is not safe for promotion.

A 90/10 public/stable-elastic ensemble is the most conservative promising
variant: 21.52 all-cycle mean MAE, 10.48 post-2016, and 9.18 in 2022, while
limiting 2026 changes to 2.13 points and producing no winner changes. It remains
experimental because it was selected from a large tournament and has only
three CVAP-era holdouts.
