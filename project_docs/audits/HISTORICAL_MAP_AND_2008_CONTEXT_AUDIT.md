# Historical map and 2008 presidential-context audit

## 1992–2000 legislative plan

The public CMO page uses two distinct Census TIGER/Line archives for the 1994
and 1998 election panels:

- `al_lower_1992_2000.zip`: 105 unique State House districts; SHA-256
  `9b457d36f76fb6b36af1c02ce895c6af5eaf5534b8bcf0a9e564a8a05712ee8a`.
- `al_upper_1992_2000.zip`: 35 unique State Senate districts; SHA-256
  `bbb7a3c2e91e6b1c85f8b71571b507ad0319da2f46e95d6b5a44402ce0a05c8d`.

Embedded Census metadata identifies the files as the 2009 TIGER/Line Census
2000 Alabama State Legislative District lower- and upper-chamber products.
Their statewide exterior boundary and total covered area are identical, as
they must be, but their internal district geometries are not. The generated
site payload contains 105 distinct House paths and 35 Senate paths with
different payload hashes. The same chamber map is correctly reused for 1994
and 1998 because both elections used the 1992–2000 enacted plan.

## 2008 official precinct results

The official SOS workbook has 67 county sheets. Two legacy-format issues were
corrected before use:

1. `Calculated` and `Reported` footer rows repeated county totals and were
   previously treated as precinct observations.
2. `President PSC` meant president of the Public Service Commission and was
   previously classified as the presidential contest.

The corrected presidential totals are 813,437 Democratic votes and 1,266,193
Republican votes (2,079,630 major-party votes). Federal Senate and House office
labels were also canonicalized.

## 2008 to 2010 allocation

OpenElections does not publish a 2008 Alabama file; its Alabama repository
starts in 2012. The allocation therefore uses a combined official-source alias
layer. It prioritizes canonical 2010 VTD/population weights, then adds precinct
aliases from the 2006 and 2002 official legislative results. Those elections
used the same enacted legislative plan as 2010.

Current identity results for 2,679 presidential precinct/batch rows:

- 2,101 exact alias matches;
- 140 high-confidence fuzzy matches;
- 72 textually ambiguous matches whose tied aliases have identical House and
  Senate district-allocation vectors;
- 139 explicitly county-level ballot batches; and
- 227 precinct names without a defensible direct identity match.

All rows are allocated and all 140 legislative districts have complete county
source coverage. The 227 unresolved identities use an explicit within-county
district distribution; they are not silently forced to a named precinct.
Thus there are zero unassigned vote rows, but 227 names remain unmatched at
the precinct-identity level. Reducing that second number to zero requires a
reviewed alias table or additional county/VTD source evidence.
