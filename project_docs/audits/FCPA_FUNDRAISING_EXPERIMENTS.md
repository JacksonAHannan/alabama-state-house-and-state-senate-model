# FCPA fundraising forecast experiments

## Design

The experiment uses 137 contested Democratic-versus-Republican races with
usable PCC totals for both candidates: 48 in 2014, 59 in 2018, and 30 in 2022.
Every model uses the identical race sample and the existing presidential,
incumbency, demographic, and trend baseline. Prospective tests train only on
earlier cycles and hold out 2018 and 2022. Leave-one-cycle-out tests train on the
other two cycles and provide a secondary stability check.

Fundraising is monetary contributions plus other receipts during the election
calendar year and preceding calendar year. In-kind contributions and beginning
cash are not included in the fundraising measure.

## Results

Fundraising improves forecast accuracy, although less dramatically once the
forward model correctly omits non-extrapolatable election-cycle fixed effects.
The raw Democratic-minus-Republican dollar gap reduces mean prospective MAE
from 15.46 to 15.15, a 2.0% reduction. A diminishing-return transform performs
better: the difference in `log1p(amount / $50,000)` reduces MAE to 14.55, a 5.9%
reduction.

| Specification | Prospective MAE | Improvement | LOCO mean-cycle MAE | $200k vs $50k effect | $50k vs $0 effect |
|---|---:|---:|---:|---:|---:|
| Nonfinance baseline | 15.46 | — | 22.92 | 0.0 | 0.0 |
| Raw dollar gap | 15.15 | 2.0% | 22.51 | +1.24 | +0.41 |
| Log diminishing, $50k scale | 14.55 | 5.9% | 20.75 | +5.45 | +4.12 |
| $25k viable flag | **12.40** | **19.8%** | **18.04** | 0.0 | +11.48 |
| Log-$50k + $100k viable | 15.20 | 1.7% | 20.63 | +6.25 | +3.78 |
| $100k viable flag | 15.42 | 0.2% | 20.75 | +7.78 | 0.0 |

Effects are fitted Democratic-margin differences on a representative race,
holding all nonfinance features constant.

The $25,000 viability flag has the best held-out accuracy, but it encodes a
cliff: $50,000 versus zero is important while $200,000 versus $50,000 receives
no additional credit because both candidates are viable. That contradicts the
desired ordering and is vulnerable to threshold overfitting. The threshold was
selected from several exploratory values, so its apparent advantage is
optimistic.

The $50,000-scale log transform is the cleanest specification consistent with
both diminishing marginal returns and the substantive ordering. It estimates a
larger advantage for $200,000 versus $50,000 than for $50,000 versus zero. A
hybrid with a $100,000 viability threshold also has the desired ordering, but it
does not outperform the simpler log model.

## Stability

Prospective improvements are concentrated in 2022. In leave-one-cycle-out
testing, the log-$50k model improves 2014 and 2022 but is 0.31 points worse in
2018. Fundraising appears more informative in the newest cycle, but three
completed electronic-FCPA cycles are insufficient to distinguish a structural
increase from election-specific variation.

The paired row bootstrap for the log-$50k forward predictions gives a mean
absolute-error improvement of 0.73 points with a 95% interval of -0.02 to 1.48
and 97.2% probability of improvement. The $25,000 viability flag improves by
3.23 points with a 95% interval of 2.20 to 4.24. These intervals describe the
observed race sample and do not account for trying multiple transforms and
thresholds.

## Recommendation

Use `log1p(D fundraising / 50,000) - log1p(R fundraising / 50,000)` as the
leading experimental finance feature. Retain the $25,000 viability flag as a
comparison tab, not as the public default. Also retain a $100,000 viability
hybrid as a conservative way to encode a credible-campaign threshold while
preserving the requested $200k-versus-$50k ordering.

Do not promote finance into the public forecast until the remaining PCC review
queue is adjudicated and the experiments are rerun with candidate incumbency,
open-seat status, and district competitiveness interactions. Fundraising is
partly endogenous: competitive candidates attract money, so these results are
predictive rather than causal.

Reproduce with `python scripts/run_fcpa_fundraising_experiments.py`.
