# Forecast variable screening

This pipeline tests which information should be considered for the prospective
Alabama legislative forecast. It is separate from the CMO estimand: a variable
can improve prediction without belonging in headline CMO, and a useful
retrospective explanation can be unavailable or post-treatment at forecast time.

## Design

`scripts/run_forecast_variable_screen.py` uses the frozen historical feature
assembly consumed by the existing forecast tournament. It covers 509 district
races in eight cycles from 1994 through 2022. Each scored cycle is an expanding-
window holdout: only earlier cycles train its residual adjustment. Errors are
summarized with equal weight per election cycle so large House cohorts do not
overwhelm small Senate cohorts.

The first screen includes five pre-election bundles: incumbency, strictly lagged
candidate history, demographics, prior presidential trend, and fundraising.
Adding groups rather than dozens of correlated columns individually reduces
false discoveries. The variable screen uses the post-2016-step baseline because
the initial regime comparison rejects adding the proposed 2008 transfer. Later
rounds should use ablations within any bundle that passes this screen.

## Federal-environment break hypothesis

The regime comparison explicitly tests the hypothesis that federal environment
and attitudes gained weight in two steps:

- pre-2008: no automatic transfer of the national swing;
- 2010–2014: half transfer, representing increased nationalization after the
  2008 election;
- 2018 onward: full transfer, representing a second increase after 2016.

It compares this prespecified two-step path with no transfer, uniform full
transfer, a 2008-only step, and a 2016-only step. These are structural scenarios,
not causal estimates. In particular, no Alabama model trained before 2008 or
2016 could learn that a break was about to occur. The 2018 and 2022 evidence
therefore provides only two post-2016 cycle observations.

## Screening gate

A variable bundle is flagged for the next round only if it:

1. improves cycle-balanced forward MAE overall;
2. improves mean MAE in 2018–2022;
3. improves the latest 2022 holdout;
4. has at least 75% complete-case coverage; and
5. has a cycle-block bootstrap interval whose upper bound does not exceed zero.

Passing is permission for deeper testing, not automatic promotion to the public
forecast. Final promotion also requires leakage review, district/chamber and
candidate-group validation where applicable, coefficient and rank stability,
and an independently reviewed 2026 feature build.

Same-cycle statewide and federal vote margins are excluded from this screen.
They remain valuable CMO baselines and retrospective information upper bounds,
but are unavailable before the election and would leak the outcome environment.

## Initial result, 2026-08-17

The 2008 step does not pass the smell test in the current archive. Relative to
no environment transfer, a full post-2008 transfer worsens MAE from 25.91 to
35.62 in 2010 and from 23.58 to 29.09 in 2014. The more conservative half-step
also worsens those cycles, to 30.56 and 25.89. This is consistent with Alabama's
state-legislative partisanship lagging national realignment rather than jumping
immediately after Barack Obama's election.

The 2016 step is more plausible. It changes 2018 MAE from 13.11 to 12.47 and
2022 MAE from 12.03 to 9.78. Across all seven forward holdouts, the post-2016-
only rule has mean MAE 24.85, compared with 25.84 for the two-step rule and
25.26 for no national-environment transfer. This remains thin evidence: only
2018 and 2022 identify the post-2016 regime.

None of the five first-stage candidate or district bundles passes the screening
gate. Each regularized residual model reduces mean error over the full archive,
but each loses badly in the two post-2016 holdouts:

| Added bundle | Full-period delta MAE | 2018–2022 delta | 2022 delta | Result |
|---|---:|---:|---:|---|
| Incumbency | -3.92 | +10.72 | +9.20 | reject |
| Prior presidential trend | -3.47 | +9.40 | +2.60 | reject |
| Demographics | -3.39 | +10.65 | +7.64 | reject |
| Fundraising | -3.19 | +11.17 | +8.73 | reject |
| Candidate history / prior CMO | -2.36 | +13.27 | +10.34 | reject |

Negative deltas indicate improvement. The cycle-block intervals for all five
also cross zero. Finance and presidential-trend measurements are sparse in the
historical mart, and candidate-history fields are structurally unavailable for
many candidates, so their pooled results should not be interpreted as proof of
no effect. The appropriate next test is a narrower post-2016 model with strong
shrinkage and explicit availability patterns—not promotion of the pooled effect.

The current evidence therefore supports a baseline-first forecast: previous
presidential partisanship plus the post-2016 national-environment transfer.
Candidate-side variables remain contextual scenarios until they demonstrate
recent-era forward gains.
