# Historical precinct geometry audit

## Objective

Use documented precinct changes and known legislative race assignments to reduce cross-cycle ambiguity and create explicitly approximate precinct geometry for 1994, 1998, 2002, and 2006.

These outputs are analytical reconstructions. They are not certified precinct maps.

## Method

1. Read every historical precinct/district relationship established by positive State House or State Senate ballot activity.
2. Use the nearest available Census VTD donor: Census 2000 for 1994–2002 and Census 2010 for 2006.
3. Match within county using VTD code, normalized precinct name, or fuzzy name.
4. When names or codes identify multiple VTD fragments, use the intersection of the known House and Senate district assignments to select the compatible fragment.
5. Compare the physical precinct count with the usable donor-VTD count within each cycle and county. Equal inventories are solved as a district-constrained bijection: each precinct gets one cell and each cell gets one precinct.
6. Only an overflow inventory (more precincts than VTD cells) permits multiple precincts in one VTD. Unresolved overflow locations may use geocoding and the shared donor is then physically partitioned. Underflow and internally inconsistent equal inventories remain reviewable rather than being forced through geocoding.
7. Clip the donor VTD to the known cycle-specific legislative district polygon.
8. Flag every match with a potentially relevant DOJ Section 5 boundary-change submission between the donor snapshot and election date.
9. Preserve unresolved records in a review queue rather than fabricating a location.

The follow-up pass also treats suffix fragments such as `Center 1`, `Center 2`, `Box 3`, and numbered district tables as possible children of one parent polling place. The ballot records remain separate and the donor VTD is clipped independently into every observed House and Senate district.

An adjacent-cycle graph connects 1994, 1998, 2002, 2004, 2006, 2008, and 2010 precinct identities using names, codes, split-base names, and county-relative turnout. Exact code/name/parent evidence may create one-to-many or many-to-one split/merge edges. A donor identity propagates through a component only when its strong seeds agree on one VTD.

Finally, unresolved named locations in overflow inventories were submitted to a geocoder. A result is accepted only when the returned name remains similar to the historical polling-place name, the result is in Alabama and inside the stated county, and the point falls in a donor VTD compatible with the known legislative races. Multiple geocoded precincts may occupy that VTD.

When a donor VTD contains multiple historical precincts within the same legislative-district slice, the output physically partitions the donor polygon. Geocoded polling places are Voronoi seeds. Missing co-occupant locations receive deterministic synthetic seeds and a low-confidence label. A failed partition is withheld rather than represented by overlapping duplicate polygons.

## Results

The inventory-aware audit covers 9,972 historical precinct identities. It classifies 1,106 rows in equal-count inventories, 7,324 in overflow inventories, and 1,542 in underflow inventories. The equal-inventory global assignment resolved or reconciled 337 rows; 31 equal-count county/cycle inventories are now complete bijections. Two remain internally inconsistent (1994 Jefferson and 1998 Baldwin), leaving 78 equal-inventory rows unresolved rather than forcing them.

Geocoding is confined to overflow. Expanded historical-name queries produced 1,022 accepted resolution records; 902 final audit assignments rely on geocoded polling-place evidence after stronger code, alias, and inventory matches take precedence.

The subsequent iterative pass freezes every completed equal-inventory bijection and
only fills null donor identities. In each round it first propagates an adjacent-cycle
donor when all resolved neighbors agree on one donor of the correct Census vintage.
It then assigns a unique district-compatible cell: unused and exclusive for underflow
inventories, reusable for overflow inventories. Iteration stops at a fixed point.

The final iterative state contains 222 assignments (171 adjacent-cycle consensus and
51 uniquely compatible overflow cells). County-specific Mobile, Lee, and Morgan code
decoders account for another 187 assignments, a relaxed fragment-aware solve closed
the 78 remaining equal-inventory gaps, and two aliases came from validated same-year
primary ordering. The physical review queue fell from 1,927 before this sequence to
1,376: 856 overflow and 520 underflow. All 320 administrative/county-level records are
explicitly non-geographic. The 832 frozen physical one-to-one assignments retained
the exact pre-iteration mapping hash
`ccec4ff703e69491563f0e8e1e2e99290f64c10b11d9612d11c319dfcb440a7b`.

