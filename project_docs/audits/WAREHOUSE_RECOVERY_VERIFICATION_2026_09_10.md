# Warehouse recovery verification — 2026-09-10

Internal execution evidence for the `warehouse-12` recovery-verification component:
verify that the latest verified backup of the central warehouse restores to a
separate path and still matches the live warehouse modulo the documented
2026-09-08 metadata run. Recorded per
[`WAREHOUSE_COMPLETION_REPAIRS_2026_09_08.md`](WAREHOUSE_COMPLETION_REPAIRS_2026_09_08.md)
style. This unit was read-only against `data/`; it did not replace, repair or
rebuild anything, and ran no builder, test suite, formatter or linter.

Files: this audit only. The scratch directory `.validation_tmp/recovery_20260910/`
(explicit write scope) was created, used, and deleted; no companion `.json` is in
scope for this component.

## 1. Preconditions, file identity and sidecars

Checked free space and file identity before copying anything:

```powershell
& .venv/Scripts/python.exe -c "import shutil; u=shutil.disk_usage('.'); print(u.free/1024**3)"
stat -c '%n %s %y' data/processed/elections/backups/pre-shor-registry-metadata-2026-09-08.sqlite `
  data/processed/elections/alabama_elections.sqlite
stat -c '%n %s %y' data/processed/elections/alabama_elections.sqlite-wal `
  data/processed/elections/alabama_elections.sqlite-shm `
  data/processed/elections/backups/pre-shor-registry-metadata-2026-09-08.sqlite-wal `
  data/processed/elections/backups/pre-shor-registry-metadata-2026-09-08.sqlite-shm
```

- Free space **206.108 GiB** — the 8 GB gate passes. The restored copy needs
  ~5.82 GiB in addition to the source pair, so the copy never approached the
  threshold. Free space after cleanup and after a concurrent sibling writer:
  219,065,921,536 bytes (204.02 GiB). The 2.1 GiB reduction is not attributable
  to this unit (its own scratch was deleted).
- Backup `pre-shor-registry-metadata-2026-09-08.sqlite`: size **5,819,052,032**
  bytes (expected 5,819,052,032 → match), mtime
  `2026-09-08 10:35:05.537377100 -0500`.
- Live `alabama_elections.sqlite`: size **5,819,056,128** bytes (expected
  5,819,056,128 → match), mtime `2026-09-08 10:38:30.839534200 -0500`.
- Sidecars: **all four absent** before the work (`-wal` and `-shm` for both the
  backup and the live file). Re-checked after all work: still absent; this unit's
  read-only opens created none. No sidecar was deleted or created.

## 2. Restore to a separate path

A scratch driver `.validation_tmp/recovery_20260910/verify.py` (7,773 bytes,
deleted with the directory) performed the steps below with the `sqlite3` stdlib
only; no pandas and no whole-table reads.

```powershell
& .venv/Scripts/python.exe .validation_tmp/recovery_20260910/verify.py hashbackup
& .venv/Scripts/python.exe .validation_tmp/recovery_20260910/verify.py copy
```

- Backup SHA256 (streamed in 1 MiB blocks): `5ab59f3ad577417ffcdc5e5bbff20564ef1d5acdc33cef770d7c3ddb4fed7087`
  over 5,819,052,032 bytes, 26.939 s. This digest is **identical** to the value
  recorded independently in
  [`SOUTHERN_V3_INPUT_REVISION_2026_09_10.json`](SOUTHERN_V3_INPUT_REVISION_2026_09_10.json)
  (`backup_file_hashes_2026_09_08`).
- Copy to `.validation_tmp/recovery_20260910/restored.sqlite` with
  `shutil.copyfile`: 140.805 s; restored size 5,819,052,032 bytes.
- SHA256 of the restored copy: `5ab59f3ad577417ffcdc5e5bbff20564ef1d5acdc33cef770d7c3ddb4fed7087`
  — **equal to the backup**, asserted and passed. The copy command's total wall
  time was 162.80 s; its internal hash sub-timing was held only in the deleted
  scratch `result.json` and is not reported.

