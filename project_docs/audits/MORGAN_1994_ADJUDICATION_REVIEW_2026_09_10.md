# Morgan 1994 fractional cell — independent review of the staged adjudication (2026-09-10)

Independent pre-application review (AGENT_WORKFLOW.md §5) of the staged warehouse correction
`scripts/repair_morgan_1994_fractional_cell.py`, its fixture tests, and the live dry-run proposal.
The reviewer did not write the script, the tests, or the evidence audit. Everything below was
reproduced from the raw archive, the read-only warehouse, and the code as read on 2026-09-10; the
implementer's summary was not relied on.

Reviewer side effects: this file only. No warehouse write (every warehouse connection was
`mode=ro` + `PRAGMA query_only=ON`), no `--apply`, no commit, no `docs/` write, nothing under
`data/raw/` opened for writing (archive members read in memory via `zipfile` + `xlrd`).

## Snapshot

| Item | Value |
|---|---|
| HEAD | `720c3507b147bc0a7c048c4c84ab0262920802c1` |
| `scripts/repair_morgan_1994_fractional_cell.py` | untracked (`??`); sha256 `6865f2d57e48afe1aaa46675f84c259c88777b68bbdbcb5a51865189f6039733` |
| `scripts/tests/test_repair_morgan_1994_fractional_cell.py` | untracked (`??`); sha256 `eee486e306ab1701f67acc36e5dd4dc2dcf5c1ff316cd9c8e1aebf9ab5682ae6` |
| `scripts/warehouse.py` | tracked, clean; sha256 `dd9df42bbb3760a51443027f53f166d7f943e8d3e8ba9ce4461ac403b72234e0` |
| `scripts/source_vote_quality.py` | untracked (`??`); sha256 `9a3b4755459a63ca6da7368f32232f4c6e5ce5733312d1673e4fa95077633547` |
| `project_docs/audits/MORGAN_1994_FRACTIONAL_CELL_QUARANTINE_2026_09_10.md` | untracked; sha256 `82d6f79e63b0fd88f56f4b4e5fa7e557920f1d9115d2a95ff740d8cb2fbd8f90` |
| `project_docs/audits/MORGAN_1994_FRACTIONAL_CELL_QUARANTINE_2026_09_10.json` | untracked; sha256 `2525020ec41689ae99f1acb6545feedc1a8bba13c33dc248a9f503c7167851e1` |
| Warehouse | `data/processed/elections/alabama_elections.sqlite`, 5,819,056,128 bytes, mtime 2026-09-08T15:38:30Z (not hashed: 5.8 GB, read-only throughout) |
| Latest `warehouse_build_run` | `RUN-55E4997B16DA4330BF6E2EE7A1E5FD36` (`shor_manifest_registry_metadata`, `validated`) |

## Check 1 — raw evidence (immutable source)

Registry query (read-only): `SELECT local_path, sha256 FROM warehouse_source_file WHERE
source_file_id='SRC-E64FFC4299ED54CB2D3A'` →
`data/raw/alabama_elections_and_geography/94g-prec.zip`,
`94512391c389c45d2899f06686484790adaf4c99fa638b217e31f54652c55097`.

Streamed sha256 of the archive on disk: `94512391c389c45d2899f06686484790adaf4c99fa638b217e31f54652c55097`
— **matches the registry row**. Member `94g-prec/MORGAN.XLS` read from the archive in memory:
40,960 bytes, sha256 `e00a9c487b38490a9e6d97c2e85b8f2d3dd07d6e5a2cd3d4eb102d70c30a7b39` (matches
`EVIDENCE['raw_member_sha256']` in the script and the audit JSON). Workbook has one sheet,
`Morgan`, 53 × 63.

| Cell | Observed | Expected |
|---|---|---|
| K3 / K4 / K5 | `Sessions` / `AG2` / `AG2` | header + ballot code |
| C48 | `26001.0` | precinct 26001 |
| **K48** | **`144.4`** | 144.4 ✔ |
| B52 / K52 | `Total Votes - Reported` / `21571.0` | 21,571 ✔ |
| B53 / K53 | `Total Votes - Calculated` / `21571.4` | 21,571.4 ✔ |

