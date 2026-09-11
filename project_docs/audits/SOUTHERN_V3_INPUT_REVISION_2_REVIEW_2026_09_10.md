# Southern v3 second accepted input revision — independent review (2026-09-10)

Independent, read-only review of the second byte state proposed for acceptance under the
`accepted_input_revisions` mechanism of the approved Southern v3 release decision:
`data/processed/elections/alabama_elections.sqlite` moving from the first accepted digest
`77379bb5…` to `e2dbdb9d…`. The reviewer (`InputRevision2Review`) did not perform the warehouse
writes, the evidence record, or the scratch replay, and did not re-review the gate code (accepted
in `SOUTHERN_V3_INPUT_REVISION_REVIEW_2026_09_10.md`, PASS). Procedure:
`project_docs/coordination/AGENT_WORKFLOW.md` section 5. This file is the review record that the
amended decision entry binds by SHA256; it must not be edited after the decision is amended.

## Scope and snapshot

- Repository HEAD: `720c3507b147bc0a7c048c4c84ab0262920802c1` (`git rev-parse HEAD`). Working tree carries
  uncommitted changes (22 modified, 1 untracked in the scoped status below); relevant to this review:
  `M project_docs/audits/SOUTHERN_V3_RELEASE_DECISION.json` (the first-revision amendment, +22/-1),
  `M scripts/southern_war_release_gate.py`, `M scripts/build_1994_cmo_baseline.py`,
  `M scripts/build_historical_federal_baselines.py`, `?? scripts/repair_morgan_1994_fractional_cell.py`,
  `?? project_docs/audits/SOUTHERN_V3_INPUT_REVISION_REVIEW_2026_09_10.md`.
- Approved run of record: `WAR-POST2016-V3-4AF79A70EAA8F39EBD49`, decision
  `project_docs/audits/SOUTHERN_V3_RELEASE_DECISION.json` (`approved_for_descriptive_historical_use`,
  warehouse build run `RUN-92AB8DE353AC47D6AECE3D7767C29FCD`).
- Files hashed by the reviewer (`sha256sum`, streamed):
  - `data/processed/elections/alabama_elections.sqlite` — `e2dbdb9d414041bf61eec83bca8e3c9439eae35b03822dddec9ac3f41bfe72bd`,
    5,819,064,320 bytes, mtime 2026-09-10 23:44:47 local (+8,192 bytes = 2 pages over the rev-1 state).
  - `data/processed/war/post2016_southern_war_v3/manifest.json` — `c6c09e19335965380e068c40484437bf460db81add232dc8d7cf78d135a905a6` (= `manifest_sha256`).
  - `project_docs/audits/SOUTHERN_V3_INDEPENDENT_REVIEW_2026_09_08.md` — `cd0847259e84592e528d5b1d9784e6db77b1caf52fe5ace8e708bf4f0c0ff9d0` (= `review_record_sha256`).
  - `project_docs/audits/SOUTHERN_V3_INPUT_REVISION_REVIEW_2026_09_10.md` — `451ffaf512975ed1e42e63ff599da13b54c2984c675f802162dedcaf5449ef54` (= rev-1 entry `review_record_sha256` and evidence `independent_review.sha256`).
  - `project_docs/audits/SOUTHERN_V3_RELEASE_DECISION.json` — `23cbd19e9f9730e80aaa05821907f028da9df1b550812dc0170dc1e5156c9d91` (one `accepted_input_revisions` entry; not yet amended for this revision).
  - `project_docs/audits/SOUTHERN_V3_INPUT_REVISION_2026_09_10.json` — `259a80c1249a5277196e7f5b9c71f7a334f7bcf4d8c4ded2b303ac0bc69f6d73` (contains `second_revision`).
  - `project_docs/audits/MORGAN_1994_ADJUDICATION_REVIEW_2026_09_10.md` — `ca72ea878281a2e2c9d9d626666d5fdcb43537c1836aa91ae648914f934b1b6f` (line 183: `Verdict: PASS`).
  - `artifacts/war/alabama_dependency_rebuild_20260910/v3_scratch_replay.py` — `d1a7fbf2d5356b5bf4287d75c906ceac60f874040e8985060da79974d81addb2` (rev-1 review hashed `69a2ab47…`; the difference is the disclosed `streaming_sha256` monkeypatch).
  - `scripts/southern_war_release_gate.py` — `a3a64616f0993972d736b8cee0e9fb2bc315689cdbb26e99e9cf834da8af8204`.
  - `data/processed/elections/backups/pre-morgan-1994-adjudication-2026-09-10.sqlite` — 5,819,056,128 bytes (= rev-1 live size), 1,420,668 pages (= rev-1 live page count), 124 ledger rows, latest `RUN-55E4997B…`; used below as the rev-1 logical anchor.
  - `data/processed/elections/backups/pre-1994-federal-mart-rebuild-2026-09-10.sqlite` — 5,819,064,320 bytes (present; not opened).
