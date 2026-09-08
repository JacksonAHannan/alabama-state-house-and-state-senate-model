# Southern presidential district allocation validation

## Result

Warehouse schema version 18 provides a validated, reusable allocation of the
national 2020 presidential block result to Southern state-legislative districts
on the 2022 and 2024 election plans.

- Build run: `RUN-3F9B3CEA244646B796CF86E962A919FE`
- Assignment sources: 2
- Southern block-assignment rows: 6,324,382
- District-result rows: 4,532
- State-plan-chamber reconciliation audits: 56
- Review audits: 0
- Minimum two-party vote coverage: `0.9999999999999728`
- Exact-plan geometry links: 1,762

Each national archive contains 8,126,956 Census blocks, of which 3,162,191
belong to the 14-state Southern model universe. The bridge is unique on source,
state, and 15-digit block GEOID. District totals preserve Democratic,
Republican, other, and total vote fields; stored two-party margins reproduce
their component vote calculation within `1e-12`.

## Source and join contract

The immutable 2022 and 2024 Redistricting Data Hub archives are registered in
`southern_context_assignment_manifest.csv` with URL, retrieval time, SHA-256,
terms, geographic vintage, cycle, and authoritative scope. The allocation joins
the validated Redistricting Data Hub 2020 block result to an assignment only on
exact state and Census block GEOID. It never substitutes a neighboring block,
plan, or election year.

The district result joins geometry only when the warehouse contains exactly one
validated feature for the same state, plan cycle, chamber, and district.
Missing geometry does not invalidate a vote allocation and is not silently
replaced with another vintage.

## Scope limit

This schema-version-18 stage answers 2020-on-2022-plan and
2020-on-2024-plan questions. Schema version 20 separately adds validated VEST
2016-on-2022-plan results; see
`SOUTHERN_2016_VEST_PLAN_ALLOCATION_VALIDATION.md`. Neither stage turns raw
2012 precinct results into historical-plan district margins.

## Reproduction

```powershell
python scripts/acquire_southern_context_assignments.py
python scripts/load_southern_context_warehouse.py
python scripts/build_southern_context_allocations.py
python -m pytest scripts/tests/test_southern_context_warehouse.py scripts/tests/test_southern_context_allocations.py -q
```