- Non-integer numeric cells in the data block rows 6–51 × columns D–S: exactly one, `(48, 11, 144.4)` ✔.
- Non-integer numeric cells anywhere on the sheet: `(48, 11, 144.4)` and `(53, 11, 21571.4)` — the
  second is the calculated total that re-adds the fraction; there is no other fractional cell.
- Column K rows 6–51: 46 numeric cells, no blanks/text. Sum of the 45 cells other than K48 =
  **21,427.0** ✔; 21,427 + 144 = 21,571 = K52; 21,427 + 144.4 = 21,571.4 = K53.

Additional cross-column check (not requested, strengthens the reading): for every one of the 60
candidate columns D–BK, row 52 (`Reported`) and row 53 (`Calculated`) both equal the column's
row 6–51 sum **except column K**, where only row 53 equals the printed sum and row 52 differs by
exactly 0.4. Row 52 is therefore not a mechanical recomputation of the printed cells in that
column; the sheet's own `Reported` row states 21,571. Nothing in the workbook contradicts the K52
reading. (The archive still cannot prove *how* K52 was produced — see Limitations.)

## Check 2 — live staging (dry run) and independent SQL

Command: `.venv/Scripts/python.exe scripts/repair_morgan_1994_fractional_cell.py --expected-run RUN-55E4997B16DA4330BF6E2EE7A1E5FD36`
(0.61 s). Output: `warehouse_status = dry_run`, `latest_run = RUN-55E4997B16DA4330BF6E2EE7A1E5FD36`,
one observation `rowid 2424457` with `source_file 94g-prec/MORGAN.XLS`, `source_sheet Morgan`,
`source_row 48`, `source_column 11`, `source_file_id SRC-E64FFC4299ED54CB2D3A`, `ballot_code AG2`,
`candidate_key SESSIONS`, `party_norm R`, `votes 144.4`, `build_run_id RUN-40A033B9854141F6B05A76173E66D17B`;
`fractional_observations_in_table = 1`; `prior_review = {WQA-04-fractional-evidence, source_review}`;
`existing_adjudication = null`; `proposal = {rowid 2424457, 144.4 -> 144.0}`. Matches the primary's
reported staging exactly.

Independent read-only SQL (`mode=ro`, `PRAGMA query_only=ON`):

| Query | Result |
|---|---|
| `SELECT rowid, votes, typeof(votes) … WHERE source_file_id='SRC-E64FFC4299ED54CB2D3A' AND source_sheet='Morgan' AND source_row=48 AND source_column=11` | one row: `(2424457, 144.4, 'real')` |
| same locator by `source_file='94g-prec/MORGAN.XLS'` | `COUNT(*) = 1` |
| `SELECT COUNT(*) FROM vote_observations WHERE votes <> CAST(votes AS INTEGER)` | **1** |
| `SELECT COUNT(*) FROM vote_observations WHERE votes=144.4` | 1 |
| `SELECT COUNT(*) FROM vote_observations` | 2,184,861 |
| `qa_warehouse_source_repair WHERE issue_id='WQA-04-fractional-evidence'` | present: `vote_observations`, `1994/MORGAN/26001/AG2`, `source_review`, run `RUN-C7DE0A0267EC4445938D1CA0CB5C4BD3`, 2026-09-05T21:35:27Z |
| `warehouse_manual_adjudication WHERE adjudication_id='ADJ-1994-MORGAN-26001-AG2-K48'` | none (table currently has 0 rows) |
| triggers on `vote_observations` / `warehouse_manual_adjudication` / `warehouse_build_run` / `qa_warehouse_source_repair` | none (database has 0 triggers) |
| `vote_observations` schema | ordinary rowid table (no `INTEGER PRIMARY KEY`, not `WITHOUT ROWID`) — rowid is unique but not durable across VACUUM/rewrite; the script re-derives it from the physical locator at apply time rather than hard-coding 2424457 |
| `SUM(votes)` Morgan 1994 AG R | 21,571.4 (= K53 today) |
| `SUM(votes), COUNT(*)` statewide 1994 AG R | 660,998.4 over 3,026 rows (3,025 integer rows = 660,854.0 + this cell) |

