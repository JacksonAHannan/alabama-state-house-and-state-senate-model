# Alabama 2002 Marshall canonical repair — independent review of the staged correction (2026-09-11)

Independent pre-application review (AGENT_WORKFLOW.md §5) of the staged canonical correction
`scripts/repair_alabama_2002_marshall_canonical.py` (HD26 A1, HD27 B1, SD9 same-defect rule), its
fixture tests, and the live dry-run proposal against `RUN-504CE4C4DF904D88A5A40D268F3FCEAB`. The
reviewer did not write the script, the tests, the adjudication packet or the scratch identity rebuild.
Everything below was reproduced from the raw workbook (xlrd, in memory), the read-only warehouse, the
read-only scratch rebuild, and the code as read on 2026-09-11; the implementer's summary was not relied on.

Reviewer side effects: this file only. No warehouse write (every warehouse connection was
`file:...?mode=ro` + `PRAGMA query_only=ON`), no `--apply`, no commit, no `docs/` write, no other file
edit, nothing under `data/raw/` opened for writing.

## Snapshot

| Item | Value |
|---|---|
| HEAD | `38c30819f3524c3d97cb7a1bfa4fb6ec00e8f249` (2026-09-11T09:47:54-05:00) |
| `scripts/repair_alabama_2002_marshall_canonical.py` | untracked (`??`); sha256 `a7052c10961af84050aa050edd04c7dc06de8ac70c7089671139d3734ad9b89c` |
| `scripts/tests/test_repair_alabama_2002_marshall_canonical.py` | untracked (`??`); sha256 `30ff10b557258ec3751eec9a30465fd2b8dff814452f0ad138f17c69227fe86b` |
| `scripts/warehouse.py` | tracked, clean; sha256 `dd9df42bbb3760a51443027f53f166d7f943e8d3e8ba9ce4461ac403b72234e0` |
| `project_docs/audits/SOURCE_COLLISION_ADJUDICATION_PACKET_2026_09_11.md` | untracked; sha256 `579c589db74d6d97356f4aadf9f385db5934f5218bf2a8dafb3761b6747ac0a5` |
| `artifacts/war/canonical_identity_rebuild_20260911/identity_rebuild_diff.json` | sha256 `358362ddbc50d07df267ddf27c6f3fa9f5f6e8a16996ac96f45d929d548d6cfc` |
| Raw workbook `data/raw/alabama_elections_and_geography/2002-GeneralElection-PrecinctLevel_0.xls` | sha256 `9400cfa16da62d303fac0115707ad3f71fc9d29a36f157ac17e0792d2a5ed45e` — equals the required hash and the `warehouse_source_file` row for `SRC-9E0F7297AEB976F98688` |
| Warehouse | `data/processed/elections/alabama_elections.sqlite`, 5,819,064,320 bytes, mtime 2026-09-11T05:25:44Z, `journal_mode=delete`, `quick_check` ok (not hashed: 5.8 GB, read-only throughout) |
| Latest `warehouse_build_run` | `RUN-504CE4C4DF904D88A5A40D268F3FCEAB` (`southern_war_preparation_no_finance`, `validated`, 2026-09-11T05:25:44Z) |
| Runtime | Python 3.9.6, SQLite 3.35.5, xlrd 2.0.2 (`.venv`) |

## Check 1 — raw evidence (immutable workbook, xlrd read-only)

Workbook: 67 county sheets. Sheet layouts differ: DEKALB/BLOUNT/MADISON carry `Total Number of Votes` in
column F (0-based 5) with precinct cells from column G; MARSHALL carries a duplicated `County`/`Contest Title`
column so its `Total Of Number Votes` sits in column G (0-based 6) with precinct cells from column H — the
column offset that defeated the legacy parse. Every row below was read by `sheet.cell_value(row-1, col)`.

