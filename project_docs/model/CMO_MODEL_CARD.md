# Alabama legislative Candidate Margin Overperformance model card

## Intended use

Candidate Margin Overperformance (CMO) is a retrospective candidate-strength
index for contested
Democratic-versus-Republican Alabama House and Senate general elections from
1994 through 2022. It measures two-party margin percentage points above or
below a cross-fitted model expectation. The 1998–2022 series is the core
historical tier. Fitted 1994 scores are a sensitivity tier because their
geographic and prior-presidential features use substantially more fallback
allocation.

CMO is not wins above replacement, a fully identified causal candidate effect,
a forecast, or a ranking of every legislator. It is the candidate-attributable
electoral signal left after removing measured district and election context.
That signal can include strategic positioning, biography, campaign skill,
constituent relationships, and opponent weakness. Uncontested and non-D/R
races are not scored.

The complete inventory of proposed explanatory and predictive variables,
including their timing and endogeneity classifications, is maintained in
`project_docs/model/CMO_HYPOTHESIS_REGISTRY.md` and its machine-readable CSV.

## Scores

- **Total CMO** is the headline, selection-aware candidate-strength score.
  It adjusts for prior presidential margin and trend, demographics, cycle, and
  chamber. It deliberately does not adjust for incumbency or prior candidate
  performance: winning office and surviving to run again are partly downstream
  of candidate strength, so controlling them away would bake survivorship into
  the score.
- **Predictive Total** retains the former party-specific incumbency controls.
  It is the better election-outcome predictor, but is no longer interpreted as
  the candidate-performance estimand.
- **Candidate-history forecast** adds strictly lagged prior contested
  overperformance, prior unopposed status, and first-term/established-incumbent
  indicators. It is a forecast sensitivity, not a CMO ranking.
- **Resource-adjusted CMO** additionally adjusts for the D/R spending balance.
- **Fundraising-adjusted CMO** is a sensitivity specification using
  FollowTheMoney candidate fundraising totals. Missing FTM candidates remain
  unknown rather than being assigned zero dollars.
- Both public scores use nested out-of-fold predictions. The model scoring a
  race did not train on that race.
- Republican scores are the sign reversal of the Democratic race residual, so
  scores are zero-sum by construction. The data do not independently identify
  each candidate's contribution.

## Uncertainty and stability

The cross-cycle stability band shows how far the OOF score may move when the
expectation is trained without an entire election cycle. It is deliberately not
labeled a confidence or predictive interval. Leave-one-cycle-out and forward
tests are the primary evidence about transfer across election environments.

## Important limitations

Current all-years build (August 2026): 509 model-eligible contested races across
eight cycles. Selection-aware Total CMO random-fold MAE is 15.92 points
(R² 0.153); leave-cycle-out MAE is 16.92 (R² 0.067). Predictive Total performs
better, at 13.79 random-fold MAE and 15.60 leave-cycle-out MAE. This difference
is expected because Total CMO no longer conditions away incumbent selection.
Mean true-forward MAE is 16.71 for Total CMO, 15.79 for Predictive Total, and
16.07 for the candidate-history forecast, so lagged history has not cleared the
gate for promotion as the production forecast. The index is useful
retrospectively but is not uniformly predictive across new election
environments. Nine rows with positive incumbent matches for both parties are
neutralized and carry an `incumbency_conflict` flag.

- The fitted canonical build contains eight cycles. Official 2008 presidential
  precinct results are normalized, but historical finance coverage remains
  uneven and is not required by the headline specification.
- For 1994,
  official ballot labels assign single-district precincts exactly; split
  precincts use legislative-activity shares labeled
  `legislative_activity_split_provisional`. Allocation coverage is 98.1%-99.3%
  across chamber, office, and party cells, and unmatched votes remain in a
  review table. These limitations make 1994 a sensitivity tier.
- The 1994 demographic features use official 1990 Census SF3 tract counts
  intersected with the 1992-2000 legislative plan. They cover all 140 districts
  and reconcile 99.997% of the mapped Census population, but tract-area
  interpolation is less precise than a block-level allocation.
- The 1994 prior-presidential feature uses official 1992 Clinton/Bush precinct
  returns. Wilcox is absent from the archive, while Montgomery and Talladega
  contain blank presidential columns. Of 71 score-eligible races, 66 receive a
  margin and 62 have complete source-county coverage. The median fallback share
  is 60.7%, so this feature remains provisional and must carry its fallback and
  completeness fields into any model comparison.
- Seventy-four 1994 candidates have positive incumbency evidence from a unique
  chamber-level surname match to a 1990 general-election winner. Unmatched
  candidates remain unknown rather than being classified as non-incumbents.
  Shor-McCarty's 1996 serving roster corrects party labels for unopposed winners
  where the 1994 workbook's ballot-order inference is not informative.
- DIME contains no 1994 Alabama legislative recipient observations. All 1994
  candidate finance values remain null with status
  `not_observed_unknown_not_zero`; finance-adjusted 1994 scores cannot yet be
  estimated.
- The 2010 and 2014 environments are structurally different and much noisier.
- Forward-cycle performance remains era-dependent, particularly in 2014 and
  2018. The fitted historical index must not be described as a prospective
  forecast or as uniformly validated across unseen cycles.
- District allocation is now independent of legislative turnout. Census block
  population connects VTDs to the applicable legislative plan. Precinct labels
  without a defensible VTD match fall back to county population district shares
  and are retained as a source-quality limitation.
- Eleven genuine competing-VTD assignments remain. Across the audited link
  scenarios, the largest district baseline range is 1.735 points; only one
  scored race has a range of at least one point.
- Campaign-finance identities and presidential precinct fallbacks are
  incomplete for some races, especially in older cycles. Spending and FTM
  fundraising therefore remain secondary specifications and do not solve era
  generalization.
- Same-cycle statewide baselines make the index historical rather than usable
  before Election Day.
- Saved Wikipedia pages provide an independent, non-certified validation check:
  520 of 778 canonical 2010–2022 Democratic/Republican candidate totals match
  exactly. Nonmatches and ambiguous page structures remain in a review file and
  do not overwrite SOS-derived totals.

## Release gates

Public rankings must use Total CMO OOF, show resource-adjusted CMO separately,
call the uncertainty display a stability band, disclose source-quality flags,
and publish random, district-grouped, leave-cycle-out, forward, and benchmark
diagnostics. Predictive Total must not be substituted for Total CMO in candidate
rankings, and Total CMO's weaker predictive fit must not be described as a
forecast failure: the two specifications answer different questions. A
negative leave-cycle-out R-squared blocks claims that a model generalizes to
unseen election eras; it does not invalidate descriptive use.
