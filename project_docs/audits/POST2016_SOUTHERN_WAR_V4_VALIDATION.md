# Post-2016 Southern WAR v4 validation

## Result

The finance-free V4 research pipeline reconciles exactly and now covers every
strict race except 31 review-only Mississippi 2019 contests. It is not approved
for publication.

- Model run: `WAR-SOUTH-V4-20B574D955B9BF08B704`
- Central 2020 context allocation: `RUN-3F9B3CEA244646B796CF86E962A919FE`
- VEST 2016 allocation: `RUN-F1AF08B0478A4B34BA87DE80E91F1CAF`
- Historical exact-plan allocation: `RUN-ECFBAD9189AB4074A042DEEEECB33D3E`
- Four-state 2012 precinct allocation: `RUN-2EFD501D5FCA4AB0A60611AE766DB2A8`
- Mississippi district-readiness allocation: `RUN-971118910F5E4DF68E316573C3AAABB2`

| Check | Result |
|---|---:|
| Strict 2017-2022 input races | 2,800 |
| Direct election-year ACS joins | 2,800 |
| Exact required presidential histories | 2,769 |
| Research WAR scores | 2,769 |
| Unscored review-only races | 31 |
| Maximum WAR identity error | 0.0 |

All remaining incomplete rows are Mississippi 2019: 19 lower-chamber and 12
upper-chamber contests. Missing context is null in the race file; neither its
structural expectation nor WAR is calculated.

## Forward diagnostics

| Holdout | Training rows | Test rows | Model MAE | Zero-adjustment MAE |
|---:|---:|---:|---:|---:|
| 2019 | 1,025 | 113 | 7.252 | 7.536 |
| 2020 | 1,138 | 870 | 9.994 | 5.979 |
| 2022 | 2,008 | 761 | 4.855 | 5.635 |

These are model diagnostics, not WAR definitions. The mixed forward result,
especially the 2020 loss to the zero-adjustment comparator, remains a
publication blocker.

## Historical context disposition

Exact 2016 and 2020 context is complete for all 14 states on the relevant
modern plans. Historical allocations supply the earlier plan context for every
strict race outside Mississippi's unresolved set. The dedicated 2012 allocator
passes all 14 state/plan/chamber cells for Florida, Georgia, North Carolina,
and Virginia, producing 1,272 district rows from 14,436 prepared precincts and
54,537 precinct/district weights. Alabama's official SOS-reconciled 2012
source covers all 67 counties and explicitly retains four county-only rows
where the archive reports precinct detail unavailable.

Mississippi's corrected 2012 source contains 1,867 result rows and 1,273,695
two-party votes. The conservative crosswalk accepts 1,733 rows representing
1,188,380 two-party votes; 134 rows and 85,315 votes remain unresolved. The
exact 2019-plan allocation marks 49 of 122 House districts and 19 of 52 Senate
districts passed. Only 9 of the 40 observed contested races fall in those
passed districts. The other 31 remain unscored. The statewide chamber audits
remain review, with 59,892 House-allocation and 41,519 Senate-allocation
two-party votes unresolved.

The 2019 RDH/VEST archive used for later VTD/name aliases is pinned at SHA-256
`b43a1ba41c75e584a2e22fb9f34597b9e2929d373a61d975719088c9d569acc9`.
Its embedded README records RDH's upstream retrieval and source lineage. Its
votes do not enter the 2012 allocation.

## Reproduction

```powershell
python scripts/register_mississippi_2019_precinct_alias_source.py
python scripts/audit_mississippi_2012_precinct_plan_readiness.py
python scripts/build_mississippi_2012_partial_plan_allocations.py
python scripts/retrain_post2016_southern_war_v4.py
python -m pytest scripts/tests/test_mississippi_2012_partial_plan_allocations.py scripts/tests/test_post2016_southern_war_v4.py scripts/tests/test_southern_context_allocations.py scripts/tests/test_southern_context_warehouse.py scripts/tests/test_southern_2016_vest_warehouse.py scripts/tests/test_southern_2016_vest_plan_allocation.py -q
```

The focused validation suite passes 27 tests. Publication and website
regeneration remain intentionally blocked until the outstanding source
ambiguity and model-performance gate are resolved.