| Sheet!row | Contest title | Party | Candidate | Printed total | Precinct-cell sum (n cells) | Script `cells` |
|---|---|---|---|---|---|---|
| DEKALB!r71 | STATE HOUSE OF REPRESENTATIVES, DISTRICT 26 | DEM | McDaniel, Frank | 1,102 | 1,102 (77) | 1,102 ✓ |
| DEKALB!r72 | STATE HOUSE OF REPRESENTATIVES, DISTRICT 26 | REP | Patterson, Jeffrey | 598 | 598 (77) | 598 ✓ |
| MARSHALL!r65 | STATE SENATE, DISTRICT 9 | DEM | Mitchem, Hinton | 15,689 | 15,689 (50) | 15,689 ✓ |
| MARSHALL!r66 | STATE SENATE, DISTRICT 9 | REP | Edmonds, Doris | 7,557 | 7,557 (50) | 7,557 ✓ |
| MARSHALL!r68 | STATE HOUSE OF REPRESENTATIVES, DISTRICT 26 | DEM | McDaniel, Frank | 5,967 | 5,967 (50) | 5,967 ✓ |
| MARSHALL!r69 | STATE HOUSE OF REPRESENTATIVES, DISTRICT 26 | REP | Patterson, Jeffrey | 3,861 | 3,861 (50) | 3,861 ✓ |
| MARSHALL!r71 | STATE HOUSE OF REPRESENTATIVES, DISTRICT 27 | DEM | McLaughlin, Jeffrey | 7,724 | 7,724 (50) | 7,724 ✓ |
| MARSHALL!r72 | STATE HOUSE OF REPRESENTATIVES, DISTRICT 27 | LIB | Driggers, Allen Eugene | 662 | 662 (50) | not in scope (canonical is D/R only; matches packet B1 'LIB 662 excluded') |
| MARSHALL!r73 | STATE HOUSE OF REPRESENTATIVES, DISTRICT 27 | REP | Hawkins, Gerald (Jerry) | 4,789 | 4,789 (50) | 4,789 ✓ |
| BLOUNT!r65 | STATE SENATE, DISTRICT 9 | DEM | Mitchem, Hinton | 2,029 | 2,029 (26) | 2,029 ✓ |
| BLOUNT!r66 | STATE SENATE, DISTRICT 9 | REP | Edmonds, Doris | 1,232 | 1,232 (26) | 1,232 ✓ |
| MADISON!r79 | STATE SENATE, DISTRICT 9 | DEM | Mitchem, Hinton | **6,725** | **6,885** (99) | 6,885 cells / 6,725 printed ✓ |
| MADISON!r80 | STATE SENATE, DISTRICT 9 | REP | Edmonds, Doris | **7,959** | **8,206** (99) | 8,206 cells / 7,959 printed ✓ |

Adjacent rows (BLOUNT!r67, DEKALB!r73, MADISON!r81, MARSHALL!r67/r70/r74) are `WI`/`WRITE-IN` rows
(11 / 0 / 82 / 50 / 5 / 14 votes); none is D or R and none enters canonical.

All-sheet scan (columns A–F of every sheet, regex on `STATE SENATE, DISTRICT 9` and
`STATE HOUSE OF REPRESENTATIVES, DISTRICT 26|27`): SD9 appears only on BLOUNT (r65–67), MADISON (r79–81),
MARSHALL (r65–67); HD26 only on DEKALB (r71–73) and MARSHALL (r68–70); HD27 only on MARSHALL (r71–74).
**No other sheet carries these contests**, so the district totals 7,069/4,459 (HD26), 24,603/16,995 (SD9)
and 7,724/4,789 (HD27) are complete county complements.

Madison discrepancy reproduced: 6,885 − 6,725 = 160 and 8,206 − 7,959 = 247, exactly `MADISON_DISCREPANCY`.
The gap is **sheet-wide, not SD9-specific**: 109 of 115 Madison value rows have precinct-cell sum above the
printed total (e.g. TOTAL BALLOTS CAST 88,475 printed vs 90,372 cells; the 99 precinct headers have no
duplicates). Existing canonical practice already uses the cell sum for Madison: every Madison-only 2002
contest in `canonical_candidates` (HD6 6,659/4,883; HD10 4,198/8,344; HD19 9,978; HD20 6,779/11,903;
HD21 5,672/5,156; SD7 25,365/12,823) equals the precinct-cell sum, not the printed total. Keeping 6,885/8,206
for SD9 is therefore the consistent rule, and the script records the discrepancy rather than adjusting it.

## Check 2 — stored evidence (read-only SQL)