Additional bounded cross-check (beyond the required steps, read-only): the live
file was hashed with the same streaming method, 14.242 s, giving
`77379bb50124ddbba150581c537765f79ffd48e804a596f6243aef8a0c9e4432` over
5,819,056,128 bytes — **identical** to `declared_input.current_sha256` in
`SOUTHERN_V3_INPUT_REVISION_2026_09_10.json`. This pins the live warehouse to the
known post-metadata run state at verification time.

## 3. Integrity checks on the restored copy

Opened read-only (`file:...?mode=ro`, `PRAGMA query_only=ON`); nothing was
modified.

```powershell
& .venv/Scripts/python.exe .validation_tmp/recovery_20260910/verify.py pragmas
```

| Check | Result | Rows | Elapsed |
|---|---|---:|---:|
| `PRAGMA quick_check` | `ok` | 1 | 395.784 s |
| `PRAGMA integrity_check` | `ok` | 1 | 226.027 s |
| `PRAGMA foreign_key_check` | no violations | 0 | 46.128 s |

This completes the backup `quick_check` that
`WAREHOUSE_COMPLETION_REPAIRS_2026_09_08.md` recorded as cancelled and not
counted; it is now performed independently on a separate restore of that exact
file.

## 4. Ledger and schema

```powershell
& .venv/Scripts/python.exe .validation_tmp/recovery_20260910/verify.py ledger
& .venv/Scripts/python.exe .validation_tmp/recovery_20260910/verify.py schema
```

Latest row of `warehouse_build_run` (`ORDER BY rowid DESC LIMIT 1`):

| Field | Restored (backup) | Live |
|---|---|---|
| `build_run_id` | `RUN-91B2A0C3435548A1B6932613B3073995` | `RUN-55E4997B16DA4330BF6E2EE7A1E5FD36` |
| `target` | `sos_legacy_source_cell_lineage` | `shor_manifest_registry_metadata` |
| `started_at_utc` | `2026-09-08T15:22:48.115964+00:00` | `2026-09-08T15:37:24.479919+00:00` |
| `completed_at_utc` | `2026-09-08T15:24:32.777294+00:00` | `2026-09-08T15:37:24.496680+00:00` |
| `status` | `validated` | `validated` |
| `code_commit` | `720c3507b147bc0a7c048c4c84ab0262920802c1` | `720c3507b147bc0a7c048c4c84ab0262920802c1` |
| `warehouse_build_run` rows | 123 | 124 |
| `qa_warehouse_source_repair` rows | 54 | 55 |

Both latest run IDs are exactly the ones expected for this pair: the backup stops
at the legacy-source-locator run and the live file adds the registry metadata run.
The newest QA row in the live file is
`WQA-SHOR-METADATA-RUN-55E4997B16DA4330BF6E2EE7A1E5FD36`, scoped to
`warehouse_source_file`, status `metadata_repaired`; the restored file's newest QA
row is `SOSLEGACYCELL-BC8883A71B89FFC0267F04CE` for
`RUN-91B2A0C3435548A1B6932613B3073995`.

Schema and pragmas:

- `PRAGMA user_version`: `0` in both.
- `PRAGMA schema_version`: restored **1**, live **589**.
- `sqlite_master` content (`type,name,tbl_name,sql`, ordered) is **byte-identical**:
  302 objects in both files, SHA256
  `4d1c1deaa40f19b7845efdc7bd843c81b8f1c87e488094442fa8d30f6d58cdd9` in both.
- The `schema_version` difference is the SQLite schema cookie, not logical schema
  content, and it is explained by the recorded backup mechanism: the parent repair
  created this backup with the SQLite online backup API
  (`scripts/sync_warehouse_source_registry.py`, `reader.backup(destination)`), not
  a byte copy. A local control experiment reproduced the effect — source
  `schema_version` 11, backup-API destination 1, plain byte copy 11. Also the
  project's own `warehouse_schema_version` table is 27 in both files.