Live schemas of `warehouse_manual_adjudication`, `qa_warehouse_source_repair` and
`warehouse_build_run` were read and match the fixture `SCHEMA` in the test module column-for-column
(including the `review_status` CHECK and the `build_run_id` foreign key), so the positional
`INSERT INTO qa_warehouse_source_repair VALUES (?,?,?,?,?,?,?)` binds the intended columns.

## Check 3 — code review of the apply path

Read in full: `repair_morgan_1994_fractional_cell.py` (304 lines), `source_vote_quality.py`,
`warehouse.py` helpers (`begin_run`, `finish_run`, `file_sha256`, `git_commit`, `database_path`),
and the mirrored `repair_alabama_canonical_certified_totals.py` (`authorize`, `repair`, guard sites).

| # | Guard | Finding |
|---|---|---|
| a | Authorizer | `authorize` permits `SQLITE_INSERT` only for `warehouse_manual_adjudication`, `warehouse_build_run`, `qa_warehouse_source_repair`; `SQLITE_UPDATE` only for `vote_observations.votes` and any column of `warehouse_build_run` (needed by `finish_run`); denies every DELETE/DDL/ATTACH action and any write originating from a trigger/view. Exercised directly with 24 (action, table, column, trigger) cases — all decisions as intended. Passthrough (`SQLITE_OK`) remains for PRAGMA/TRANSACTION/REINDEX/ANALYZE/CREATE_VTABLE exactly as in the mirrored pattern; none is issued by the script. Authorizer is installed before `begin_run` and after the backup/hash checks, so every SQL write is under it. ✔ |
| b | Guarded UPDATE | `UPDATE vote_observations SET votes=? WHERE rowid=? AND votes=?` with `(144.0, rowid, 144.4)`; `rowcount != 1` raises. rowid is unique, so at most one row can match; the authorizer forbids any other UPDATE of the table. ✔ |
| c | Recorded evidence | Adjudication row: `subject_id SRC-E64FFC4299ED54CB2D3A:94g-prec/MORGAN.XLS:Morgan:R48C11`, `decision reported_count=144`, `rationale` (K52/K53 argument), `evidence_locator` JSON with `audit`, `prior_review`, `reported_cell/value 144.4`, K52/K53 cells and values, 45/1 cell counts, both raw sha256s, materiality; `review_status approved`; `decided_at_utc`. QA row (`WQA-04-fractional-adjudicated-<run>`, status `repaired_with_adjudication`): full `before_image` and `after_image` rows, `adjudication_id`, `backup`, `remaining_fractional_observations`, `not_rebuilt`. Build-run `configuration_json`: `authorized_by`, `authority`, `audit`, `prior_review`, `cell`, `evidence`, `backup`, `expected_run`, before digests/counts, `application_code_sha256`. Owner authorization is therefore recorded, but in the run row rather than in the adjudication/QA rows (Finding 2). ✔ with note |
| d | Other observations | `observations_digest_excluding(rowid)` (sha256 over `SELECT rowid,* … WHERE rowid<>? ORDER BY rowid`) computed before the write and compared after; also recorded in `configuration_json`. ✔ |
| e | Control tables | `control_snapshot` digests `warehouse_build_run`, `qa_warehouse_source_repair`, `warehouse_manual_adjudication`, `warehouse_source_file`, `warehouse_table_registry`, `warehouse_schema_version`, `canonical_candidates` before; after the write the three owned tables must show exactly +1 row with the first N rows (`ORDER BY rowid LIMIT before_count`) digest-identical, every other control table digest-identical and count-identical, and `vote_observations` count unchanged. ✔ |
| f | Backup | Path must differ from the database, must not exist, and `<backup>.application.json` must not exist; created with exclusive `open('xb')`; populated by `sqlite3.Connection.backup` from a separate `mode=ro` connection; `PRAGMA quick_check == [('ok',)]`; `control_snapshot(backup) == before_controls`; `locate(backup) == [row]` (holds the reported 144.4 cell). ✔ |
| g | Expected run | `--expected-run` must equal `SELECT build_run_id FROM warehouse_build_run ORDER BY rowid DESC LIMIT 1`, checked inside `BEGIN IMMEDIATE`, so no run can be appended between the check and the write. Required for `--apply`. ✔ |
| h | FK | `PRAGMA foreign_keys=ON` before the transaction; `PRAGMA foreign_key_check` must return nothing before `finish_run`/commit. ✔ |
| i | Rollback | `except BaseException: connection.rollback(); raise` around the whole transaction; verified by fault injection (below): after an injected failure *after* the UPDATE, observations, adjudication (0 rows), build-run and QA counts were all back to the pre-state. ✔ |
| j | Idempotence | If `ADJ-1994-MORGAN-26001-AG2-K48` exists or the cell already reads 144.0 the script rolls back and returns `unchanged` without creating a backup (verified in dry-run and `--apply` mode on an already-applied fixture). Any other value raises `Cell no longer holds the reported value`. ✔ |

