# CMO v6: observed performance and Southern-prior decomposition

## Purpose

This is the current historical CMO decomposition. It estimates generic
down-ballot lag and incumbency outside Alabama before the remaining race
differential is attributed to candidates. It does not redefine Direct CMO and
it is not a direct 2026 forecast adjustment.

## Measures

- **Direct CMO** remains observed candidate margin minus the selected
  same-cycle federal or state-ticket margin.
- **Southern structural expectation** is the expected Democratic down-ballot
  gap from the validated `portable_temporal` model, refitted on 2,350 Southern
  contests after excluding every Alabama observation.
- **Incumbent-neutral expectation** sets incumbency balance to zero while
  retaining the same district, year, chamber, baseline, and office context.
- **Generic incumbency gap** is the difference between the inclusive and
  neutral expectations.
- **Residual candidate quality** is Direct CMO minus the inclusive Southern
  expectation. It remains a candidate-versus-opponent differential.
- **Total electoral value** adds a candidate-oriented half-share of the generic
  incumbency differential to the partial-pooled residual candidate effect.

Federal Alabama ticket baselines can combine multiple federal offices. The
model therefore averages the predictions obtained under presidential and U.S.
Senate source-office categories and publishes their range as a source-choice
sensitivity. State-ticket fallbacks use the governor category.

## Validation result

Across eight Alabama cycles, the external Southern expectation reduces
cycle-balanced MAE from 21.33 points for the ticket baseline alone to 17.29.
The improvement is concentrated in 1994–2014. It fails the modern-era gate:
average MAE in 2018 and 2022 is 13.66, versus 6.54 for the unadjusted ticket
baseline. The validated Southern historical panel ends in 2016, so this is
evidence of post-2016 nationalization rather than a reason to extrapolate the
old down-ballot relationship into 2026.

The candidate-effect tournament selects a ridge penalty of 3 among candidates
previously observed. Its improvement is small: MAE 15.99 versus 16.35 for a
zero candidate-effect prediction. Effects must retain uncertainty labels.

## Publication and forecast decision

This decomposition is the current historical candidate-quality research view
and distinguishes generic incumbency from residual quality. Direct CMO remains
the public headline measure. The Southern expectation is rejected as a direct
2026 forecast adjustment because it fails the modern-era gate. The robust
forecast instead uses the modern 2018–2024 tournament and keeps historical CMO
information outside the headline margin.
