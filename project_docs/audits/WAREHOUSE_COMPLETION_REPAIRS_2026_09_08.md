# Warehouse completion repairs — 2026-09-08

Internal execution evidence for the Phase 2 request. Overall warehouse completion
is **not established**. The resumed unit changes only reviewed source provenance
metadata, as recorded below. No source values, analytical results or public
files have been rewritten by this work. Existing WIP is preserved.
The execution record is
[CHECKLIST-EXECUTION-20260906.md](../coordination/CHECKLIST-EXECUTION-20260906.md).

## Current database evidence

Read-only SQLite connection used the resolved file URI with `mode=ro`,
`PRAGMA query_only=ON` and one read transaction. Latest live build:
`RUN-92AB8DE353AC47D6AECE3D7767C29FCD`, target
`southern_war_preparation_no_finance`, status `validated`.

Executed `PRAGMA integrity_check` and the existing
`repair_warehouse_source_defects.validate(connection)` on that snapshot:

- Full integrity check: `ok`; quick check: `ok`.
- Foreign-key violations: 0; every stored view prepares successfully.
- Repaired-pattern failures: 0; incomplete finance rows retaining numeric
  features: 0; invalid stored geometry rows: 0.
- Remaining source QA: 5,354 natural-key collision groups, 15,035 excess rows
  at the proposed grain; one fractional-source observation.
- Combined elapsed time: 202.61 seconds. No allocation, model, publication,
  source refresh or database mutation ran.

These checks verify storage and the recorded repair patterns. They do not
establish the correct source grain, historical allocations or downstream freshness.

## Accepted code: literal source-count guards

Five previously unguarded SQL boundaries now call the existing
`require_reported_vote_quality` helper before pandas reads or aggregation:

- `build_candidate_identity.main`.
- `build_canonical_geographic_weights.main`.
- `build_presidential_district_features.load_legislative_activity_weights`.
- `build_1998_2006_context_features.legislative_weights` and `_pres2004`.

Each predicate matches its existing consumed source/cycle/office/district/party
slice. Missing, fractional, negative, nonnumeric and nonfinite reported counts
fail with source evidence. Observed zero passes; defects outside the consumed
slice do not block it. Existing calculations, identities and query results are
unchanged for eligible input. Fixtures stop at pandas, before analytical work.

Implementer verification:

```powershell
& .venv/Scripts/python.exe -m pytest --testmon --testmon-noselect scripts/tests/test_warehouse_consumer_source_guards.py -q
& .venv/Scripts/python.exe -m pytest --testmon scripts/tests/test_warehouse_consumer_source_guards.py scripts/tests/test_source_vote_quality.py -q
& .venv/Scripts/python.exe -m pytest scripts/tests/test_warehouse_consumer_source_guards.py scripts/tests/test_source_vote_quality.py -q
```

Initial regression: 32 failed, 23 passed. After the guard additions: 55 new
tests passed. Testmon-selected combined run: 55 passed, 18 deselected. Explicit
combined run: 73 passed in 3.22 seconds. Independent read-only review by
`/root/collision_review` found no scoped defects; the reviewer did not rerun tests.
Prior identity/presidential changes visible in the full Git diff are unrelated
WIP, not changes attributed to this unit.

## Accepted code: declared dependency integrity at the existing release gate

`southern_war_release_gate.require_approved_release` previously checked the
approval, manifest and review record without checking the manifest's declared
files. An unchanged approval could therefore accept replaced or missing inputs,
code, outputs or reports.

The gate now verifies every declared file in `input_hashes`, `code_hashes`,
`outputs` and `reports` after the existing approval checks. It rejects missing
or changed bytes and malformed/outside-repository declarations. Hashing streams
bounded blocks, including for the central SQLite file. No numerical calculation,
model selection, approval alteration or output regeneration is performed.

```powershell
& .venv/Scripts/python.exe -m pytest --testmon --testmon-noselect scripts/tests/test_southern_war_release_gate.py -k approval_cannot_hide -q
& .venv/Scripts/python.exe -m pytest --testmon --testmon-noselect scripts/tests/test_southern_war_release_gate.py -q
```

Before repair: all 8 new changed/missing-file regressions failed (5 unrelated
tests deselected). After repair: 13 tests passed in 6.05 seconds, including the
read-only check of the existing approved bundle. Independent read-only code
review found no scoped defects. This is file-integrity acceptance, not renewed
scientific acceptance. Undeclared transitive dependencies and other product
publication routes remain outside this guard's coverage; `warehouse-11` stays open.

## Source-grain and lineage findings

### Accepted parser metadata and verification

