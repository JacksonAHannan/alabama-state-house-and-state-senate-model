# Southern 2016 VEST plan-allocation validation

## Result

Warehouse schema version 20 provides validated 2016 presidential margins on
the enacted 2022 legislative plan for all 14 Southern model states.

- Build run: `RUN-F1AF08B0478A4B34BA87DE80E91F1CAF`
- Official Census block archives: 14
- Precinct/district weight rows: 96,114
- District-result rows: 2,266
- State/chamber audits: 28
- Review audits: 0
- Two-party votes using geometry-area fallback: 4,160
- Maximum state/chamber fallback-vote share: `0.0004262917`
- Maximum unmatched-VAP share: `0.0000077835`
- Maximum precinct weight-sum error: `1.11e-16`

## Sources and allocation

The source votes and precinct polygons are VEST 2016, Harvard Dataverse DOI
`10.7910/DVN/NH5S2I`, version 97, CC BY 4.0. The allocation uses official
TIGER2020 Census block polygons, RDH 2020 modified voting-age population, and
the validated RDH national 2022 state-legislative block assignment. Every raw
archive is immutable and hash-registered.

For each state, a Census block representative point selects its VEST precinct.
Duplicate point matches and unmatched positive-VAP blocks touching a precinct
are resolved by greatest polygon-intersection area. Precinct-to-district
weights are the share of matched 2020 modified VAP in each legislative
district. Geometry-intersection area is used only where a vote-bearing
precinct has no positive-VAP block match; its affected vote share is audited.
Seventy-two Louisiana BAF omissions have zero VAP and are explicitly excluded,
not assigned or zero-filled.

## Acceptance gates

Every vote-bearing precinct must receive an allocation; every precinct's
weights must sum to one within `1e-10`; unmatched VAP and fallback votes must
each be at or below 0.1% within every state/chamber; and allocated Democratic
and Republican totals must separately reconcile to their VEST source totals.
All gates passed.

## Reproduction

```powershell
python scripts/acquire_southern_2016_precinct_geography.py --offline
python scripts/load_southern_2016_vest_warehouse.py
python scripts/acquire_southern_context_assignments.py
python scripts/build_southern_context_allocations.py
python scripts/acquire_southern_2020_census_blocks.py --offline
python scripts/build_southern_2016_vest_plan_allocation.py
python -m pytest scripts/tests/test_southern_2016_vest_plan_allocation.py -q
```