- Writes by the reviewer: this file, plus the permitted scratch replay re-run in check 4 (writes only under
  `artifacts/war/alabama_dependency_rebuild_20260910/v3_scratch/`). The warehouse and the backup were opened only via
  `sqlite3.connect('file:...?mode=ro', uri=True)` with `PRAGMA query_only=ON`, stdlib `sqlite3`, bounded SQL, one process at a
  time; every digest was streamed (1 MiB blocks or row-by-row). No pandas loads of warehouse tables.

## Check 1 — live digest

`sha256sum data/processed/elections/alabama_elections.sqlite` -> `e2dbdb9d414041bf61eec83bca8e3c9439eae35b03822dddec9ac3f41bfe72bd`,
`stat` size 5,819,064,320. Equals `second_revision.declared_input.to_sha256` in the evidence JSON. Three independent
implementations agree on this digest: `sha256sum`; the driver's `streaming_sha256` (fresh scratch manifest
`input_hashes[sqlite]` in check 4); and the gate's 1 MiB-block `sha256()` (check 5 probe passes only when the
accepted digest is exactly this value). SQLite header read directly: change counter 914, schema cookie 591,
1,420,670 pages (rev-1 live: 904 / 589 / 1,420,668).

Result: match.

## Check 2 — warehouse build ledger and change footprint (read-only)

Query: `SELECT build_run_id,target,started_at_utc,completed_at_utc,status,code_commit FROM warehouse_build_run
WHERE started_at_utc > '2026-09-08T15:37:24' ORDER BY started_at_utc` (127 rows total, previously 124; `MAX(started_at_utc)`
= `2026-09-11T04:44:47.716478+00:00`). Four rows match the string cutoff because the rev-1 boundary run itself carries
fractional seconds; the three strictly new rows are exactly the expected ones, all `validated`, all `code_commit` `720c3507…`:

| build_run_id | target | started_at_utc | completed_at_utc | status |
|---|---|---|---|---|
| RUN-55E4997B16DA4330BF6E2EE7A1E5FD36 | shor_manifest_registry_metadata (rev-1 boundary) | 2026-09-08T15:37:24.479919Z | 15:37:24.496680Z | validated |
| RUN-C0A15A7AB6A6403991BB5FE5143BACFF | morgan_1994_fractional_cell_adjudication | 2026-09-11T04:35:09.965158Z | 04:36:30.671252Z | validated |
| RUN-22C8E3AE51C34579A6BCD9A49EF8C700 | historical_1994_cmo_baseline | 2026-09-11T04:42:54.045707Z | 04:42:54.189592Z | validated |
| RUN-70A750C82BEC43D686E5F4B1FE13461C | historical_federal_district_baseline | 2026-09-11T04:44:47.716478Z | 04:44:47.756843Z | validated |

`configuration_json` / `validation_json` read from the ledger:

- `RUN-C0A15A7A…`: `expected_run` `RUN-55E4997B…`; `cell` = 1994 / alabama_sos / MORGAN / precinct 26001 / Attorney General /
  SESSIONS (R) / `94g-prec/MORGAN.XLS` Morgan!R48C11 / `SRC-E64FFC4299ED54CB2D3A`; `before_image.rowid` 2424457 `votes` 144.4,
  `after_image.rowid` 2424457 `votes` 144.0, all other columns identical; `adjudication_id` `ADJ-1994-MORGAN-26001-AG2-K48`;
  `remaining_fractional_observations` 0; `observations_digest_excluding_cell` `240f226f…`; `before_counts` (`vote_observations`
  2,184,861, `warehouse_build_run` 124, `warehouse_manual_adjudication` 0, `qa_warehouse_source_repair` 55); `before_controls`
  digests for `canonical_candidates` `95078def…`, `warehouse_source_file` `b00d8991…`, `warehouse_table_registry` `d3a55e8a…`,
  `warehouse_schema_version` `898094d7…`; `application_code_sha256` for `repair_morgan_1994_fractional_cell.py` `0a844d3c…`,
  `source_vote_quality.py` `9a3b4755…`, `warehouse.py` `dd9df42b…` (all three equal the current files' `sha256sum`);
  `not_rebuilt` lists the 1994 marts, CMO CSVs, `alabama_historical_war_v1`, pages and forecast.
- `RUN-22C8E3AE…`: config `{cycle: 1994, split_precinct_policy: legislative_activity_split_provisional}`; validation
  `weight_rows` 7384, `race_rows` 139, `contested_two_party_races` 72, `unmatched_precinct_party_rows` 256, `minimum_allocation_coverage` 0.99813.
- `RUN-70A750C8…`: config `{cycles: [1994,…,2022], contested_only: true}`; validation `rows` 1004, `minimum_contested_coverage` 0.0.

Live state: `warehouse_manual_adjudication` has exactly 1 row, `ADJ-1994-MORGAN-26001-AG2-K48` (`elections_source` /
`vote_observation_cell` / subject `SRC-E64FFC4299ED54CB2D3A:94g-prec/MORGAN.XLS:Morgan:R48C11` / `reported_count=144` / `approved`);
`vote_observations` rowid 2424457 = (1994, Attorney General, MORGAN, 26001, SESSIONS, 144.0 REAL); zero non-integer `votes` remain.

Writers (code): `scripts/build_1994_cmo_baseline.py:173-190` writes `mart_historical_precinct_district_weight`,
`mart_historical_district_office_baseline`, `mart_historical_cmo_race_feature`, `qa_historical_baseline_allocation`
(`DELETE … WHERE cycle=1994` then append; `register_table`; also `register_source_file` upserts for two plan files);
`scripts/build_historical_federal_baselines.py:141-147` deletes and rewrites `mart_historical_federal_district_baseline`
(also writes CSVs under `data/processed/elections/`, outside the warehouse). Registry entries do not carry run ids, so the
footprint was verified by content, not by registry lookup.

Full-content footprint (reviewer's own pass, 324 s): for every one of the 120 tables in both the pre-adjudication backup and the
live file, a SHA256 over `SELECT * … ORDER BY rowid` rows (the adjudication script's `digest_rows` serialization), with
`vote_observations` split into rowid 2424457 and all other rows; plus a digest of `sqlite_master`. 122 keys compared; exactly nine differ:

| object | backup -> live |
|---|---|
| `vote_observations` rowid 2424457 | `votes` 144.4 -> 144.0; the other 23 columns identical |
| `vote_observations` all other rows | identical; digest `240f226fe02401ebe8dc20563049b5df9beb3b4a1b124b2423ef636c18a34e52` = ledger `observations_digest_excluding_cell` |
| `mart_historical_precinct_district_weight` | 6,441 -> 7,384 rows (= `weight_rows`) |
| `mart_historical_district_office_baseline` | 278 rows both; content rewritten |
| `mart_historical_cmo_race_feature` | 139 rows both (= `race_rows`); content rewritten |
| `qa_historical_baseline_allocation` | content rewritten |
| `mart_historical_federal_district_baseline` | 1,004 rows both (= `rows`); content rewritten |
| `warehouse_build_run` | 124 -> 127 |
| `warehouse_manual_adjudication` | 0 -> 1 |
| `qa_warehouse_source_repair` | 55 -> 56 (`WQA-04-fractional-adjudicated-RUN-C0A15A7A…`, `vote_observations`, `1994/MORGAN/26001/AG2`, `repaired_with_adjudication`) |

Everything else is byte-for-byte identical in content, including `canonical_candidates` (`95078def…`), `warehouse_source_file`
(`b00d8991…` — the two `register_source_file` upserts were no-ops), `warehouse_table_registry` (`d3a55e8a…`), `warehouse_schema_version`
(`898094d7…`), the schema (`sqlite_master` digest equal; 302 objects both), and the three tables behind the training frame (check 3).
The schema cookie moved 589 -> 591 with identical `sqlite_master` content, consistent with the two `executescript(SCHEMA)` passes
(DROP/CREATE VIEW) in the mart builders. The ledger, the evidence JSON `change_scope`, and the observed footprint agree.

Result: confirmed. One `vote_observations` cell, one adjudication row, one QA row, three ledger rows, and the five declared
1994/federal mart or QA tables; nothing else.

## Check 3 — relevance to the approved run (training-frame scope)

`scripts/retrain_post2016_southern_war_v3.py:310` calls `v2.load_training()`; `scripts/retrain_post2016_southern_war_v2.py:72-110`
is the only warehouse read in the v3 code path (v3 has no `read_sql`/`sqlite3.connect` of its own; the remaining v2 reads at lines
118, 141 and 604 are CSVs declared in `input_hashes`, all unchanged). The query (lines 73-90) is
`SELECT … FROM mart_southern_war_training_with_finance WHERE cycle > ? AND training_status = ?` with `CUTOFF_CYCLE = 2016`
(line 40) and `TRAINING_STATUS = 'strict_war_ready_no_finance'` (line 41), opened `mode=ro` (line 91), followed by a lookup of the
single `build_run_id` in `warehouse_build_run` (lines 97-99) and hard assertions `cycle > 2016` for every row (line 102) and
race-key uniqueness (line 104).

Live view chain (`sqlite_master`): `mart_southern_war_training_with_finance` (view) -> `mart_southern_war_training_no_finance` (view)
and `mart_southern_race_finance` (table); `mart_southern_war_training_no_finance` -> `mart_southern_war_outcome` (table) LEFT JOIN
`mart_southern_war_context_feature` (table) (`scripts/warehouse_southern_war_preparation_schema.sql:96-135, 155-181`). The three base
tables are materialized; no view in the warehouse references `mart_historical_*`, `qa_historical_*` or
`warehouse_manual_adjudication`; `vote_observations` is referenced only by `canonical_vote_observations` and `qa_vote_observation_quality`,
neither of which is in this chain. Live frame under the training predicate: 3,660 rows, cycles 2018-2024, 14 states, one
`build_run_id` = `RUN-92AB8DE353AC47D6AECE3D7767C29FCD`; `mart_southern_war_outcome` spans cycles 2016-2024, chambers lower/upper
only (the 620 cycle-2016 rows are excluded by the predicate). The edited row is a 1994 statewide (district NULL) Attorney General
precinct cell, so it can enter neither the outcome table (legislative races, 2016+) nor the frame (cycle > 2016); the five rebuilt
mart/QA tables are Alabama 1994-2022 statewide/federal allocation marts that no object in the chain reads. Check 2 also shows all
three base tables content-identical to the pre-adjudication backup.

Result: confirmed — none of the check-2 changes can reach the approved run's training frame.

## Check 4 — replay verification (independent recomputation and fresh replay)

Reviewer digest code (own, not the driver's): assert the header's first column is `model_run_id`, drop the first field of every
line with line endings preserved, verify each file carries exactly one run id matching `^WAR-POST2016-V3-[0-9A-F]{20}$`, count rows.

Scratch bundle present at review start (`WAR-POST2016-V3-58FF952DE4FACDAF75BD`, manifest generated 2026-09-11T04:46:39Z): 13/13 CSVs
equal the approved bundle without the run id, row counts equal (race_war 3660, candidate_cycle_war 7320, structural_forward_predictions
31620, structural_forward_metrics 120, validation_cross_fitted_predictions 3660, structural_coefficients_by_cycle 204,
lag_diagnostics_by_cycle 6, v2_correction_comparison 3660, coverage 94, finance_forward_predictions 29003, finance_forward_metrics 78,
finance_nested_predictions 2754, finance_nested_metrics 8). All 26 `approved_digest`/`scratch_digest` values in `comparison.json` were
reproduced with a driver-compatible (line-ending-stripped) digest; `comparison.json.outputs` equals the evidence JSON
`second_revision.scratch_replay.outputs` and equals `comparison.rev1.json.outputs` (the rev-1 record is preserved, scratch id
`WAR-POST2016-V3-142199F69DF8300F1E20`, sqlite `77379bb5…`).

Manifest comparison (approved vs scratch): `warehouse_build_run_id`, `diagnostics`, `configuration`, `code_hashes`,
`methodology_version`, `warehouse_code_commit`, `status` equal; `input_hashes` differ on exactly one key,
`data/processed/elections/alabama_elections.sqlite` (`8cb49945…` -> `e2dbdb9d414041bf61eec83bca8e3c9439eae35b03822dddec9ac3f41bfe72bd`);
`model_run_id`, `generated_at_utc`, `source_commit`, and the per-file `outputs`/`reports` digests differ as expected (run id column,
scratch paths).

Fresh replay: `.venv/Scripts/python.exe artifacts/war/alabama_dependency_rebuild_20260910/v3_scratch_replay.py` -> `scratch_run_id`
`WAR-POST2016-V3-58FF952DE4FACDAF75BD` (deterministic from `run_basis`, which includes the input hashes, so the same id ties the replay
to `e2dbdb9d…`), `input_hash_differences` = [sqlite], `code_hash_differences` = [], `diagnostics_equal` true, `configuration_equal` true,
`all_outputs_identical_without_run_id` true, 13/13, `elapsed_seconds` 10.8. The reviewer's digest pass on the fresh outputs again shows
13/13 identical with equal row counts; the fresh scratch manifest's sqlite input hash is `e2dbdb9d…`; the fresh `comparison.json.outputs`
equals the evidence JSON's array.

Driver monkeypatch: `v3_scratch_replay.py:24-33` replaces `v3.sha256` (`retrain_post2016_southern_war_v3.py:36-37`,
`hashlib.sha256(path.read_bytes())`) with a 1 MiB streaming loop. The function was extracted with `ast` (without executing the module)
and compared with `hashlib.sha256(read_bytes())` on `manifest.json`, `coverage.csv`, `finance_forward_predictions.csv` and the driver
itself: identical in all four cases; on the 5.8 GB file it produced the same `e2dbdb9d…` as `sha256sum`. The approved script's bytes
are unchanged (`code_hash_differences` empty).

Side effect to disclose: the re-run rewrote `v3_scratch/comparison.json` (`elapsed_seconds` 8.1 -> 10.8), the scratch manifest
(`generated_at_utc` now 2026-09-11T05:03:15Z) and the scratch CSVs/reports with identical content. `comparison.rev1.json` untouched.

## Check 5 — governance

- `model_run_id` `WAR-POST2016-V3-4AF79A70EAA8F39EBD49`, `manifest_sha256` `c6c09e19…`, original `review_record_sha256` `cd084725…`
  and the decision text (`decision`, `limits`, `supersedes`, `resolved_blockers`) are unchanged; the first-revision entry is present and
  intact (`declared_sha256` `8cb49945…`, `accepted_sha256` `77379bb5…`, `review_record_sha256` `451ffaf5…` = the file's live digest,
  `review_verdict` pass, `accepted_at_utc` 2026-09-11T04:05:28Z). `git status` shows no modification under
  `data/processed/war/post2016_southern_war_v3/`, `docs/southern*`, `docs/data/southern*`, or the original review record.
- Gate probe (read-only, live manifest, 25 declarations): `reviewed_input_revisions(decision)` returns `{(sqlite, 8cb49945…): 77379bb5…}`;
  `require_declared_files` and `require_approved_release` currently refuse with `Declared manifest file changed: …alabama_elections.sqlite`
  (expected: the gate re-blocks on the new bytes). `require_declared_files(manifest, ROOT, {(sqlite, 8cb49945…): e2dbdb9d…})` passes;
  mapping to `77379bb5…`, to a digest differing in the last hex digit, or keying by `(sqlite, 77379bb5…)` all refuse. Only the
  `e2dbdb9d…` byte state is unblocked by the correct entry.
- Entry-shape probe (finding 1): appending a second entry with `declared_sha256` `8cb49945…` makes `reviewed_input_revisions` raise
  `Duplicate accepted input revision`; a second entry keyed `declared_sha256` `77379bb5…` -> `e2dbdb9d…` parses but is never consulted
  (the manifest declares `8cb49945…`) and the gate still refuses; re-pointing the single `(sqlite, 8cb49945…)` entry to `e2dbdb9d…` passes.
- Owner authorization is quoted in the evidence JSON (`authorization`); the adjudication itself carries its own owner disposition and
  PASS review (`MORGAN_1994_ADJUDICATION_REVIEW_2026_09_10.md:183`). Publication is not implied: `not_established` still lists
  publication approval first and the decision's `limits` text is unchanged. `docs/` does carry uncommitted modifications from other
  work (Alabama v1/forecast data files and pages), none touching Southern published outputs; they are outside this review.

## Findings

1. **(P1, action required before amending) The current gate admits only one entry per `(path, declared_sha256)`, so this revision
   cannot be recorded as a second entry alongside the first.** `reviewed_input_revisions` keys by `(path, declared_sha256)` and raises
   on duplicates; `require_declared_files` looks up `(relative, declared)` where `declared` is the manifest's `8cb49945…`. A second
   entry keyed `8cb49945…` breaks the whole decision (`Duplicate accepted input revision`); one keyed `77379bb5…` is never consulted.
   The only enforceable amendment under the accepted gate is a single entry with `path` `data/processed/elections/alabama_elections.sqlite`,
   `declared_sha256` `8cb49945d657b0d928dee1bfdaa33d4729c5c8fbda5c51217d1cc55492ba03b5`, `accepted_sha256`
   `e2dbdb9d414041bf61eec83bca8e3c9439eae35b03822dddec9ac3f41bfe72bd`, `review_record_path`
   `project_docs/audits/SOUTHERN_V3_INPUT_REVISION_2_REVIEW_2026_09_10.md` and `review_record_sha256` = this file's final SHA256. The first
   revision's lineage (`77379bb5…`, `RUN-91B2A0C3…`/`RUN-55E4997B…`, `SOUTHERN_V3_INPUT_REVISION_REVIEW_2026_09_10.md` `451ffaf5…`) should be
   preserved in non-gate fields of that entry (e.g. a `superseded_revisions` list), since the gate ignores unknown keys. Extending the gate
   to chained revisions is the alternative, but that is a gate change needing its own review and is not endorsed here. Consequently the
   literal reading of "the first revision entry remains intact" holds now but cannot hold after amendment without a gate change.
2. **(P3) Mart builder scripts are uncommitted while the ledger records `code_commit` `720c3507…`.** `scripts/build_1994_cmo_baseline.py`
   and `scripts/build_historical_federal_baselines.py` are modified against HEAD and `scripts/repair_morgan_1994_fractional_cell.py` is
   untracked; `RUN-22C8E3AE…`/`RUN-70A750C8…` record no script hashes (the adjudication run does, and they match the current files).
   Commit them so `code_commit` becomes meaningful for the two mart runs. Does not affect this decision (those tables are outside the frame).
3. **(P3) Driver hash changed from the rev-1 review (`69a2ab47…` -> `d1a7fbf2…`).** Caused by the disclosed `streaming_sha256`
   monkeypatch (`driver_note`); equivalence with `hashlib.sha256(read_bytes())` verified here. No action.
4. **(Info) Evidence `elapsed_seconds` vs `comparison.json`.** The evidence JSON does not record a rev-2 `elapsed_seconds`; the file now
   shows 10.8 (this review's re-run) instead of 8.1. No effect on the gate.
5. **(Info) Schema cookie 589 -> 591 with identical `sqlite_master` content**, consistent with the two `executescript(SCHEMA)` DROP/CREATE
   VIEW passes. Not a defect.

No defect was found in the evidence, the ledger, the change footprint, or the replay. Finding 1 constrains how the decision is amended;
it does not weigh against accepting the byte state.

## Verdict

Verdict: PASS — the second accepted input revision for data/processed/elections/alabama_elections.sqlite (77379bb5… -> e2dbdb9d…) is supported by the reproduced replay, the ledger and the training-frame scope.

Amend the decision per finding 1 (single `(sqlite, 8cb49945…)` entry re-pointed to `e2dbdb9d…`, bound to this file's final SHA256,
with the first revision's lineage retained in non-gate fields). After amendment `require_approved_release` is expected to pass, since
only the warehouse declaration drifts and the mapping was shown to pass on the live manifest; any further byte change re-blocks.

## Remaining limitations

- This is file-integrity and reproduction acceptance for one further input revision of one approved run. It is not renewed scientific
  acceptance, not publication approval, and not validation of the 1994 adjudication's downstream products (`not_rebuilt` in
  `RUN-C0A15A7A…`: CMO CSVs, `alabama_historical_war_v1`, pages, forecast), which must rebuild and pass their own gates.
- The rev-1 logical anchor is the `Connection.backup()` image `pre-morgan-1994-adjudication-2026-09-10.sqlite`, not the `77379bb5…` bytes
  themselves (no backup-API image can byte-match the live file; see the rev-1 review, check 5). Its size, page count, 124-row ledger and
  the adjudication script's own control-snapshot check against the live pre-state tie it to the rev-1 state; row-level equality with
  `77379bb5…` beyond that is inferred, not recomputed.
- The replay proves equivalence for the v3 code path only. Other whole-database consumers need their own freshness review.
- Rebuilt 1994/federal mart contents were not validated for correctness here; only their footprint and irrelevance to the frame were.
- No test suite ran for this review; the gate was exercised only through the read-only probes above.