The 1998/2004 adapters and candidate-header fallback now retain sheet,
one-based row/column, and literal printed labels without changing previous
substantive fields, filtering, order or counts. Independent code review by
`/root/collision_review` found no scoped defects; no raw replay was independently
rerun by that reviewer.

Executed by the implementer:

```powershell
& .venv/Scripts/python.exe -m pytest scripts/tests/test_sos_legacy_source_locators.py -q --tb=line
& .venv/Scripts/python.exe -m pytest scripts/tests/test_sos_legacy_source_locators.py scripts/tests/test_sos_precinct.py -q --testmon --tb=short
& .venv/Scripts/python.exe -m pytest scripts/tests/test_sos_legacy_source_locators.py scripts/tests/test_sos_precinct.py -q --tb=short
```

Initial regression: 5 failed. Selected run after repair: 7 passed, 7 deselected.
Explicit run: 14 passed in 0.60 seconds. Six workbook parses retained identical
before/after substantive-record hashes:

| Year/member (under its existing source archive) | Rows | Substantive SHA256 |
|---|---:|---|
| 1998 `98g-prec/AUTAUGA.XLS` | 1342 | `f20b9452e446b3f14220ce316db1576cc83b9966254f8f467a7dd461cb0fe252` |
| 1998 `98g-prec/BALDWIN.XLS` | 3570 | `8865887b681e52ff83eb82f3ef9b48d29beeb302b5f322a2ee56c91ad588d0b7` |
| 1998 `98g-prec/BARBOUR.XLS` | 2280 | `9289c5f40a3ddc01b59d3d8b0230516c80c6fd6b68df98b616cdd158b8abb9d6` |
| 2004 `2004-GeneralElection-PrecinctLevel/Autauga - GEN04.xls` | 1202 | `486b78e24de6578d607b2951f0d85f526999aced72792843b42fcc81de59fda2` |
| 2004 `2004-GeneralElection-PrecinctLevel/Baldwin - GEN04.xls` | 3224 | `480572bc55875e469f354d72383eae16ccb2d5f59fc0ab8438d7d55e47f4c08c` |
| 2004 `2004-GeneralElection-PrecinctLevel/Barbour - GEN04.xls` | 1850 | `316c852ae26259c5f93b3eb45bf1a3f27643a4760e25ab5f086ac612bd23a50b` |

Digest procedure: call `normalize_workbook` on each archive member using
`_county_from_filename`; select existing columns in order
`county,precinct,office,district,party,candidate,votes,party_method,year,party_norm,county_key,precinct_key`;
hash UTF-8 `frame.to_json(orient='split')`. All five new metadata columns were
nonnull on these bounded examples. These are parsed-record hashes, not raw-file
hashes. The direct normalization harness did not register sources or assign the
archive member field; the unchanged normal ZIP loader owns `source_file`.

Historical repair commands pin their original parser hashes and may now refuse
replay on the newer code, as designed. Do not rewrite those accepted audit pins
or claim that these metadata changes revalidate historical applications.

### Live findings

The independent helper used query-only connections and did not write artifacts.
The collision census groups `vote_observations` by
`source,year,county_key,precinct_key,office,district,candidate_key`, keeps
`COUNT(*) > 1`, then sums `COUNT(*)-1`. Current counts:

| Year | Collision groups | Excess rows at proposed grain |
|---|---:|---:|
| 1994 | 83 | 83 |
| 1998 | 922 | 1,666 |
| 2004 | 3,661 | 12,509 |
| 2006 | 281 | 311 |
| 2008 | 326 | 385 |
| 2010 | 27 | 27 |
| 2012 | 54 | 54 |

The 1994 groups retain physical locators: reused provider identifiers identify
distinct printed rows (Covington 121 and Jackson 37030). The 2004 blank-office
subset contains 1,820 groups/7,384 excess rows; nonblank offices account for
1,841/5,125. The immutable archive member `Barbour - GEN04.xls` contains six
named contest-family sheets. Distinct measurement categories and omitted title
meaning explain why the proposed normalized key is insufficient; they are not
evidence that observations may be deleted. Washington accounts for 253 of the
281 groups in 2006; its workbook has two-row office headings and separate
precinct/box fields. Preserve those distinctions in any later source review.

Six 2010/2012 rows still have equally plausible physical alternatives:
Geneva rowids `1007810,1007811`; Morgan
`1183727,1183812,1183725,1183810`. QA issue
`SOSCELL-3171F6960B9DE8E7B24000D4` preserves the alternatives. Do not invent
scalar lineage by assigning row order. See
[the accepted source-cell repair](SOS_CELL_LINEAGE_REPAIR_2026_09_07.json).

