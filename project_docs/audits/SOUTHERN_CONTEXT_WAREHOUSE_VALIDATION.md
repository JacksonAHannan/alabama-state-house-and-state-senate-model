# Southern context warehouse validation

Schema version 17 centralizes the acquired presidential context and
election-year legislative boundaries without treating co-located inputs as a
validated geographic join.

Build run: `RUN-B60F18E1B9CD4DAE89BBBF4F59338A99`

## Validated contents

| Schema-17 source-family object | Rows |
|---|---:|
| Presidential result geographies | 3,224,020 |
| Validated presidential result geographies | 3,221,297 |
| Review presidential result geographies | 2,723 |
| Legislative boundary layers | 90 |
| Legislative district features | 7,520 |
| Accepted result-to-geometry links | 0 |

These counts are scoped to the schema-17 source family. Schema version 19 later
adds VEST 2016 precinct results and matched precinct geometry without changing
or implicitly linking these source rows.

The result table includes the five supplied 2012 precinct sources, the
Southern-state subset of the nationwide RDH 2020 block result, and the 2024
New York Times precinct-result CSV. The 90 Census state/cycle/chamber
cartographic-boundary ZIPs are normalized to EPSG:4326 WKB and retain their
source CRS, source identifier, feature hash, extent, and area.

Georgia, Mississippi, North Carolina, and Florida 2012 presidential rows
reconcile exactly after excluding Florida overvote and undervote counters from
candidate votes. The Virginia contest export's precinct rows exceed its state
summary by 6,837 votes. All 2,723 Virginia precinct observations therefore
remain `review` and are excluded from the validated fact view.

The 2020 block values remain fractional and explicitly derived under RDH's
VAP-disaggregation method. They are not recast as observed precinct votes.
The New York Times 2024 TopoJSON is registered and hashed, while its companion
CSV supplies normalized result rows. TopoJSON precinct geometry remains
`registered_unparsed`; district boundaries are fully normalized.

Most importantly, `bridge_southern_result_geography` is empty. A precinct or
block result and a district outline in the same database are not automatically
a model-ready baseline. The next build must create explicit block membership
or audited precinct overlap weights and reconcile allocated votes before WAR
consumes the new tables.

## Validation commands

```powershell
python scripts/acquire_southern_war_v4_context.py --offline
python scripts/load_southern_context_warehouse.py
python -m pytest scripts/tests/test_southern_context_warehouse.py scripts/tests/test_post2016_southern_war_v4.py scripts/tests/test_southern_war_map.py -q
```

The focused suite passed 12 tests.