Second-row exposure: none found. The only statement touching `vote_observations` is the single
rowid-guarded UPDATE; the authorizer denies INSERT/DELETE on the table and UPDATE of any other
column; `stage` refuses unless the physical-locator predicate returns exactly one row; the
other-rows digest and the table count are re-verified after the write.

Additional guard probes on `tmp_path`-style fixtures (throwaway, not saved):

- duplicate locator row inserted → `ValueError: Expected exactly one Morgan 1994 AG2 observation, found 2` (no write);
- `CREATE TRIGGER … ON vote_observations` present → `--apply` refused with `Triggers on owned tables require separate review`, database unchanged, no backup file created;
- `require_reported_vote_quality` monkeypatched to raise after the UPDATE → `RuntimeError` propagated, all rows/counts restored; the pre-state backup file remains on disk (Finding 3);
- normal `--apply` → prior `WQA-04-fractional-evidence` row byte-identical before/after; `typeof(votes)` after = `real`, value `144.0`; re-run `--apply` with a fresh backup path → `unchanged`, no backup created.

## Check 4 — tests

Command: `.venv/Scripts/python.exe -m pytest --testmon --testmon-noselect -p no:cacheprovider scripts/tests/test_repair_morgan_1994_fractional_cell.py -q`
→ **4 passed**, 0 failed, 0 skipped, 0.46 s. All four build a fresh SQLite file under `tmp_path`
(`build_warehouse`), so the live warehouse is never opened by the tests.

Coverage of the guards: dry run writes nothing (a, j); apply changes exactly one cell and leaves
every other observation row byte-identical (b, d); adjudication decision/status/rationale and QA
before/after images recorded (c); prior QA row count preserved (e, partial); backup holds 144.4
and the application report is written (f, partial); re-application is `unchanged` (j);
snapshot mismatch refuses before any write (g); drifted value refuses; missing `--authorized-by`
and an existing backup path refuse (f). Not exercised by the fixtures: the authorizer deny
branches, the trigger refusal, the digest/count mismatch raises, the FK check and the rollback
path — these are defensive checks that need fault injection; the reviewer exercised the trigger,
rollback and duplicate-row paths manually (above). Proportionate to the mirrored pattern.

## Check 5 — governance

- The change is a human adjudication recorded as data, not a code conditional: stable id
  `ADJ-1994-MORGAN-26001-AG2-K48`, `domain elections_source`, `subject_type vote_observation_cell`,
  evidence locator, rationale, `review_status approved`, `decided_at_utc`, `supersedes NULL`. No
  consumer or adapter is being taught to round; `source_vote_quality.py` still refuses fractions.
- Raw workbook untouched: the script never opens `data/raw/`; the archive hash on disk equals the
  registry hash after all review activity.
- Prior `WQA-04-fractional-evidence` row: not updated or deleted by any statement (authorizer
  denies UPDATE/DELETE on `qa_warehouse_source_repair`); verified byte-identical after a fixture
  apply; the new row uses a distinct id `WQA-04-fractional-adjudicated-<run>`.
- Nothing rebuilt: the only writes are the three control-row inserts, the one-column UPDATE and
  `finish_run`. The `not_rebuilt` list is truthful; it is a coarse inventory (see Finding 4) — the
  authoritative stale-dependency trace is the quarantine audit (9 files + 3 warehouse tables).
- The proposal did not alter `canonical_vote_observations` semantics; the corrected cell remains
  `authority_rank 1` and the QA view will simply stop flagging it after apply.

## Check 6 — materiality

