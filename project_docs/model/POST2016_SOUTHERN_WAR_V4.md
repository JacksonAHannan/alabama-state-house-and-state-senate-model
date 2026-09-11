# Post-2016 Southern WAR v4: finance-free presidential residual

## Status

V4 is a research candidate and is **not approved for publication**. The ACS
and election-result joins validate, and exact-vintage presidential history is
complete for 2,769 of 2,800 strict 2017-2022 races currently available to the
build. All 31 remaining gaps are Mississippi 2019 races whose unresolved 2012
precinct identity can affect more than one legislative district. They remain
unscored rather than being encoded as zero, guessed, or replaced by a
statewide-ticket result. All 761 strict 2022 races are covered.

## Estimand

Every value is expressed as Democratic two-party margin points.

`environment_baseline = current district presidential margin + national environment swing`

`raw_gap = legislative margin - environment_baseline`

`WAR = raw_gap - fitted structural expected gap`

The national-environment adjustment is zero in a presidential election and is
the realized national House-versus-prior-presidential swing in 2018 and 2022.
For 2019 it is the election-day generic-ballot margin minus the 2016 national
presidential margin.  This definition keeps a presidential comparison in every
cycle instead of switching among governor, Senate, and House baselines.

## Structural regression

The same-cycle descriptive regression contains:

- recent district presidential margin;
- the environment-adjusted current margin minus each of two earlier
  presidential margins;
- symmetric incumbency balance (`Dem incumbent - Republican incumbent`);
- ACS nonwhite population share;
- ACS white non-Hispanic college graduates as a share of all residents age
  25 or older;
- state and chamber intercepts.

The two swing variables are genuine district presidential comparisons.  V4
does not use V3's ticket-change-by-calendar-time interaction and does not enter
algebraically redundant current-ticket, prior-ticket, and change columns.
Separate cycle fits allow the observed relationship between presidential swing
and downballot lag to be weaker in 2022 than in 2018 if the data support that.

Finance, ideology, candidate history, and pooled candidate effects are absent.
Candidate-cycle scores are only party orientations of the single race
residual: Democratic WAR equals race WAR and Republican WAR equals its
negative.

## Presidential vintages

- 2018-2019 require 2012 and 2016 margins on the election-year plan; the 2016
  margin is shifted by the current national environment.
- 2020 requires 2012, 2016, and actual 2020 margins on the 2020 plan.
- 2022 requires 2016 and 2020 margins on the enacted 2022 plan; the 2020 margin
  is shifted by the 2022 national environment.

The central warehouse aggregates the nationwide 2020 block result through the
national 2022 block-assignment file. It also allocates 45,990 VEST 2016
precinct results to that plan using 2020 Census-block voting-age population.
Each modern year produces 2,266 state-legislative district rows across the 14 states;
all state/chamber allocations reconcile to their source totals and are read by
V4 from `fact_southern_presidential_district_result`. The raw 2012
presidential returns for Florida, Georgia, Mississippi, North Carolina, and
Virginia are also local and hash-registered in the V4 presidential manifest.
Validated exact-plan historical allocations now make every strict race outside
the 31 Mississippi exceptions context-complete.

Raw precinct returns are not interchangeable with a presidential margin on a
particular legislative plan. The 2016 crosswalk assigns Census blocks to VEST
precincts by representative point, resolves boundary ambiguities by greatest
intersection area, and weights split precincts by 2020 modified VAP. A
geometry-intersection-area fallback is allowed only for vote-bearing precincts
with no positive-VAP block match, and the run fails if fallback votes or
unmatched VAP exceed 0.1%. The validated run used that fallback for 4,160 of
the Southern two-party votes (maximum state share 0.043%), with no review
audits. Separate exact-plan allocation validates the 2012 supplements for
Florida, Georgia, North Carolina, and Virginia. Alabama uses an official-SOS-
reconciled 2012 source, including explicit county-level treatment where the
official archive says precinct detail is unavailable.

Mississippi is gated at district grain. Of 1,867 corrected 2012 result rows,
1,733 are accepted through a conservative one-to-one within-county name
crosswalk and 134 remain unresolved. Every unresolved row retains its plausible
2012 donor set. Only districts with no cross-district ambiguity enter the fact
view: 68 of 174 plan districts pass, including 9 of the 40 observed contested
2019 races used by V4. The other 31 observed races remain null. The 2019
RDH/VEST file supplies hash-registered VTD/name aliases only; it supplies no
2012 votes.

The V4 manifest records every validated central allocation run ID. Migrating
the 2020-on-2022-plan calculation into the warehouse changes lineage, not the
underlying margins: all 2,266 values reproduce the prior direct calculation to
within `7.5e-13` margin points.

## Demographics

`scripts/acquire_southern_sld_acs_v4.py` retains each Census API response as
immutable raw evidence and writes a manifest with URL, retrieval time, hash,
vintage, and scope.  All 2,800 strict input races join to a direct election-year
ACS SLD record.  Census `ZZZ` non-district aggregates are excluded.

The prior Southern ACS script divided white college graduates by the white
25+ population.  V4 instead divides by the total 25+ population, matching the
published description of the amount/share of white college-educated voters;
the within-white rate is retained only as a sensitivity field.

## Validation rule

Forward predictions are diagnostics, not WAR. The current candidate improves
on a zero structural adjustment in the 2019 and 2022 holdouts but loses in the
2020 holdout. The 31 review-only Mississippi races and those mixed time-forward
results still block publication or downstream forecast/site regeneration.