## 5. Table-count comparison

```powershell
& .venv/Scripts/python.exe .validation_tmp/recovery_20260910/verify.py counts
```

`SELECT COUNT(*)` was run for every table in `sqlite_master WHERE type='table'` in
both files: **120 tables compared**, 26 stored views excluded (not tables),
18.58 s total. No table exists on only one side. Exactly two tables differ, both
the expected `+1` controls from the 2026-09-08 registry commit:

| table | restored (backup) | live | diff |
|---|---:|---:|---:|
| `qa_warehouse_source_repair` | 54 | 55 | +1 |
| `warehouse_build_run` | 123 | 124 | +1 |

All 118 other tables are identical. Full comparison:

| table | restored (backup) | live | diff |
|---|---:|---:|---:|
| `bridge_alabama_canonical_candidate_certified_result` | 377 | 377 | +0 |
| `bridge_southern_2012_precinct_plan_weight` | 54537 | 54537 | +0 |
| `bridge_southern_block_district_assignment` | 6324382 | 6324382 | +0 |
| `bridge_southern_candidate_result_source` | 20099 | 20099 | +0 |
| `bridge_southern_finance_candidate_identity` | 12556 | 12556 | +0 |
| `bridge_southern_finance_record_source` | 63114 | 63114 | +0 |
| `bridge_southern_result_geography` | 45990 | 45990 | +0 |
| `bridge_southern_vest_historical_plan_weight` | 166562 | 166562 | +0 |
| `bridge_southern_vest_precinct_district_weight` | 96114 | 96114 | +0 |
| `candidate_alias_match_candidates` | 2113 | 2113 | +0 |
| `candidate_aliases` | 2058 | 2058 | +0 |
| `candidate_party_affiliations` | 1564 | 1564 | +0 |
| `candidate_party_switches` | 35 | 35 | +0 |
| `canonical_candidate_finance_match` | 1078 | 1078 | +0 |
| `canonical_candidates` | 1564 | 1564 | +0 |
| `canonical_doj_section5_submission` | 2584 | 2584 | +0 |
| `canonical_geography_evidence` | 7183 | 7183 | +0 |
| `canonical_legislator_person_match` | 198 | 198 | +0 |
| `canonical_precinct_geography_links` | 4336 | 4336 | +0 |
| `canonical_southern_legislative_candidate_election` | 79812 | 79812 | +0 |
| `dim_southern_geography_layer` | 104 | 104 | +0 |
| `dim_southern_geography_unit` | 53510 | 53510 | +0 |
| `geographic_precinct_nodes` | 7917 | 7917 | +0 |
| `geographic_vote_fingerprints` | 27517 | 27517 | +0 |
| `mart_alabama_2026_incumbency_roster` | 140 | 140 | +0 |
| `mart_candidate_resources` | 1564 | 1564 | +0 |
| `mart_cmo_cycle_input_coverage` | 64 | 64 | +0 |
| `mart_historical_candidate_finance_coverage` | 211 | 211 | +0 |
| `mart_historical_candidate_incumbency` | 211 | 211 | +0 |
| `mart_historical_candidate_result` | 411 | 411 | +0 |
| `mart_historical_cmo_context_feature` | 140 | 140 | +0 |
| `mart_historical_cmo_context_feature_v2` | 420 | 420 | +0 |
| `mart_historical_cmo_race_feature` | 139 | 139 | +0 |
| `mart_historical_district_demographic_feature` | 140 | 140 | +0 |
| `mart_historical_district_office_baseline` | 278 | 278 | +0 |
| `mart_historical_district_presidential_feature` | 140 | 140 | +0 |
| `mart_historical_federal_district_baseline` | 1004 | 1004 | +0 |
| `mart_historical_incumbency_evidence` | 207 | 207 | +0 |
| `mart_historical_precinct_district_weight` | 6441 | 6441 | +0 |
| `mart_race_resource_features` | 1055 | 1055 | +0 |
| `mart_southern_2012_precinct_vote_geometry` | 14436 | 14436 | +0 |
| `mart_southern_candidate_cycle_finance` | 12532 | 12532 | +0 |
| `mart_southern_presidential_district_result` | 13800 | 13800 | +0 |
| `mart_southern_race_finance` | 7976 | 7976 | +0 |
| `mart_southern_war_context_feature` | 8085 | 8085 | +0 |
| `mart_southern_war_outcome` | 4582 | 4582 | +0 |
| `precinct_block_links` | 625502 | 625502 | +0 |
| `precinct_change_event` | 434 | 434 | +0 |
| `precinct_change_event_type` | 521 | 521 | +0 |
| `precinct_county_coverage` | 0 | 0 | +0 |
| `precinct_geography_conflicts` | 1036 | 1036 | +0 |
| `precinct_geography_links` | 8228 | 8228 | +0 |
| `precinct_geography_match_candidates` | 41038 | 41038 | +0 |
| `precinct_lineage` | 0 | 0 | +0 |
| `precinct_match_candidates` | 36090 | 36090 | +0 |
| `precinct_nodes` | 45132 | 45132 | +0 |
| `precinct_snapshot` | 4 | 4 | +0 |
| `precinct_source_links` | 10297 | 10297 | +0 |
| `precinct_version` | 0 | 0 | +0 |
| `precinct_vote_fingerprints` | 1076275 | 1076275 | +0 |
| `precinct_vtd_link_evidence` | 6488 | 6488 | +0 |
| `precinct_vtd_links` | 8522 | 8522 | +0 |
| `qa_historical_baseline_allocation` | 8 | 8 | +0 |
| `qa_southern_2012_plan_allocation` | 14 | 14 | +0 |
| `qa_southern_context_ingest` | 99 | 99 | +0 |
| `qa_southern_election_coverage` | 135 | 135 | +0 |
| `qa_southern_election_reconciliation` | 1196 | 1196 | +0 |
| `qa_southern_finance_coverage` | 60 | 60 | +0 |
| `qa_southern_historical_plan_allocation` | 67 | 67 | +0 |
| `qa_southern_legislative_source_reconciliation` | 52 | 52 | +0 |
| `qa_southern_presidential_district_allocation` | 167 | 167 | +0 |
| `qa_southern_presidential_district_readiness` | 174 | 174 | +0 |
| `qa_southern_presidential_precinct_match` | 1867 | 1867 | +0 |
| `qa_southern_presidential_result_correction` | 1 | 1 | +0 |
| `qa_southern_spatial_plan_geometry_overlay` | 6 | 6 | +0 |
| `qa_southern_vest_context_ingest` | 14 | 14 | +0 |
| `qa_southern_vest_precinct_plan_allocation` | 28 | 28 | +0 |
| `qa_warehouse_source_repair` | 54 | 55 | **+1** |
| `snapshot_precinct` | 0 | 0 | +0 |
| `source_availability` | 934 | 934 | +0 |
| `source_dime_recipient` | 2554 | 2554 | +0 |
| `source_doj_section5_entry` | 58773 | 58773 | +0 |
| `source_doj_section5_notice` | 763 | 763 | +0 |
| `source_historical_legislative_county_result` | 671 | 671 | +0 |
| `source_historical_presidential_precinct` | 2105 | 2105 | +0 |
| `source_historical_statewide_county_result` | 737 | 737 | +0 |
| `source_legiscan_amendment` | 5912 | 5912 | +0 |
| `source_legiscan_bill` | 28833 | 28833 | +0 |
| `source_legiscan_bill_document` | 39853 | 39853 | +0 |
| `source_legiscan_bill_history` | 205574 | 205574 | +0 |
| `source_legiscan_bill_sponsor` | 102291 | 102291 | +0 |
| `source_legiscan_bill_subject` | 28265 | 28265 | +0 |
| `source_legiscan_legislator_session` | 2429 | 2429 | +0 |
| `source_legiscan_member_vote` | 2225079 | 2225079 | +0 |
| `source_legiscan_person` | 327 | 327 | +0 |
| `source_legiscan_roll_call` | 31257 | 31257 | +0 |
| `source_legiscan_session` | 31 | 31 | +0 |
| `source_manifest` | 19 | 19 | +0 |
| `source_southern_assignment_file` | 49 | 49 | +0 |
| `source_southern_candidate_cycle_finance` | 12559 | 12559 | +0 |
| `source_southern_candidate_election` | 15834 | 15834 | +0 |
| `source_southern_census_block_file` | 14 | 14 | +0 |
| `source_southern_context_file` | 99 | 99 | +0 |
| `source_southern_election_file` | 4013 | 4013 | +0 |
| `source_southern_finance_file` | 20089 | 20089 | +0 |
| `source_southern_incumbency_evidence` | 9536 | 9536 | +0 |
| `source_southern_legislative_candidate_result` | 83064 | 83064 | +0 |
| `source_southern_legislative_observation_set` | 52511 | 52511 | +0 |
| `source_southern_precinct_geometry_file` | 5 | 5 | +0 |
| `source_southern_presidential_geography_result` | 3270010 | 3270010 | +0 |
| `source_southern_spatial_plan_assignment` | 47 | 47 | +0 |
| `source_southern_vest_context_file` | 14 | 14 | +0 |
| `vote_observations` | 2184861 | 2184861 | +0 |
| `warehouse_asset` | 103 | 103 | +0 |
| `warehouse_asset_lineage` | 99 | 99 | +0 |
| `warehouse_build_run` | 123 | 124 | **+1** |
| `warehouse_manual_adjudication` | 0 | 0 | +0 |
| `warehouse_schema_version` | 27 | 27 | +0 |
| `warehouse_source_file` | 26694 | 26694 | +0 |
| `warehouse_table_registry` | 99 | 99 | +0 |