The checklist's old statement that 97 current outcome rows lack scalar source
IDs is superseded by the
[certified integration](ALABAMA_CERTIFIED_CANONICAL_REPAIR_2026_09_08.md):
all 4,582 current outcome rows have a source ID, and the certified bridge has
377 rows. Historical transformation lineage is still incomplete: 1,564 regional
canonical rows retain the compatibility token `legacy-alabama-canonical` and
null direct source IDs. The newer bridge does not recreate their original ingest.

The registry has 26,694 files, including 33 missing URLs, 9 unknown retrieval
dates, 2,154 missing terms and 1,351 missing authoritative scopes. The nine dates
are DIME plus eight Census registrations already reviewed as unknown. Do not
replace them with registration times. Thirteen old `running` records have later
validated runs for the same targets; that does not prove the predecessors'
terminal state or actual completion time.

## Remaining acceptance boundaries

- `warehouse-04`: affected allocations/baselines require source-grain and
  correct-plan reconciliation. No accepted replacement was produced here.
- `warehouse-05`: collisions require provider-grain evidence; individual
  ambiguity remains explicit. No deduplication is authorized by the census.
- `warehouse-06`: literal-count refusal is improved, but full downstream
  quarantine of the Morgan conflict and cached artifacts is not established.
- `warehouse-08/09`: current scalar outcome linkage is repaired; historical
  ingest evidence, source terms/scope and the broader local-source inventory
  still require reconciliation. Unknowns are retained.
- `warehouse-10/11`: the accepted safeguards cover named boundaries only;
  complete shared joins and all publication consumers are not yet certified.
- `warehouse-12`: storage/source-pattern checks pass; complete geometry/allocation
  replay, recovery verification and downstream acceptance remain open.
- `warehouse-13`: the existing catalog still needs complete source-to-consumer
  reconciliation. No competing catalog has been created.

No remaining Phase 2 task is marked complete merely because one safeguard passed.

## Final verification and checkpoint

Primary consolidated verification:

```powershell
& .venv/Scripts/python.exe -m pytest --testmon --testmon-noselect scripts/tests/test_warehouse.py scripts/tests/test_warehouse_data_repairs.py scripts/tests/test_raw_vote_consumer_gates.py scripts/tests/test_source_vote_quality.py scripts/tests/test_warehouse_consumer_source_guards.py scripts/tests/test_southern_war_release_gate.py -q
```

Result: **109 passed**, no deselections, in 21.73 seconds. One existing pandas
FutureWarning from concatenation in `sos_precinct.load_sos_year`; no failed checks.
The separate parser run above adds 14 passing tests. No full repository suite
or analytical rebuild was run.

The existing `scripts/tests/internal_checklist_browser_checks.js` passed in
nonpersistent, headless Edge contexts at 1258×900 and 390×844 using the installed
Playwright 1.63.0-alpha-2026-08-31 runtime. It checked scope/IDs, toggling,
persistence, counters/history, filters, escaped portable export and overflow;
restored test edits and closed both contexts/browser. Checklist revision
`2026-09-08T14:47:16Z` retains 23/82 completed items and all previous history.

Current repository HEAD inspected: `720c3507b147bc0a7c048c4c84ab0262920802c1`.
No commit, publication, live database write or backup replacement occurred.
Next safe source task: stage full-cohort 1998/2004 locator comparisons against
registered raw hashes and the current source table before proposing any fills.
Only unique, substantive-field-identical pairs qualify; unresolved alternatives
must retain their evidence. That staging and any reviewed transactional load
remain outstanding, as do the acceptance boundaries above.

## Resumed source metadata repair

Complete raw replays established that legacy office spellings prevented exact
cohort matching. The separately reviewed
`LEGACY_SOURCE_OFFICE_EQUIVALENCE_2026_09_08.json` authorizes comparison-only
spelling equivalences, never source-label changes. Of 134 county cohorts, 87
fully reconcile (232434 records); 47 retain substantive mismatches (91404
records) and receive no updates. Within reconciled cohorts, 3552 ambiguous rows
retain all 1322 alternative groups; 228882 unique rows qualify for five physical
provenance fields only. Original ingest IDs and every substantive value remain
outside the write scope.

The first exact reviewed proposal (SHA256
`171d2853604e6c8dddad336b8218e1b68c14364784931e2599f4f610d9d3e026`)
failed final expected-after digest validation and rolled back. Pandas emitted
integral coordinates as JSON floats; SQLite INTEGER affinity stores them as
integers, which are distinct under exact JSON hashing. The regression failed
before correction (1 failed, 25 deselected). Staging now emits integer physical
coordinates; the combined staging/application/parser checks pass: 71 tests in
4.20s, no deselections. No preservation check was weakened.