Segment query (the script's own `stage()` SQL plus provenance columns):

```
SELECT office, CAST(district AS INTEGER), county_key, party_norm, ROUND(SUM(votes)), COUNT(*),
       build_run_id, source_file IS NULL, MIN(source_sheet), MIN(source_row), MIN(source_column), MAX(source_column), source_file_id
FROM vote_observations WHERE source='alabama_sos' AND year=2002
  AND ((office='State Senate' AND district=9) OR (office='State House' AND district IN (26,27)))
  AND party_norm IN ('D','R') GROUP BY 1,2,3,4,7,8,13
```

| Segment | Live sum | `expected_segments()` | Rows | Provenance |
|---|---|---|---|---|
| House 26 DEKALB D / R | 1,102 / 598 | 1,102 / 598 | 77 / 77 | legacy: `build_run_id` NULL, `source_file` NULL |
| House 26 MARSHALL D / R | 5,967 / 3,861 | 5,967 / 3,861 | 50 / 50 | `RUN-40A033B9854141F6B05A76173E66D17B`, sheet MARSHALL rows 68/69, cols 8–57, `SRC-9E0F7297AEB976F98688` |
| House 27 MARSHALL D / R | 7,724 / 4,789 | 7,724 / 4,789 | 50 / 50 | `RUN-40A033B9…`, rows 71/73, cols 8–57 |
| Senate 9 BLOUNT D / R | 2,029 / 1,232 | 2,029 / 1,232 | 26 / 26 | legacy (NULL source_file) |
| Senate 9 MADISON D / R | 6,885 / 8,206 | 6,885 / 8,206 | 99 / 99 | legacy (NULL source_file) |
| Senate 9 MARSHALL D / R | 15,689 / 7,557 | 15,689 / 7,557 | 50 / 50 | `RUN-40A033B9…`, rows 65/66, cols 8–57 |

All 12 sums equal; row counts equal the workbook precinct-cell counts (77/50/26/99); the Marshall column
range 8–57 is exactly the 50 precinct cells after the offset total column. The only non-D/R segment in
scope is MARSHALL HD27 `O` Driggers 662 (matches r72).

Canonical before-images (`canonical_candidates`, `year=2002`): HD26 D `AL-2002-house-26-D-MCDANIEL-FRANK`
1,102.0 winner 1; HD26 R `…PATTERSON-JEFFREY` 598.0 winner 0; SD9 D `…MITCHEM-HINTON` 8,914.0 winner 0;
SD9 R `…EDMONDS-DORIS` 9,438.0 winner 1; **no HD27 rows**. 2002 canonical holds D 112 / R 101 rows only,
139 contests, every contest has exactly one winner and no winner has fewer votes than a rival.

Materialized `canonical_southern_legislative_candidate_election` before-images: the same four ids with
`observation_set_id` `ALCANON-2002-house-26` / `ALCANON-2002-senate-9`, `build_run_id`
`legacy-alabama-canonical`, contract_version 1, votes 1102/598/8914/9438, vote_share 0.6482/0.3518/0.4857/0.5143,
`source_family=alabama_canonical`, authority_rank 5, `validation_status=passed`, `as_of_utc='legacy'`.
Klarner HD27 rows exist: `LCAND-B1A8473C428DB3E46D37` MCLAUGHLIN D 7,724 (share 0.6173) and
`LCAND-9BD17D79BFA93F9EFC32` HAWKINS R 4,789 (share 0.3827), set `LSET-120E9CDFC994B713A780`, authority_rank 30,
`SRC-C3ABE0AF40990D35F24C`; they are the **only** Klarner AL-2002 rows in the table (gap fill for the missing
ALCANON HD27 set). `warehouse_manual_adjudication` has 1 row (`ADJ-1994-MORGAN-…`); none of the three
new ids exists. `PRAGMA foreign_key_check` on the live warehouse: 0 violations (55 s), so the script's
post-apply FK check cannot trip on pre-existing state.

Scratch rebuild (`artifacts/.../scratch_warehouse.sqlite`, read-only): the six 2002 rows in scope equal the
script's after-images field-for-field, including `person_id` `ALPERSON-MCLAUGHLIN-JEFFREY` /
`ALPERSON-HAWKINS-GERALD-JERRY`, `canonical_candidate_id`, `incumbent` 0 and `winner` (D 1 / R 0 in all
three contests). `identity_rebuild_diff.json`: 2002 changes = exactly these 4 vote changes + 2 added rows,
0 removed, 0 name/id/incumbent changes; the other 21 vote changes are 2018 (11) / 2022 (10).

## Check 3 — dry run (read-only)

`.venv/Scripts/python.exe scripts/repair_alabama_2002_marshall_canonical.py --expected-run RUN-504CE4C4DF904D88A5A40D268F3FCEAB`
→ `warehouse_status: dry_run`, `latest_run: RUN-504CE4C4DF904D88A5A40D268F3FCEAB`, proposal with the 4 updates
(1,102→7,069 w1; 598→4,459 w0; 8,914→24,603 w1; 9,438→16,995 w0), the 2 HD27 inserts (D 7,724 w1; R 4,789 w0)
and 3 adjudication ids (`ADJ-2002-AL-HD26-COUNTY-COMPLEMENT`, `ADJ-2002-AL-HD27-MARSHALL-PARSE`,
`ADJ-2002-AL-SD9-MARSHALL-SEGMENT`), plus `madison_discrepancy`. Warehouse mtime unchanged afterwards.


## Check 4 — code review of the apply path

| Item | Finding |
|---|---|
| Authorizer scope | Installed after the backup, before any write. READ/SELECT/FUNCTION allowed; any trigger context denied (and the script refuses if a trigger exists on an owned table; live DB has none). INSERT only into `canonical_candidates`, `canonical_southern_legislative_candidate_election`, `warehouse_manual_adjudication`, `warehouse_build_run`, `qa_warehouse_source_repair`. UPDATE only `canonical_candidates.canonical_votes/winner`, materialized `votes/vote_share`, and `warehouse_build_run` (needed by `finish_run`). DELETE/DDL/ATTACH denied. Correct. |
| Snapshot guard | `expected_run` compared to the last `warehouse_build_run` by rowid inside `BEGIN IMMEDIATE`, so no writer can interleave. |
| Segment guard | 12 live `vote_observations` sums must equal `expected_segments()` (verified equal above). |
| Before-image guards | Canonical: `WHERE canonical_candidate_id=? AND canonical_votes=?` with `rowcount==1`; materialized: `WHERE candidate_result_id=? AND votes=?` with `rowcount==1`; stage-time checks also verify both before-images before any write. |
| Inserts vs unique indexes | `canonical_candidate_id_pk`: new ids; `canonical_candidate_election_uk (year,chamber,district,canonical_party)`: `(2002,house,27,D/R)` absent, explicitly checked by `existing_hd27`. Materialized PK `candidate_result_id`: new ids. All NOT NULL / CHECK columns of the materialized DDL are populated from the template or overrides (office SLDL, chamber lower, votes int ≥ 0, share in [0,1]). |
| Winner rule | `build_candidate_identity.py:229` sets `winner = canonical_votes == max(canonical_votes) over (year,chamber,district)`. After-images: HD26 7,069 > 4,459 → D 1/R 0 (unchanged); SD9 24,603 > 16,995 → D 1/R 0 (flip from R); HD27 7,724 > 4,789 → D 1/R 0. Consistent with the builder and with the scratch rebuild. |
| Other-row digests | `canonical_digest_excluding(4 ids)` before vs `excluding(4 ids + 2 inserted ids)` after — identical row sets since the inserted ids did not exist before; same for the materialized table. Row-count deltas asserted exactly (+2/+2/+3/+1/+1). |
| Control tables | Digests of `warehouse_build_run`, `qa_warehouse_source_repair`, `warehouse_manual_adjudication` (prior rows via `LIMIT before_count`), `warehouse_source_file`, `warehouse_table_registry`, `warehouse_schema_version`, `vote_observations` (2,184,861 rows), `mart_southern_war_outcome` (4,582), `mart_southern_war_context_feature` (8,085) compared before/after and against the backup. |
| Vote-share check | Per `observation_set_id` (`ALCANON-2002-house-26/-27`, `ALCANON-2002-senate-9`) `ROUND(SUM(vote_share),9) == 1.0`; two-party shares, consistent with every existing ALCANON set (0 sets deviate from 1.0 today). |
| Backup | New path required (`open('xb')`), `Connection.backup` from a separate `mode=ro` connection while the writer holds only RESERVED (no write yet, so no backup restart), `quick_check == ok`, control digests equal. Note: 5.8 GB copy plus three passes over 2.18 M `vote_observations` rows; expect several minutes and ensure ≥ 6 GB free at the backup path. |
| Application-code hash | `repair_*.py` + `warehouse.py` sha256 recorded in configuration and re-checked before writes. |
| FK / rollback / report | `PRAGMA foreign_keys=ON`; `foreign_key_check` must be empty (live: 0 violations); `except BaseException: rollback; raise`; report JSON written only after commit, `report_status` honest about post-commit write failure. |
| Idempotence | Re-run returns `unchanged` when any of the 3 adjudication ids or any HD27 canonical row exists (checked before the before-image guard, so a repeat cannot fail spuriously). |
| Materialized template | Copied from `AL-2002-house-26-D-MCDANIEL-FRANK`; everything copied unchanged is chamber/cycle-level (`contract_version` 1, `election_date` 2002-11-05, `district_plan_id AL-2002-house-reported-unknown-vintage`, geography vintage, office/chamber, statuses, provider, family, rank 5, NULL source_file_id) and is identical for HD26 and HD27. Overrides set id, set, district, names, party, votes, share. `build_run_id`/`as_of_utc` are set to the new run/timestamp rather than the view's synthetic `legacy-alabama-canonical`/`legacy` — more traceable, harmless; the `repair_alabama_canonical_certified_totals.py` parity check compares only votes/vote_share. `fact_candidate_election` is a view over `canonical_candidates`, so the `all_southern_…_observations` view tracks the canonical updates automatically and votes/vote_share stay in parity with the materialized rows (0 mismatches today). |
| Klarner HD27 conflict | `canonical_southern_legislative_candidate_election` is materialized from `resolved_southern_legislative_candidate_election`, which keeps one observation set per (state,cycle,stage,chamber,district) by authority rank; today 0 contests have >1 set. After the insert AL/2002/lower/27 will hold two sets (ALCANON rank 5 and Klarner `LSET-120E…` rank 30). Downstream: `fact_southern_legislative_final_candidate_election` ranks sets by date (both 2002-11-05) then `observation_set_id` ascending, so `ALCANON-2002-house-27` wins and the Klarner rows drop out of the final view and of `qa_southern_legislative_final_competition_coverage`; `load_southern_war_preparation_warehouse.py` reads `cycle BETWEEN 2016 AND 2024` and sorts by `authority_rank` anyway; no FK rows reference the two Klarner ids. **No double counting reaches any mart**, but the resolution invariant of the materialized table is broken for one contest until `load_southern_legislative_history_warehouse.py` re-materializes it (that loader `DELETE`s and re-inserts from the resolved view, which would then drop the Klarner HD27 rows). See F2. |
| `not_rebuilt` | Every listed item is genuinely untouched. The list is incomplete — see F3. |
| Adjudication rows | `domain=elections_canonical`, `subject_type=canonical_contest` are new vocabulary values (only `elections_source`/`vote_observation_cell` exist); no CHECK constrains them. `review_status=approved`, stable ids, rationale, evidence_locator JSON with packet, source file, run, authorizer and (for SD9) the Madison discrepancy. Satisfies the AGENTS.md adjudication rule. |

## Check 5 — tests

`.venv/Scripts/python.exe -m pytest --testmon --testmon-noselect -p no:cacheprovider scripts/tests/test_repair_alabama_2002_marshall_canonical.py -q`
→ **4 passed in 0.59 s**, 0 failed, 0 skipped, 0 deselected.

| Guard | Exercised by fixture |
|---|---|
| Segment guard | yes (`break_segment`: HD27 MARSHALL D − 1 → `Source segments differ`) |
| Canonical before-image guard | yes (`break_before`: SD9 D 8,900 → `Before-image mismatch`) |
| Materialized before-image guard | no (canonical guard trips first) |
| Snapshot guard | yes (`RUN-OTHER` → `snapshot changed`, table unchanged) |
| Fresh-backup guard | yes (`FileExistsError`) |
| Apply + backup + report + winner flip + share sums + unrelated table preserved | yes |
| Idempotence | yes (second `repair(db)` → `unchanged`) |
| Authorizer denial, trigger refusal, code-hash drift, other-row digest failure | not exercised |

The fixture materialized table omits the live PK/CHECK constraints; the live DDL was checked by hand above.

## Check 6 — downstream consumers

The script writes only the five owned tables. Consumers invalidated by the 2002 change (none rebuilt by the
script, all must be revalidated before publication):

- Identity-build copies (`build_candidate_identity.py`, `if_exists=replace`): `candidate_aliases`,
  `candidate_party_affiliations`, `candidate_party_switches`, `candidate_alias_match_candidates`; views
  `dim_person`/`bridge_person_alias` update automatically (two new person ids appear).
- Compatibility exports (`build_canonical_cmo_features.py`): `canonical_cmo_features.csv`,
  `canonical_cmo_candidates.csv`, `historical_cmo_extension.csv`.
- `cmo_v5_*` (`cmo_v5_races.csv`, `cmo_v5_candidates.csv`), `alabama_historical_war_v1`
  (`build_alabama_historical_war_v1.py`), `southern_war_panel_v1` Alabama 2002 rows
  (`build_southern_war_panel_v1.load_alabama_canonical` reads `cmo_v5_*`), `docs/cmo.html`, ideology page and
  the historical WAR pages.
- Also reading 2002 `canonical_candidates` but **not listed in `not_rebuilt`**: `build_1998_2006_context_features.py`
  (`1998_2006_candidate_incumbency.csv`, `1998_2006_cmo_context_features.csv`, `mart_historical_cmo_context_feature_v2`),
  `build_dime_finance_features.py` and `build_multisource_finance_features.py` (candidate/race finance matches
  over all D/R canonical candidates), and the stale Klarner HD27 duplicate in the Southern materialized table.
- Unaffected: `bridge_alabama_canonical_candidate_certified_result` (2018/2022), `build_2026_forecast_dashboard.py`
  (2022 only), `build_1994_*`.

`mart_southern_war_training_with_finance` is a **view**; its dependency closure is
`mart_southern_war_training_no_finance` (view) → `mart_southern_war_outcome` (table, cycles 2016–2024, 4,582 rows),
`mart_southern_war_context_feature` (table) and `mart_southern_race_finance` (table). The first two are
digest-guarded control tables; the third is write-denied by the authorizer. The training frame therefore
cannot change. Reference digest (script `digest_rows` method, `SELECT * ... ORDER BY rowid`) of
`mart_southern_war_training_with_finance` before application: `99aed15cdeebaea9d0b558282db06966885c4fb0ed159d15a89c0441a360e531`
(4,582 rows, cycles 2016–2024); the primary can recompute it after `--apply` to prove the approved v3 run is untouched.

## Findings

| # | Severity | Finding |
|---|---|---|
| F1 | none | All 13 workbook cells, all 12 stored segments, the 4 canonical and 4 materialized before-images, the Klarner HD27 rows, the scratch-rebuild after-images and the dry-run proposal agree with the script. Winner flips follow the builder's max-votes rule. |
| F2 | P2 (record, not a blocker) | After application the Southern materialized table will carry two observation sets for AL/2002/lower/27 (ALCANON rank 5 + Klarner rank 30), breaking its one-set-per-contest resolution invariant for that contest. The final-stage view and the 2016–2024 marts still select ALCANON, and no FK references the Klarner ids, so no outcome is double counted; but the state is only healed by the next `load_southern_legislative_history_warehouse.py` materialization. Smallest repair: add `canonical_southern_legislative_candidate_election (Klarner HD27 set LSET-120E9CDFC994B713A780 remains as a superseded lower-authority duplicate until the history warehouse is re-materialized)` to `not_rebuilt`, or record it in the handoff. |
| F3 | P2 | `not_rebuilt` omits the 1998–2006 context/incumbency outputs, the DIME/FTM finance-feature matches, `historical_cmo_extension.csv` and `candidate_party_switches`/`candidate_alias_match_candidates`. Every listed item is truthful; the omissions should be added to the list (or the handoff) so the qa row's `evidence_json` is a complete stale-dependency ledger. |
| F4 | P3 | `domain=elections_canonical` / `subject_type=canonical_contest` introduce new adjudication vocabulary; acceptable (no CHECK, clearly named) but should be reflected wherever the adjudication vocabulary is documented. |
| F5 | P3 | Operational: the apply path copies a 5.8 GB database and digests 2.18 M `vote_observations` rows three times; budget several minutes and ≥ 6 GB free at the backup path. |
| F6 | P3 (pre-existing, out of scope) | Identity linkage across cycles is per-cycle (e.g. McDaniel has three person ids across 1994/2002/2006; McLaughlin 2006–2014 is `ALPERSON-JEFF-MCLAUGHLIN`), so the new `ALPERSON-MCLAUGHLIN-JEFFREY` will not link to his later rows. This matches the scratch rebuild and the builder's existing behaviour; not introduced by the patch. |

F2–F5 do not affect the correctness or safety of the canonical values written; F2/F3 are documentation
completeness items the primary should fold into `not_rebuilt` (a one-line edit that changes the script hash
recorded in this review) or into the handoff before publication.

## Verdict

Verdict: PASS — the staged 2002 Marshall canonical repair (HD26, HD27, SD9) is supported by the workbook cells and repaired source rows and is safe to apply against RUN-504CE4C4DF904D88A5A40D268F3FCEAB.

Remaining limitations: the tests do not exercise the authorizer denial, trigger refusal, code-hash drift or
materialized before-image paths (they were reviewed by reading); the 5.8 GB warehouse was not hashed; nothing
downstream was rebuilt or revalidated by this review.

