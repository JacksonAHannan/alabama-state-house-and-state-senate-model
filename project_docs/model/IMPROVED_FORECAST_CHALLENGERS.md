# Improved-data forecast challengers

This is a challenger-model audit. It does not alter the selected public 80/20
ramp–ridge forecast.

The broad RDH tournament evaluates 576 combinations and is useful for discovery,
not unbiased selection. The confirmatory layer therefore freezes a compact set:

- the public 80/20 total-population ridge;
- the same feature set with stronger ridge shrinkage and a full residual;
- a full ridge replacing total-population nonwhite share with cycle-matched CVAP;
- a stable CVAP-composition elastic net;
- three stable, moderately blended Bayesian/elastic specifications that remove
  explicit time-extrapolation fields; and
- 25%, 50%, and 75% blends between the public model and full CVAP ridge;
- small blends with the stable Bayesian model; and
- one- and two-point caps on the stable Bayesian adjustment.

Every result uses the same seven expanding-window holdouts. Cycle-block bootstrap
intervals treat election environments, rather than individual districts, as the
resampling unit. A simulated selector chooses a model for each cycle using only
earlier holdout scores and falls back to the public benchmark until two prior
holdouts exist.

## Eligibility decisions

Cycle-matched RDH CVAP is available historically for 2010–2022 and prospectively
for 2026, so it can enter the challenger library. Candidate-level finance name
matching is 87–94% by party and cycle from 2014 onward. Under the project's
adopted policy, the main committee/FTM sources are definitive and a remaining
unmatched entry is assigned zero, so all 153 contested D–R races in 2014–2022
have usable finance values. The earlier 137-row FCPA experiment applied a much
narrower active-committee filter and is not the project's overall coverage rate.

Vote Smart ideology is excluded from the forecast tournament. It has no usable
2022 race-pair coverage and no 2026 candidate feature build. Ideology remains a
CMO research variable until genuinely pre-election nominee coverage exists.

Historical error is not the only gate. The audit also reports maximum 2026
movement and the SD-2 margin. A challenger fails the prospective smell test if
it moves any district by more than ten points or turns SD-2 Republican despite
its nearly tied 2024 presidential vote, open seat, and a more Democratic
projected national environment. This is a diagnostic safeguard, not a substitute
for validation.

## Results

The unrestricted improved-data models fit history much better but fail the 2026
smell test. The full hybrid-CVAP ridge reaches 16.15 cycle-balanced MAE and 7.85
in 2022, versus 22.64 and 9.58 for the public model, but moves districts by as
much as 23.47 points and scores SD-2 at R+16.43. Removing explicit time trends
does not fully solve the problem: the stable Bayesian model scores SD-2 at R+2.41.

Two deliberately conservative variants survive both screens:

| Challenger | Mean MAE | 2018–22 MAE | 2022 MAE | Worst cycle delta | Maximum 2026 move | SD-2 |
|---|---:|---:|---:|---:|---:|---:|
| Public 80/20 model | 22.64 | 10.82 | 9.58 | 0.00 | 0.00 | D+1.37 |
| 25% stable-Bayesian blend | 21.88 | 10.24 | 8.65 | -0.22 | 1.89 | D+0.42 |
| Stable-Bayesian adjustment capped at one point | 22.15 | 10.44 | 9.03 | -0.20 | 1.00 | D+0.37 |

Both challengers improve all seven holdouts, their cycle-block bootstrap
intervals exclude zero, and neither changes a projected 2026 winner. However,
the blend and cap were introduced after diagnosing prospective extrapolation.
They should be frozen now and evaluated as candidates, not promoted using the
same evidence that motivated them. The public forecast remains unchanged.

The past-only selector also reveals why a numerical tournament is insufficient:
it repeatedly chooses the historically strongest stable-composition model, which
still fails the SD-2 prospective check.

## Finance-augmented models

The comprehensive finance stack uses all races allowed by the definitive-source
and unmatched-equals-zero policy. Finance predicts the remaining out-of-fold
error above three conservative base models. The tested transforms use log
spending gaps at $10,000, $50,000, and $100,000 scales, ridge shrinkage, partial
weights, and prospective adjustment caps.

The best safe result for each base is:

| Base and finance layer | 2018–22 MAE | 2022 MAE | Incremental gain | Largest 2026 finance move | SD-2 |
|---|---:|---:|---:|---:|---:|
| Public model | 10.80 | 9.58 | — | — | D+1.37 |
| Public + 10% log-$10k finance | 10.72 | 9.45 | 0.08 | 1.73 | D+1.44 |
| 25% stable-Bayesian blend | 10.23 | 8.65 | — | — | D+0.42 |
| Stable-Bayesian blend + 25% log-$10k finance, capped at 2 | 10.17 | 8.55 | 0.07 | 2.00 | D+0.67 |
| One-point stable-Bayesian cap + 10% log-$10k finance | 10.37 | 8.97 | 0.06 | 1.66 | D+0.46 |

The combined stable-Bayesian/finance model has the lowest observed error. Its
total 2026 movement relative to the public model is at most 3.89 points and it
changes no projected winner. Finance contributes only a small incremental gain;
the improved demographic/residual base does most of the work.

These results use only two finance-era forward holdouts. More importantly,
historical spending totals run through Election Day while the 2026 file is an
August snapshot. That vintage mismatch blocks promotion even though the point
estimates improve. The next valid test should reconstruct historical finance at
the same number of days before Election Day as the current forecast cutoff.