From the warehouse: statewide 1994 AG R = 660,998.4 over 3,026 rows, of which 3,025 integer rows
sum to 660,854.0; integer reading → 660,998.0, Δ = **0.4 votes** (relative 6.05e-7). Smallest
1994 Attorney General two-party totals in `mart_historical_district_office_baseline`: House
6,236.72199379276 (104 districts), Senate 22,395.65003983679 (35). Upper bound if the whole 0.4
landed in one district: 0.4 / 6,236.72 × 100 = **0.006414 pp** (House), 0.001786 pp (Senate) —
matches the audit and `EVIDENCE['max_district_effect_pp']`. Nothing in the raw sheet, the
warehouse, or the audit contradicts the K52 reading; the cross-column check above is additional
support for it.

## Findings

| # | Severity | Finding | Blocking? |
|---|---|---|---|
| 1 | info | The evidence audit's sentence "the 3,026 non-fractional rows contribute 660,854.0" should read 3,025 non-fractional rows (3,026 is the total including K48). Arithmetic and conclusions unaffected. | No |
| 2 | low | `authorized_by` (owner authorization reference) is recorded only in `warehouse_build_run.configuration_json`; the adjudication row's `evidence_locator` and the QA row's `evidence_json` do not carry it or the run id. The QA row links to the run by FK and to the adjudication by id, so provenance is complete by join; from the adjudication row alone the run is found only via the shared timestamp or a LIKE on the QA row. Optional hardening: add `authorized_by` and the run id to the adjudication `evidence_locator`. | No |
| 3 | low / operational | On a failure after the backup is created, the (~5.8 GB) pre-state backup file remains on disk and a retry must use a new path (`FileExistsError`). Free space on the volume at review time: 219 GB. Harmless copy of the pre-state; the operator should point `--backup` at a location with room and clean up on failure. | No |
| 4 | info | `not_rebuilt` names the dependency chain coarsely ("1994 baseline and context marts", `canonical_cmo_features.csv`, `canonical_cmo_candidates.csv`, `cmo_v5_*`, `alabama_historical_war_v1`, pages/forecast) and omits `preliminary_cmo_races.csv`, `canonical_cmo_district_office_baselines.csv`, `historical_cmo_extension.csv` and the three warehouse marts enumerated in the quarantine audit. All named files exist. The list is truthful about what was not rebuilt; the audit remains the authoritative stale inventory and should be cited when revalidating consumers. | No |
| 5 | info | The script, its tests and `source_vote_quality.py` are untracked, so `warehouse_build_run.code_commit` will record HEAD `720c3507…`, which does not contain the applying code. `configuration_json.application_code_sha256` records the exact file hashes, satisfying the code-identification rule; committing the three files before or with the apply makes the run reproducible from git alone. | No |

No P0/P1/P2 defects. No path was found by which a second `vote_observations` row, another
column, the prior QA row, or the raw source could be modified.

## Verdict

Verdict: PASS — the staged adjudication of 94g-prec/MORGAN.XLS Morgan!K48 (144.4 -> 144) is supported by the workbook's reported total and the guarded single-row application is safe to apply against RUN-55E4997B16DA4330BF6E2EE7A1E5FD36.

Conditions carried into the apply (not gates): the latest run must still be
`RUN-55E4997B16DA4330BF6E2EE7A1E5FD36` at apply time (the script enforces this); `--backup` must be
a new path on a volume with ≥ 6 GB free; `--authorized-by` should name the owner decision of
2026-09-10.

## Remaining limitations

- The archive cannot establish *how* K52 was produced (independent canvass figure vs. a rounded
  recomputation). The adjudication rests on the sheet's own `Reported` label and the fact that
  row 52 tracks the printed sum in all 59 other columns but not in K; the true precinct-26001
  count is not independently confirmed. This is the owner's adjudicated reading, recorded as such.
- The warehouse file was not hashed (5.8 GB, memory/time bound); read-only mode and
  `query_only` protected it, and the expected-run guard pins the snapshot for the apply.
- Downstream artifacts and marts that embed 144.4 remain stale after apply until their producers
  rerun and revalidate; this review did not assess them (out of scope, recorded in the audit).
- Authorizer deny branches, digest-mismatch raises and the FK check were verified by reading and
  by direct calls to `authorize`, not by end-to-end fault injection of each branch.
