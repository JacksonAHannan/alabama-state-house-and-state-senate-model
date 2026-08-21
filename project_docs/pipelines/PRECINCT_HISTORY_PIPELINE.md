# Alabama precinct-history pipeline

## Purpose

This pipeline records Alabama precinct geography as a versioned history rather than treating a Census VTD or election-year shapefile as valid for an entire decade. It keeps three classes of evidence separate:

1. **Confirmed events** backed by a certified resolution and accompanying map or legal description.
2. **Documentary candidates** found in DOJ Section 5 notices or other records but not yet tied to complete local documentation.
3. **Inferred changes** detected by comparing dated geographic snapshots.

An inferred relationship must never be promoted to `confirmed` without documentary evidence.

## Current implementation

- `scripts/warehouse_precinct_history_schema.sql` defines source notices, normalized DOJ entries, submission lifecycles, change events and types, snapshots, precinct versions, lineage, and county coverage.
- `scripts/ingest_doj_section5_precinct_history.py` inventories all 777 DOJ weekly notices from April 1998 through June 2013, caches source files, parses HTML, PDF, and XLS notices, retains every parsed entry, and aggregates Alabama records by submission number.
- `scripts/catalog_precinct_geometry_snapshots.py` catalogs dated geometry files without extrapolating their validity.
- `scripts/compare_precinct_snapshots.py` computes old/new overlap measures in EPSG:5070 and labels only inferred relationships.
- `scripts/download_census_2000_alabama_vtd.py` downloads the official Census 2000 Alabama VTD layer and records its URL, timestamp, feature count, and hash.
- `scripts/audit_historical_precinct_geography.py` combines historical ballot district assignments, the nearest Census VTD donor, and DOJ change warnings to build explicitly approximate 1994–2006 precinct layers and a manual review queue.
- `scripts/build_adjacent_precinct_alias_graph.py` links neighboring election cycles using precinct names, codes, split-parent names, and relative turnout, then propagates only uniquely seeded donor identities.
- `scripts/geocode_unresolved_precinct_locations.py` provides the last-resort named-place workflow: cached geocoder evidence, name/type checks, county containment, containing-VTD lookup, and low-confidence output.
- `scripts/repartition_shared_vtd_geometries.py` restores each donor clip and partitions VTDs occupied by multiple historical precincts; it is the fast rebuild path when partition logic changes without changing identity matches.

The current resumable cache contains 763 of the 777 notices linked by DOJ (98.2%). The remaining 14 DOJ links return HTTP 404 and are listed in the failure manifest. These are near-complete archive results, but must not be represented as literally complete until the broken links are recovered from another official copy or archive:

- 58,773 parsed notice entries
- 4,065 Alabama entries
- 2,584 distinct Alabama submissions
- 434 keyword-identified precinct or polling-place candidates

The classifier is deliberately inclusive. A candidate can describe only a polling-place relocation and need not imply a boundary change. Candidate records have `verification_status = documentary_candidate`.

## Observed geometry snapshots

The current catalog contains statewide Census 2010 VTD and VEST 2016, 2018, and 2020 election precinct snapshots. The first adjacent VEST comparisons produced:

| Interval | Unchanged overlap edges | Non-unchanged overlap edges | Counties flagged |
|---|---:|---:|---:|
| 2016–2018 | 1,859 | 232 | 19 |
| 2018–2020 | 1,901 | 134 | 17 |

These are overlap-graph edges, not confirmed legal events. Many-to-many edges can describe one countywide change and source-boundary differences can create false positives.

## Commands

```powershell
python scripts/ingest_doj_section5_precinct_history.py
python scripts/ingest_doj_section5_precinct_history.py --cached-only
python scripts/catalog_precinct_geometry_snapshots.py
python scripts/compare_precinct_snapshots.py OLD.zip NEW.zip --output output.csv
python -m pytest scripts/tests/test_doj_section5_precinct_history.py scripts/tests/test_compare_precinct_snapshots.py -q
```

The downloader defaults to two workers, retries transient failures, preserves successful downloads, and writes `data/processed/precinct_history/doj_notice_download_failures.json`. A later run resumes from the cache.

## Evidence hierarchy

1. Certified county resolution plus map or legal description
2. Dated official county/state GIS or precinct map
3. DOJ Section 5 submission record
4. Election-specific authoritative or validated precinct geometry
5. Census VTD
6. Snapshot-difference inference

## Next source work

1. Recover the 14 broken DOJ notice links from an official replacement URL or archival copy, then rerun the lifecycle aggregation.
2. Ingest the DOJ Alabama determination-letter index as a separate corroborating source.
3. Add RDH/official 2022 and 2024 geometries and earlier VEST/Census snapshots where licensing and downloads permit.
4. Obtain the Alabama Legislative Reapportionment Office filing index, resolutions, maps, and legal descriptions.
5. Generate a county/date coverage matrix; only then make targeted county records requests for unresolved intervals.
6. Build reviewed precinct versions and lineage before implementing election-date snapshot generation.

Raw files remain immutable and every warehouse record retains source provenance. Binary maps and documents stay outside SQLite; the warehouse stores their metadata, hashes, normalized records, and relationships.