Independent rollback verification matched full source rows against
`data/processed/elections/backups/pre-legacy-source-locators-2026-09-08.sqlite`:
SHA256 `4445e6f9137a9bebc4d2fee74f7089edbe9604d393a3851109b6be8fda822feb`.
Schema, all 122 build rows, 26694 registrations and 53 QA rows also match;
latest run remains the pre-application run. Preserve the backup and failed
proposal. Corrected raw-stage output is
`artifacts/warehouse/legacy_source_lineage_20260908/reviewed-integer-proposal.json`,
SHA256 `1ff5f7d6d9de09b51588670c97bd7491eda411ee4849435534720ef0ded35ee1`.
Fresh exact review and application acceptance are recorded below when completed.

Corrected proposal independently approved and committed as
`RUN-91B2A0C3435548A1B6932613B3073995`, QA
`SOSLEGACYCELL-BC8883A71B89FFC0267F04CE`. New verified backup:
`data/processed/elections/backups/pre-legacy-source-locators-integer-2026-09-08.sqlite`.
All 228882 proposed fills committed. Full source-table expected-after SHA256
`8abac3c2fe94a1fb840993481fe1916bee6fa018177f081363cdcfb63ca33513`
matched across 2184861 rows. Original source fields, ambiguous/refused rows,
registry and prior controls were preserved by transaction checks. Independent
post-commit verification passed: all 2184861 source rows equal backup plus the
228882 exact proposed fills, with zero discrepancies; schema and all 120 table
counts are preserved except one expected build and QA record. Prior registry
and controls remain intact. Full `PRAGMA integrity_check` returned `ok` and
`PRAGMA foreign_key_check` returned no violations. Whole-database byte-hash consumers now
require freshness review; this metadata repair does not certify those outputs.

An independent bounded registry investigation also found exact path/hash-backed
URL and license evidence for registration `SRC-3F0ED360408C5AD273F6` in
`data/raw/ideology/shor_mccarty_manifest.json` (SHA256
`06c0823666aa21e4a19bc629e4994694c22933a96e678dcfa5103e509adb7665`).
The source artifact hash is
`62e96b1d74d65b2d467bd4e24fc09ddd2dbf47fdfdab744389c4132b943ff351`.
The new guarded registry route dry run proposes only literal `access_url` and
`license` fills; retrieval time, scope and source contents remain unchanged.
Other inspected manifests do not establish missing terms/scope. This bounded
finding is not an exhaustive claim that other evidence cannot be recovered.

Registry recovery committed as `RUN-55E4997B16DA4330BF6E2EE7A1E5FD36`, with
QA `WQA-SHOR-METADATA-RUN-55E4997B16DA4330BF6E2EE7A1E5FD36` and separate
verified backup `data/processed/elections/backups/pre-shor-registry-metadata-2026-09-08.sqlite`.
Only the registered artifact's missing URL and license changed. Manifest and
artifact hashes, all-column registry comparison, prior controls, schema and
foreign keys passed transactional checks. Independent postcheck confirms exactly
one registry row changed in only the two intended fields; schema and all 120
table counts remain unchanged except builds 123 to 124 and QA 54 to 55. All
prior control rows remain intact. Full source digest remains
`8abac3c2fe94a1fb840993481fe1916bee6fa018177f081363cdcfb63ca33513`.
The application successfully verified backup `quick_check` before commit;
independent duplicate backup checking is not needed for this acceptance.
That redundant independent backup `quick_check` was cancelled and did not
complete; it is not counted as a passed check. Independent comparisons above
completed successfully and the application backup check passed before commit.
New/existing registry tests: 38 passed in the parent run (15.93s), no
deselections. The prior 71-test source-lineage run plus these 38 tests covers
109 focused cases for this resumed unit; no full repository suite ran.

The existing internal checklist browser assertions passed in headless Edge at
1258x900 and 390x844 using the inspected installed Playwright runtime. Test edits
were restored and contexts/browser closed. Workflow validation and scoped
whitespace checks passed; Git emitted line-ending conversion warnings only.
No public files were produced, no commit or push performed, and no analytical
consumers were revalidated. All remaining Phase 2 acceptance boundaries above
remain open; source-metadata acceptance is not whole-warehouse completion.

Final checklist revision: `2026-09-08T15:39:47Z`, 23/82 complete. Desktop/mobile
browser checks were repeated successfully after that final revision. No live
writer or partial transaction remains. Latest warehouse run is
`RUN-55E4997B16DA4330BF6E2EE7A1E5FD36`. Retain all three newly created backups,
including the first attempt's verified pre-repair backup; none was overwritten.
