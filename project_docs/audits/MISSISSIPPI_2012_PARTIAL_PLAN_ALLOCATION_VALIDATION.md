# Mississippi 2012 partial plan-allocation validation

## Decision

The 2012 presidential source is not complete enough for a statewide pass on
the legislative plan used in 2019. District-specific readiness is permitted
under schema version 25, and only 68 of 174 district rows pass. All other rows
remain in the mart as review data and are absent from the central fact view.

- Build run: `RUN-971118910F5E4DF68E316573C3AAABB2`
- Result rows: 1,867
- Accepted one-to-one precinct matches: 1,733
- Unresolved rows: 134
- Source two-party votes: 1,273,695
- Matched two-party votes: 1,188,380
- Passed districts: 49 House and 19 Senate
- Review districts: 73 House and 33 Senate

## Controls

Matches are county-scoped and one-to-one. Exact native names, exact same-code
later names, and exact ballot VTD codes receive explicit priority. Conservative
fuzzy matches require score and separation thresholds. Later geometry aliases
are added only for polygons mutually at least 90% coincident. Every unresolved
row retains all plausible donor IDs instead of receiving a guessed match.

Accepted donors are allocated to the exact 2019 plan with 2020 modified VAP.
Four donor geometries per chamber have no positive-VAP block and use a labeled
geometry-intersection-area fallback. Every donor's weights sum to one within
`1.12e-16`, and no positive VAP is unmatched from the plan.

An unresolved result is assigned only when all of its plausible donors fall in
one district for the chamber. A district passes only when no remaining
cross-district ambiguous result could touch it. The full House and Senate
source-reconciliation rows deliberately remain `review`.

## Remaining blocker

Among the 40 strict Mississippi 2019 races, five House and four Senate races
pass the district gate. The other 31 require additional official precinct
identity evidence or a validated block/precinct crosswalk. Their presidential
context and WAR remain null. The exact race-level queue, candidate names,
ambiguous vote exposure, and resolution requirement are exported to
`data/processed/presidential/mississippi_2012_partial_plan_allocations/war_blocked_races.csv`.

The Redistricting Data Hub publishes a potentially useful
[Mississippi 2015 precinct-history package](https://redistrictingdatahub.org/dataset/mississippi-2015-general-election-precinct-boundaries-and-selected-election-results/),
but its archive download redirected to an authenticated login on 2026-09-04.
It was therefore not acquired, and no facts from it are assumed. Supplying
that registered archive or equivalent official county precinct-identity
evidence is the shortest known path to another conservative matching pass.
