# Previous presidential district-context audit

## Finding

The reported 2008 presidential result for the 2010 version of Alabama House
District 32 was wrong. The previous build estimated the district at **R+5.84**.
After enforcing the official-ballot-first precinct hierarchy, the estimate is
**D+24.05** (Obama 11,827 allocated two-party votes to McCain 7,241, rounded).
The Democratic presidential candidate therefore did not lose HD-32 in the
corrected reconstruction.

## Cause

Several distinct Anniston election precincts were matched to the same Census
VTD. That VTD crossed House district lines. The prior hierarchy treated the VTD
split as if it applied identically to every named precinct inside the VTD. For
example, it sent 69.6 percent of both Anniston Carver Center and Anniston Golden
Springs into HD-32 even though the official 2010 legislative returns reported
HD-32 at Carver Center and did not report HD-32 at Golden Springs.

A Census VTD is not a stable precinct identity and may contain more than one
election precinct. The repaired hierarchy is:

1. One legislative district reported for a named precinct: allocate 100 percent
   to that district.
2. Multiple legislative districts reported for the same named precinct: divide
   using its observed legislative ballot activity.
3. No reported legislative district: use matched spatial evidence, then an
   explicitly labeled county fallback.
4. Countywide absentee/provisional batches remain distributed rather than
   treated as polling places.

## Scope of changes

Every presidential source-to-target pair was rebuilt from the repaired weights.
All 140 House/Senate district rows remain present where the source is complete,
and vote totals are conserved independently for each chamber.

| Presidential source -> legislative cycle | District rows changed | Median absolute change among changed rows | Maximum absolute change | Sign changes |
|---|---:|---:|---:|---:|
| 2008 -> 2010 | 139 of 140 | 5.353 points | 59.829 points | 7 |
| 2012 -> 2014 | 123 of 140 | 0.246 | 11.137 | 0 |
| 2012 -> 2018 | 118 of 140 | 0.091 | 1.734 | 0 |
| 2016 -> 2018 | 120 of 140 | 0.100 | 2.928 | 0 |
| 2016 -> 2022 | 108 of 140 | 0.063 | 12.486 | 0 |
| 2020 -> 2022 | 127 of 140 | 0.078 | 9.599 | 0 |

The particularly large 2008-to-2010 changes reflect the exact defect under
review: the older source depended much more heavily on shared Census VTD
geometry. Later election pairs already had closer precinct identity matches,
so their median changes are small even though a few districts still move
materially.

## HD-32 trace

| Field | Previous | Corrected |
|---|---:|---:|
| 2008 Democratic presidential margin | -5.841 | +24.053 |
| Allocated Democratic votes | 6,871 | 11,827 |
| Allocated Republican votes | 7,723 | 7,241 |
| Source-county coverage | Complete | Complete |

The result remains an allocation estimate because 2008 and 2010 precinct names
are not perfectly identical and countywide ballot batches have no precinct
geography. Its party direction is no longer ambiguous under the authoritative
same-plan legislative ballot evidence.

## Validation

- Regression fixtures prove that two distinct precincts sharing a
  multi-district VTD retain their separate one-district ballot assignments.
- A genuinely split precinct retains its observed legislative-activity shares.
- Presidential allocation tests enforce source-vote conservation, source
  coverage, county-batch treatment, and the corrected positive HD-32 margin.
- Commands:
  - `python scripts/build_canonical_geographic_weights.py`
  - `python scripts/build_geographic_crosswalks.py`
  - `python scripts/build_presidential_district_features.py`
  - `python -m pytest scripts/tests/test_build_geographic_crosswalks.py scripts/tests/test_build_presidential_district_features.py -q`
