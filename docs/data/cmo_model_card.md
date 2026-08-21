# Alabama Legislative Candidate Margin Overperformance model card

## Status and intended use

Candidate Margin Overperformance (CMO) is a retrospective description of how
far a Democratic or Republican candidate side ran ahead of an independently
constructed district electoral expectation. It covers contested Alabama House
and Senate general elections from 1994 through 2022. The 1994 rows remain a
sensitivity tier because their geography and presidential context require more
fallback allocation.

CMO is not wins above replacement, a causal personal effect, a forecast, or a
win probability. A race residual can contain candidate quality, opponent
quality, local political structure, measurement error, biography, ideology,
campaign execution, and omitted events. Republican and Democratic side scores
remain zero-sum within a race.

## Four distinct outputs

### Raw ticket overperformance

The observed legislative Democratic margin minus the source-aware same-cycle
district ticket baseline. This is the least modeled quantity.

### Context CMO

The observed margin minus a cycle-held-out expectation using only non-candidate
context. Its features are prior presidential margin, demographics, chamber,
state-versus-federal context, federal availability, and baseline geographic
quality. It excludes ideology, incumbency, current finance, candidate history,
winning status, and all other candidate-derived features.

### Within-cycle CMO

Context CMO minus the median context CMO in the same chamber and election
cycle. This removes shared chamber-cycle displacement and is the preferred
cross-era comparison. Absolute context CMO remains available because it retains
genuine caucus-wide ticket divergence.

### Predictive expected-performance residual

A separately named prediction error from a model that may use incumbency,
open-seat status, finance, and strictly lagged candidate history. It may
optimize election prediction but does not define historical CMO.

## Source-aware electoral baseline

Governor and Attorney General votes are summed before calculating a district
margin. This vote-weights the two available statewide measurements. In 2018
and 2022, a usable same-cycle federal index receives a prespecified 30 percent
weight and the state ticket receives 70 percent. Earlier cycles remain
state-ticket based. Previous presidential margin is a fallback if the state
ticket is unavailable, not another component that double-counts partisanship.

Because the baseline uses same-cycle results, CMO is retrospective and cannot
be calculated before Election Day.

## Eligibility and nominal contests

Every D/R race with positive votes for both parties can receive a descriptive
score. A race is meaningful when the losing party receives at least 10 percent,
marginal at 5–10 percent, and nominal below 5 percent. Nominal races are scored
but excluded from expectation fitting. Raw overperformance is never capped.
Linear expected margins are bounded using training-only residual quantiles and
the logical two-party margin range.

## Estimation and temporal validation

Each context expectation is trained without the cycle it scores. The primary
model is ridge regression in margin space. Robust Huber regression and ridge
regression on the change in logit Democratic vote share are retained as
alternatives. The headline uses the same conceptually available core features
in every era; recent-only region fields are excluded rather than zero-filled.

The nested-forward diagnostic selects among a baseline-only model, three ridge
penalties, Huber regression, and logit ridge using only earlier cycles. It then
scores the next cycle without revising the choice after observing that result.
This tests specification transfer; its same-cycle baseline still makes the
result retrospective.

## Candidate and opponent attribution

The race score cannot identify the two candidates independently. A secondary
crossed model represents each race as a Democratic person effect minus a
Republican person effect. Ridge regularization supplies the identifying
constraint and shrinks sparse candidates. Historical `person_id` values are
not trusted automatically because some are surname buckets. Longitudinal keys
use normalized full names; any full name appearing in multiple races in the
same cycle is conservatively split by chamber and district. Surname-only rows
are race-specific and do not contribute longitudinal identity evidence until a
manual crosswalk resolves them. Appearance count, identity status, and
attribution reliability accompany every partial-pooled effect.

## Uncertainty

The race-specific band measures uncertainty in the expectation, not ordinary
prediction error around a residual. It combines disagreement among
baseline-only, ridge, Huber, and logit expectations; geographic-fallback share;
and marginal/nominal-contest penalties. It is a specification/data-quality
band, not a confidence or predictive interval.

## Construct validation

The release measures same-candidate persistence, the bivariate association
between prior CMO and next-cycle winning among repeat candidates,
different-candidate same-seat persistence within a district plan, and successor
performance after an incumbent candidate departs. It does not claim to observe
the reason for departure or to estimate an independently controlled future-win
effect.

In the current build, 77 conservatively linked repeat-candidate observations
show positive persistence: Spearman correlation is approximately 0.50 for raw
ticket overperformance and 0.37 for within-cycle CMO. Different-candidate same-seat
persistence is approximately 0.49 across 173 pairs with resolved identities. The
bivariate association between prior CMO and next-cycle victory is small and
negative in the repeat sample; it is not a controlled predictive test. These
results show that unmeasured seat context remains and CMO is not a pure personal
effect.

## Current diagnostic summary

The v2 build contains 509 eligible races across eight cycles. Cycle-balanced
mean absolute error is approximately 16.04 points for the source-aware baseline,
14.71 for context ridge, 14.57 for context Huber, 14.33 for context logit ridge,
15.32 for nested-forward selected expectations, and 12.68 for the fully
predictive model. The predictive advantage is expected because that model may
use candidate-derived information.

## Release rules

- Candidate tables default to context CMO and expose raw, within-cycle, and
  partial-pooled views.
- Cross-era comparisons should use within-cycle CMO.
- Ideology, incumbency, and finance analyses use candidate-variable-free
  context CMO and treat those variables as explanations.
- Forecasts use expected performance, not CMO labels as probabilities.
- Nominal contests, incomplete geography, and the 1994 sensitivity tier remain
  visibly flagged.
- Negative generalization results may not be described as validated prediction.

## Principal limitations

- Only eight cycles are available and Alabama changed politically across them.
- Same-cycle ticket results prevent prospective use.
- Federal context is incomplete in some historical districts.
- Historical geography and demographics vary in quality, especially in 1994.
- Most candidates appear only once, limiting candidate/opponent separation.
- Successor persistence demonstrates remaining unmeasured local context.
- The modern federal weight is prespecified rather than precisely identified by
  many genuinely future cycles.

Machine-readable outputs use `data/processed/war/cmo_v2_`. The detailed report
is `project_docs/model/CMO_METHODOLOGY_V2.md`.
