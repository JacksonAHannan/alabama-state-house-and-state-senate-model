# Southern regime-aware forecast rebuild

## Data

The research tournament combines two explicitly labeled eras:

- 2,402 validated Southern legislative contests from 1994–2016; and
- 1,188 Southern legislative contests from 2018–2024 with compatible
  presidential-environment baselines.

The combined panel contains 3,590 unique state-year-chamber-district races.
The 2024 recent panel lacks incumbency labels. They remain missing and
incumbency is excluded from this promotion tournament; no missing value is
treated as an open seat.

## Tournament

The outcome is legislative Democratic margin minus the available environment
baseline. The challengers are a recent pooled gap, an all-era ridge model, two
recency-weighted ridge models with four- and eight-year half-lives, and a
recent-only ridge model. Ridge features are deliberately limited to baseline
margin and chamber. The baseline-only model applies no down-ballot adjustment.

Every forward prediction is produced by races from strictly earlier years.
Selection uses 2020, 2022, and 2024 because 2018 is the first observed cycle
after the regime break. A challenger must improve average MAE and 2024 MAE,
improve at least two cycles, and never lose by more than two points in a cycle.

| Model | Mean MAE, 2020–24 | 2024 MAE | Delta vs baseline | Selected |
|---|---:|---:|---:|---|
| baseline only | 4.739 | 3.620 | 0.000 | yes |
| recent-only ridge | 4.957 | 3.742 | +0.217 | no |
| recent pooled gap | 4.984 | 3.627 | +0.245 | no |
| four-year half-life ridge | 6.173 | 4.409 | +1.433 | no |
| eight-year half-life ridge | 7.658 | 6.089 | +2.918 | no |
| all-era ridge | 9.427 | 8.532 | +4.688 | no |

## Decision

The no-adjustment environment baseline wins. None of the historical or recent
down-ballot-gap models improves a single 2020–2024 holdout cycle. The evidence
therefore does not support applying the large pre-2016 Southern lag to 2026.

The research 2026 Basic and Fundamentals+ files retain the requested 20 and
100 percent adjustment architecture, but the selected full adjustment is zero,
so both currently equal the poll- and demographic-adjusted presidential
environment baseline. Candidate/incumbency scenarios may still be shown as
explicit experimental views after recent incumbency coverage is repaired; they
should not be embedded in headline margins yet.

Because the selected expected margin is the same environment baseline used by
the existing recent-era probability calibration, this result does not require
refitting the probability curve. It requires independent validation before any
production or website promotion.