| Cycle | Chamber | Precinct/district slices | Geometry produced | Row coverage |
|---|---|---:|---:|---:|
| 1994 | House | 2,950 | 2,153 | 73.0% |
| 1994 | Senate | 2,793 | 2,117 | 75.8% |
| 1998 | House | 2,979 | 2,430 | 81.6% |
| 1998 | Senate | 2,904 | 2,407 | 82.9% |
| 2002 | House | 3,094 | 2,477 | 80.1% |
| 2002 | Senate | 2,901 | 2,357 | 81.2% |
| 2006 | House | 2,523 | 1,963 | 77.8% |
| 2006 | Senate | 2,300 | 1,854 | 80.6% |

All produced geometries are valid. Nineteen 1998 Senate source assignments referenced district 36, which does not exist in the applicable 35-seat plan; these were quarantined rather than mapped.

The DOJ calendar downgraded 1,302 otherwise matched precinct identities because a likely geometry-change submission occurred between the election and donor VTD vintage. This is a county/date warning until underlying submission packets identify the exact affected precincts.

The local OpenElections Alabama precinct archive begins in 2012, so it supplies no independent 1994–2006 same-election names or vote totals. No historical match is labeled as OpenElections-supported. If older OpenElections files are later located, they can be added as a new evidence layer without changing the current confidence labels.

## Outputs

### Manual adjudication queue

`scripts/build_historical_precinct_adjudication_queue.py` ranks unresolved physical
precincts by legislative ballot activity. It retains the maximum all-office vote
total only as a diagnostic because split rows can repeat or aggregate statewide
totals. Calculated/reported county totals are flagged as administrative records and
excluded from the physical top-200 queue.

The queue combines the known legislative race assignments, donor-name suggestion,
adjacent-cycle alias edges, cached named-place geocoder candidates, and intervening
DOJ Section 5 descriptions. Its outputs are:

- `historical_precinct_adjudication_queue.csv` (complete queue)
- `historical_precinct_adjudication_top200.csv` (first manual tranche)

Run `python scripts/adjudicate_historical_precinct.py` to review the next case.
Decisions are written to
`data/manual/precinct_history/historical_precinct_adjudications.csv`. Accepted donor
decisions are consumed by the audit before the last-resort district-constrained
approximation. A manually selected donor must still intersect the precinct's known
House/Senate ballot districts; invalid selections are not silently forced into the
map.

- `historical_precinct_geometry_audit.csv`: one row per historical precinct identity, including donor, method, scores, DOJ flags, and confidence inputs.
- `historical_precinct_geometry_review_queue.csv`: unresolved named precincts with known House/Senate race assignments and the best name suggestion.
- `historical_precinct_invalid_district_assignments.csv`: source records inconsistent with the applicable legislative plan.
- `historical_precinct_geometry_audit_summary.csv`: cycle/chamber/confidence counts.
- `adjacent_cycle_precinct_alias_edges.csv`: accepted one-to-one, split, and merge links between neighboring election cycles.
- `adjacent_cycle_precinct_alias_resolutions.csv`: unique donor identities propagated through the graph.
- `historical_precinct_geocode_resolutions.csv`: county-validated named-place points and containing donor VTDs.
- `approximate_{cycle}_{chamber}_precincts.gpkg`: reconstructed precinct/district slices in EPSG:5070.

The GeoPackages include `vtd_occupancy_count` and `vtd_partition_method`. Across the eight outputs, 3,045 shared VTD/district groups were partitioned. Their summed overlap is effectively zero (less than `0.00002 m²` per file, numerical precision only), and every retained geometry is valid.

The many-to-many warehouse contains 8,522 precinct–VTD links, including 246 additional
underflow-union links. Its derived Census-block table contains 625,502 cycle-specific
allocations. Among blocks inside linked donor VTDs, allocation coverage ranges from
98.7% to 99.3%; ambiguous residual blocks remain unassigned.

## Interpretation

The resulting layers are already useful for assigning election results to the correct legislative race and for eliminating false name matches across documented change intervals. They are not yet suitable for precise address lookup, precinct-level demographic interpolation, or claims about the legally exact boundary.

The remaining review queue should be reduced through:

1. OpenElections/source-file aliases and cross-cycle vote-total agreement;
2. the 14 missing DOJ weekly notices and underlying DOJ submission packets;
3. county/Reapportionment Office maps and legal descriptions;
4. manual adjudication of high-activity unresolved precincts before low-value absentee or zero-geography records.