The observed `+1`/`+1` pattern matches the expectation recorded in
`WAREHOUSE_COMPLETION_REPAIRS_2026_09_08.md` ("schema and all 120 table counts
remain unchanged except builds 123 to 124 and QA 54 to 55"). No unexpected count
difference was found.

## 6. Changed registry row

```powershell
& .venv/Scripts/python.exe .validation_tmp/recovery_20260910/verify.py registry
# SELECT * FROM warehouse_source_file WHERE source_file_id='SRC-3F0ED360408C5AD273F6'
```

Exactly one row with `source_file_id = SRC-3F0ED360408C5AD273F6` exists in both
files. Comparing the physical columns of `warehouse_source_file`, **only two
columns differ**: `original_url` and `license`. (The task's `access_url` is the
manifest field name; `scripts/sync_warehouse_source_registry.py` maps it into the
physical `original_url` column.)

| column | restored (backup) | live |
|---|---|---|
| `source_file_id` | `SRC-3F0ED360408C5AD273F6` | `SRC-3F0ED360408C5AD273F6` |
| `provider` | `shor_mccarty` | `shor_mccarty` |
| `local_path` | `data/raw/ideology/shor_mccarty_individual_legislators_1993_2018.tsv` | same |
| `original_url` (**differs**) | `NULL` | `https://dataverse.harvard.edu/api/access/datafile/:persistentId/?persistentId=doi:10.7910/DVN/GZJOT3/6PK3W0` |
| `retrieved_at_utc` | `2026-08-16T19:08:41.204997+00:00` | `2026-08-16T19:08:41.204997+00:00` |
| `sha256` | `62e96b1d74d65b2d467bd4e24fc09ddd2dbf47fdfdab744389c4132b943ff351` | same |
| `media_type` | `NULL` | `NULL` |
| `license` (**differs**) | `NULL` | `CC0 1.0` |
| `extraction_status` | `normalized` | `normalized` |
| `authoritative_scope` | `incumbency_validation_context` | `incumbency_validation_context` |

`diff_columns = ['original_url', 'license']` — the observed change set is exactly
the two literal metadata fills the 2026-09-08 registry run was authorized to make.
Retrieval time, artifact hash, provider, path, extraction status and scope are
unchanged. No other difference was found to report as a finding.

## 7. Cleanup and non-mutation assertions

```powershell
& .venv/Scripts/python.exe .validation_tmp/recovery_20260910/verify.py stat_after
stat -c '%n %s %y' data/processed/elections/backups/pre-shor-registry-metadata-2026-09-08.sqlite `
  data/processed/elections/alabama_elections.sqlite
```

- Scratch `restored.sqlite` (5,819,052,032 bytes), `result.json` (15,744 bytes)
  and `verify.py` (7,773 bytes) deleted with the directory:
  **5,819,075,549 bytes freed** (free-space delta measured
  +5,819,076,608 bytes; the 1,059-byte difference is filesystem allocation
  granularity). `.validation_tmp/recovery_20260910/` confirmed absent;
  `.validation_tmp/` itself was left in place with its pre-existing sibling
  content untouched.
- Backup and live file: size and mtime compared numerically before and after all
  work — **both unchanged** (asserted, passed; the re-run `stat` matches
  section 1 exactly).
- No `-wal`/`-shm` sidecar exists for either file after the work.
- The live warehouse was only ever opened with `file:...?mode=ro` plus
  `PRAGMA query_only=ON`; the restored copy was opened the same way even though it
  was scratch. No `data/` file was written, and no builder, allocation replay,
  geometry replay or publication command ran.

## What this establishes

- The verified backup `pre-shor-registry-metadata-2026-09-08.sqlite` restores to a
  separate path as a byte-identical file (SHA256 match, streamed), and the digest
  agrees with the independently recorded value in
  `SOUTHERN_V3_INPUT_REVISION_2026_09_10.json`.
- The restored copy passes `PRAGMA quick_check` (`ok`, 395.784 s),
  `PRAGMA integrity_check` (`ok`, 226.027 s) and `PRAGMA foreign_key_check`
  (0 violations, 46.128 s). This supplies the independent backup `quick_check`
  that the 2026-09-08 unit recorded as cancelled.
- Logical schema is identical between backup and live (302 `sqlite_master` objects,
  identical content hash); all 120 table row counts are identical except the two
  documented `+1` control rows; the one changed registry row differs only in
  `original_url` (manifest `access_url`) and `license`.
- Live warehouse bytes match the recorded `current_sha256`
  `77379bb50124ddbba150581c537765f79ffd48e804a596f6243aef8a0c9e4432` for the
  post-metadata run state.
- The live warehouse and the backup were not modified by this work.

## What this does NOT establish

- **Not row-level content equality.** Counts and one registry row were compared;
  no per-table digest (other than the registry row's own columns) was computed, so
  in-place edits that preserved row counts in other tables would not be detected.
  The recorded full source digest
  `8abac3c2fe94a1fb840993481fe1916bee6fa018177f081363cdcfb63ca33513` was **not**
  recomputed here.
- **No allocation, geometry or model replay.** Restoring bytes and matching counts
  does not verify historical vote allocations, precinct/plan geometry,
  backcasts, WAR/forecast outputs or any downstream product.
- **Not a release or publication approval, and not certification of downstream
  freshness.** Whole-database byte-hash consumers still require their own
  freshness review after the 2026-09-08 metadata runs.
- **Not a backup-schedule or byte-lineage proof.** Only this one backup file was
  exercised. The mismatch between the manifest's declared pre-run digest
  `8cb49945…` and any surviving backup remains open and is unaffected here; that
  limitation is recorded in `SOUTHERN_V3_INPUT_REVISION_2026_09_10.json`.
- **Not an explanation of every header field.** The backup's SQLite schema cookie
  reads 1 versus live's 589; the online-backup-API mechanism used to create it
  (reproduced in a control experiment) accounts for this, but this unit did not
  reconstruct the original 2026-09-08 command line from an independent log.
- The scratch driver `verify.py` was deleted per the write scope, so the run is
  reproducible only from the commands and queries recorded above, not from a
  retained script hash.
