# Black candidate presence and legislative turnout

## Research question

Does having a Black major-party candidate on the Alabama legislative ballot
meaningfully increase turnout relative to the turnout expected for the same
type of district and election?

This is a candidate-entry and turnout study, not a CMO feature promotion. The
treatment is defined before observing the turnout result, but candidate entry
is not random. Black candidates disproportionately run in districts with larger
Black electorates, different partisan baselines, different incumbency patterns,
and different levels of contestation.

## Identity policy and present status

Candidate race is not present in the canonical election warehouse. The project
will not infer it from names, photographs, district composition, or party. An
approved row requires reliable biographical evidence in
`data/manual/candidates/candidate_race_ethnicity.csv`.

For coverage discovery, the pipeline also imports the Reflective Democracy
Campaign's nationwide candidate-demographics workbook. It covers 2014 Alabama
state-legislative candidates well, but its candidate-level source evidence is
not included and its Alabama 2018 race fields are blank. Those rows are labeled
`approved_external_dataset` and are suitable for sensitivity analysis, not a
substitute for reviewed biographical evidence. Manual decisions always override
the external coding.

Running `python scripts/analyze_black_candidate_turnout.py` creates
`black_candidate_identity_review_queue.csv`. Until at least 90% of district-
cycles have reviewed identities for every listed major-party candidate, the
pipeline publishes coverage and the analytical panel but deliberately withholds
the counterfactual estimate.

## Outcomes

The primary outcome is major-party legislative votes divided by district CVAP:

`legislative_turnout_cvap = legislative D+R votes / estimated CVAP`

The secondary outcome is legislative-ticket retention relative to the
same-cycle governor race allocated to the same district:

`legislative_to_governor_retention = legislative D+R votes / governor D+R votes`

The governor-retention outcome controls much of the cycle-specific electorate,
but its geographic allocation quality must be audited and reported. Neither
outcome directly measures Black turnout; an aggregate increase could come from
Black voters, white voters, or both.

## Treatments and estimands

- Any reviewed Black major-party legislative candidate in the race.
- A reviewed Black Democratic legislative candidate.
- All races, estimating the total candidate-presence association.
- Contested D/R races only, a different estimand conditional on contest entry.

Contestation may itself be affected by candidate recruitment, so the
contested-only result is not the total effect of recruiting a Black candidate.

## Counterfactual design

The initial adjusted comparison controls flexibly for Black and Hispanic CVAP
share, white-college share, prior presidential margin, Democratic and Republican
incumbency, cycle, and chamber. It reports propensity-score overlap; estimates
with weak common support should not be interpreted causally.

The production analysis should add:

1. nearest-neighbor or coarsened exact matching within cycle and chamber;
2. 2014-to-2018 within-district changes under the same district plan;
3. a 2022 new-plan analysis kept separate from the older map;
4. clustered uncertainty by district family and a candidate-identity bootstrap;
5. pre-treatment turnout and lagged contest status;
6. finance as a secondary mediator analysis, not a default confounder;
7. Black-CVAP interactions and overlap-stratified estimates;
8. if precinct-level candidate identity becomes possible, heterogeneous turnout
   changes in predominantly Black versus predominantly white precincts.

Even after adjustment, the result should be described as counterfactual evidence
under observed controls rather than proof that candidate race alone caused the
turnout change.

## Preliminary 2014 sensitivity result

The archived Reflective Democracy workbook produces 150 usable Alabama
candidate classifications in 2014 and 99 district-races in which every listed
major-party candidate is classified. Thirty of those races have a Black
candidate; in this subset every classified Black major-party candidate is a
Democrat, so the two treatment definitions are identical. This is only 23.6%
of the intended 2014-2022 panel.

The adjusted exploratory estimates do **not** presently support the claim that
a Black candidate meaningfully increased overall turnout:

| Scope | Outcome | Estimate | Exploratory 95% bootstrap interval | Overlap share |
|---|---|---:|---:|---:|
| 99 classified 2014 races | Legislative votes / CVAP | -0.4 points | -3.1 to +2.3 | 22% |
| 99 classified 2014 races | Legislative / governor retention | +11.2 points | +0.1 to +21.1 | 22% |
| 23 classified contested D/R races | Legislative votes / CVAP | -3.2 points | -5.9 to -0.6 | 78% |
| 23 classified contested D/R races | Legislative / governor retention | +6.0 points | -1.4 to +10.9 | 78% |

The positive all-race retention estimate is not reliable counterfactual
evidence because common support is extremely weak and it is sensitive to
whether the legislative race is contested. The contested-only sample is just
23 races. Its CVAP result points in the opposite direction, while its retention
interval includes zero. These conflicting outcomes are a warning about
selection and denominator choice, not evidence of demobilization.

The defensible current conclusion is therefore **insufficient evidence**, not a
positive turnout effect and not a negative causal effect.

## Remaining identity sources

- Reflective Democracy's catalog describes a nationwide candidate race/gender
  collection covering 2012-2018, but its Alabama 2018 race fields are blank in
  the recovered workbook.
- RDH publishes an Alabama 2022 State Senate candidate race/gender file with
  source type, source URL, and confidence, but downloading the CSV requires a
  free RDH login. Only candidate-reported, organization, or news-supported rows
  should be promoted; RDH rows marked as guesses should remain sensitivity-only.
- The repository also contains RDH's corresponding 2022 House file. Together
  the two archives contain 298 primary-candidate records. Most race values are
  marked `GUES` by RDH (219 House and 66 Senate records), so those rows are
  excluded from the primary treatment. Only rows sourced to the candidate or a
  third-party report with a URL are admitted automatically.
- The remaining 2018 and 2022 candidates require another dataset or manual
  biographical review. RDH's 2020 incumbent-address data can classify some
  winners but cannot identify the full candidate population.
