# Alabama 1994 party-label and House 92 district repair — evidence, decisions and dry run

Task contract: `coordination/ALABAMA-1994-PARTY-LABELS-20261004.md`. Status: applied 2026-10-05 UTC and dependents rebuilt (section 8); awaiting independent review of the rebuilt 1994 WAR before any publication. Code, evidence records
and the read-only dry run are described below. `--apply` and the
rebuilds belong to the primary session, which needs owner approval for each prompt.

- Upstream snapshot: warehouse `data/processed/elections/alabama_elections.sqlite`, latest run
  `RUN-DFB1D093D7594AB68A264292050E924D` (the 2002 Marshall repair). The dry run left that run and
  the 211 canonical 1994 rows unchanged.
- Code basis: HEAD `178d6f48` plus the uncommitted working tree, which is preserved.
- Origin: the 1994 finding in [ALABAMA_SEATS_BY_CYCLE_V1.md](ALABAMA_SEATS_BY_CYCLE_V1.md)
  (open review items).

## 0. Independent review and follow-ups (2026-10-04)

An independent reviewer returned **PASS** on the dry run of the repair script (reviewed sha256
`fd0d0d1df8220704ca132362d07b48a72342b31814899623d84d3b2c5a0f3d57`), with findings. The script was
then changed as below. Its current hash is reported in the task hand-off; it must be re-reviewed
or diffed against the reviewed version before `--apply`.

| Finding | Disposition |
|---|---|
| 1. New rows would join surname-only person IDs held by other 1994 people: HD51 F. Rogers joins `ALPERSON-ROGERS` (HD36 R, HD52 D); HD92 B. Martin joins `ALPERSON-MARTIN` (HD27 R, HD40 D). | **Fixed.** A new 1994 person whose name-derived ID is held by a different 1994 contest gets a stable district-qualified `person_id`. The `--` separator cannot occur in a name-derived ID, so the form is `ALPERSON-ROGERS--1994-HOUSE-51`, `ALPERSON-MARTIN--1994-HOUSE-92`, `ALPERSON-HILL--1994-SENATE-11`. The same check found **SD11 Dell Hill**, who would have joined HD41 Mike Hill (`ALPERSON-HILL`). Canonical candidate IDs are unchanged. The cases are recorded in the supersession file (`person_id_before`/`person_id_after`/`person_id_note`). `stage_person_ids` refuses any new person that would share an ID with another 1994 contest, and any qualification that is unjustified or unreviewed. `alabama_candidate_identity.is_stub_person` does not match the new form, and `career_identity` keeps it as is (tested). Pre-existing 1994 surname merges are **not** changed: BLACK (HD3/HD71), CLARK (HD84/HD98), HALL (HD19/HD22), HARPER (HD17 R/HD105 D), JOHNSON (HD33/HD58), KNIGHT (HD40 R/HD77 D), LINDSEY (HD39/SD22), MARTIN (HD27 R/HD40 D), MITCHELL (HD103/SD30), NEWTON (HD53/HD90), PARKER (HD9/HD63), ROGERS (HD36 R/HD52 D), SMITH (HD4/HD42/HD50/SD10 R), THOMAS (HD49 R/HD69 D). |
| 2. The contract clause did not cover a relabel when the repository holds no official summary for the office (the four statewide/federal relabels). | **Fixed.** `DATA_CONTRACTS.md` now permits an owner-approved `adjudicated_reviewed_evidence` relabel in that case and names the evidence used for 1994. |
| 3. `build_1994_context_features.py` could run against the pre-repair warehouse and rebuild context from the stale labels. | **Fixed.** `require_1994_party_repair` refuses unless all of these hold: a validated `alabama_1994_party_label_repair` run exists; all 42 adjudications are approved; no superseded canonical ID remains; no 1994 legislative B-position row is labelled D; no 1994 legislative row lacks a district. A `party_method='ballot_order_with_export_code'` test would not work, because correct 1994 rows keep that inferred method after the repair. Tested with fixtures. |
| 4. The run's `code_commit` records HEAD, but the repair script is untracked; only `application_code_sha256` identifies the version applied. Pin the reviewed version. | **Process control.** `--apply` runs only when the script's sha256 equals the version the independent reviewer accepted after the follow-up diff; the accepted hash is quoted in `--authorized-by`. |

**Owner decisions after the review:**
- **SD31 incumbency.** Terry Ellis (D) is not an incumbent: 1990 SD14 winner Frank Ellis, Jr. (R) is a different person, party and district. Recorded as `ADJ-1994-AL-INC-SD031-ELLIS-NOT-INCUMBENT` in `data/manual/elections/alabama_1994_incumbency_adjudications.csv`, with evidence from the 1990 workbook, Klarner 1990/1994 incumbency flags, the 1994 workbook and roster p.17. `build_1994_context_features.incumbency()` applies it as an explicit override; the surname rule itself is unchanged. The record is stale, and stops the build, if the matcher no longer makes that match.
- **HD1 1994 is excluded from WAR scoring** because its federal baseline still includes Covington (§7). The primary session implements this in the historical WAR builder; this task does not touch that file. Expected 1994 scored races: 66 D-vs-R contests − HD1 = **65**, The exclusion keeps HD1 in the race universe as an observed, unscored row (`scoring_scope = excluded_by_adjudication`; record `EXCL-AL-HISTWAR-1994-HOUSE-1` in `data/manual/elections/alabama_historical_war_exclusions.csv`). The historical files therefore hold 504 races, 503 of them scored.

**Other surname-matcher results, post-repair (simulated from the proposal; reported, not fixed):**
- 73 incumbents after the SD31 override.
- Matches against Klarner's `incumbent_status`:
  - **HD75: Jack Holley (D) is matched to 1990 HD91 winner Jimmy Holley.** Klarner says he is not an incumbent, and the roster says Jimmy Holley of Troy declined to run. This is a cross-person false positive that predates the repair.
  - HD45 Albert Morton (R) and HD48 John Hawkins, Jr. (R) match 1990 winners of the same name recorded as D. These are cross-party but the same person (incumbent party switchers), and Klarner agrees they are incumbents.
  - 14 cross-district matches are redistricting moves that Klarner confirms (Holley excepted).
  - 18 candidates whom Klarner flags as incumbents are not matched. Most have non-unique surnames (BLACK, PARKER, CLARK, SMITH, ROGERS, NEWTON …); some carry ballot-name variants (Senate 32 "Lipsocomb"). These pre-existing false negatives remain.

## 1. What was wrong

The 1994 SOS precinct archive (`94g-prec.zip`, `SRC-E64FFC4299ED54CB2D3A`, sha256 `94512391…55097`)
prints no party. Each county sheet has four header rows: office, district, surname and an export
code (`AHS10`, `BSENAT31`, `AG2` …). The code records a ballot position, not a party.

`scripts/sos_precinct.py::_legacy_1994` inferred party with this rule:
`code.startswith("A") or code.endswith("1") or rank==0 → D`, else `B…/…2/rank==1 → R`.
The identity build (`build_candidate_identity.py`) then summed votes per contest and party. It
names each canonical row after the longest ballot name and embeds the party in
`canonical_candidate_id`. Four defects followed:

| Defect | Mechanism | Contests |
|---|---|---|
| Lone Republican read as Democrat | A lone candidate takes the A code and `rank==0` | HD 10, 20, 41, 44, 45, 47, 74, 94, 100, 102; SD 15, 16, 17 |
| Second-position Republican read as Democrat; both candidates merged into one D row | `endswith("1")` matched the district number in `BHS91`, `BSENAT31` … | HD 1, 11, 21, 51, 91, 101; SD 11, 31 (winner flips in HD91, SD11) |
| Independent or minor-party candidate read as Republican | B position with `rank==1`, or a C code ending in 2 | HD 8, 12, 19, 29, 32, 53, 58, 67, 69, 72, 86, 97, 103; SD 18, 23 |
| District not parsed | Covington prints `House 92`. Hammett and Martin got a NULL district and dropped out of canonical. Phillips (`CHS92`) was matched by surname to House 1, adding 550 votes there, and 51 Covington precincts were allocated to House 1 in the 1994 baseline weights | HD 92, HD 1 |
| SD25 | Montgomery's only column, `Dixion` (`ASENAT25`), was read as D. It was merged with Elmore's unexplained `Anderson` column into "Anderson D 29,440" | SD 25 |

The same rule mislabelled non-legislative source rows. The second candidate was read as D in
U.S. House 1 (Callahan), PSC Place 1 (Helms) and CCA Place 1 (Long). In Chief Justice, the
Republican Hooper is printed first as `SUPJUST2`. Two consequences:

- U.S. House 1 is missing from the 1994 federal baseline (`historical_federal_contest_components.csv`
  has no `us_house_1` row for 1994).
- Published 1994 historical WAR scores 14 contests that are not D-vs-R, including SD25 at WAR
  +120.4, and omits 8 real D-vs-R contests.

## 2. Evidence

| Source | Identity | Use |
|---|---|---|
| Precinct archive | `data/raw/alabama_elections_and_geography/94g-prec.zip`; registered `SRC-E64FFC4299ED54CB2D3A`; URL `…/election-data/2023-06/94g-prec.zip`; license NULL | Source columns and precinct-cell sums |
| Official 1994 legislative workbook | `data/raw/alabama_elections_and_geography/eastateleg94.xls`, sha256 `76a5b08d…a80`; sheets `ALHse.'94` and `ALSen.'94` print `(D)/(R)/(I)/(P)` and county totals. **Not yet registered**; the repair registers it with retrieval time and license NULL. The URL `…/election-data/2017-06/eastateleg94.xls` is taken from `candidate_issue_research_attempts.csv` and the sibling 1986/1990 registrations; it was not re-fetched | Party labels and official county totals |
| Klarner | `SRC-C3ABE0AF40990D35F24C` (DOI 10.7910/DVN/FJOGJB; terms "review required"), warehouse `source_southern_legislative_*` | Matches the official workbook on every candidate's party class and votes (226 candidates, 140 districts), except the party of HD19 Hall and HD41 Hill |
| Pre-election roster | `data/raw/ideology/alabama_1994_archival_sources/alabama_treasured_forests_fall_1994.pdf`, sha256 `adff09d1…2248`. It is a scan: p.18 is the House candidate table with parties and incumbent asterisks; p.17 is Senate narrative. Registered by the repair with NULLs | Tiebreaker for HD19 and HD41; corroborates SD25, SD31 and HD92 |
| Official statewide 1994 returns | `data/raw/historical_statewide_elections/ea*1986-2010.xls`, `Gen 94`/`Gen.94` sheets | Confirm the export-code convention: GOVERNOR/GOV2, LT.GOV1/LTGOV2, AG1/AG2 and STTREAS1/STTREAS2 are D/R; A/B is D/R for Secretary of State and Agriculture Commissioner |
| Adjacent cycles | `eastateleg90.xls Hse.90Gen.!G73` "Mike Hill (R)"; `eastateleg86.xls Hse.86gen.!B120` "Mike Hill (D)"; printed 2002/2006 canonical labels | HD41, HD19 |

Not usable:
- `data/manual/ideology/alabama_1994_candidate_observations.csv` is a header-only ideology
  template, not an election source.
- Shor-McCarty's 1996 serving roster records post-election switches. For example, HD89 Flowers
  ran as a Democrat in 1994 and is listed as a Republican in 1996.
- The Ballotpedia 1994 pages were "page not found".

## 3. Owner decisions (2026-10-04)

1. **HD41 Mike Hill = R.** This goes against the workbook's lone "D"; the roster, the 1990
   official label, Klarner and the 2002 label all say R. Adjudication `ADJ-1994-AL-HD041-HILL-R`.
2. **HD19 = Laura Hall D vs J. Anderson I**, not a D-vs-R contest
   (`ADJ-1994-AL-HD019-HALL-D-ANDERSON-I`).
3. **SD25 = Larry Dixon R, winner.** The contest is not WAR-scored. Elmore's "Anderson" column
   keeps its source rows with an unresolved party (`ADJ-1994-AL-SD025-DIXON-R`).
4. **Scope:**
   - Restore HD92 and move Covington's three columns out of HD1.
   - Retire the Shor 1996 party override in `build_1994_context_features.py`.
   - Relabel the four statewide/federal source-row sets (CD1, Chief Justice, PSC Place 1,
     CCA Place 1) in `vote_observations` only. Federal baselines are **not** rebuilt.
5. **Votes:** canonical votes keep the precinct-cell-sum rule (Marshall 2002 precedent). Each
   difference from the official county totals is recorded per adjudication.

## 4. Changes in this task (no warehouse write)

| File | Change |
|---|---|
| `scripts/sos_precinct.py` | `_party_1994`: explicit statewide codes (`STATEWIDE_1994_PARTY_CODES`); A/B positions only when a contest has at least 2 named candidates; a lone, C-position or unknown position gets `party=""` and `party_method=unresolved_ballot_position`. `_office` parses `State Representative, House NN`. |
| `scripts/tests/test_sos_precinct.py` | 4 tests: lone and C positions, the district-ending-in-1 case, statewide codes, Covington House 92 |
| `scripts/repair_alabama_1994_party_labels.py` | Scoped repair (§5) |
| `scripts/tests/test_repair_alabama_1994_party_labels.py` | 8 fixture tests (never the real warehouse): dry run, apply, idempotence, before-image refusal, snapshot/backup/authorization, record tampering and re-keyed manual references, rows outside scope unchanged, district-qualified person IDs (not stubs, not folded by `career_identity`), refusal of a person-ID collision |
| `scripts/build_1994_context_features.py` | `incumbency()` takes party from the canonical label (`+canonical_1994_ballot_label`). The Shor comparison is now `shor_1996_party_disagreements()`, a printed review diagnostic. `incumbency()` applies the owner-approved records in `alabama_1994_incumbency_adjudications.csv` (stale records stop the build). `main()` first calls `require_1994_party_repair` and refuses a pre-repair warehouse. |
| `scripts/tests/test_1994_context_features.py` | Live test made state-aware (75 incumbents and Sanderford "D" before apply; 73 and "R" after, with the SD31 override); fixture tests for the retired override, the SD31 adjudication (including the stale case) and the pre-repair guard (five refusals, one acceptance) |
| `data/manual/elections/alabama_1994_party_label_adjudications.csv` | 42 adjudications, `reviewer_status = owner-approved 2026-10-04`, with locators for the precinct ZIP member/column, workbook cell, Klarner set and roster page, plus precinct-sum vs official totals |
| `data/manual/elections/alabama_1994_candidate_id_supersession.csv` | 49 rows: 13 re-keyed, 4 re-keyed with corrected votes, 5 corrected votes on the same ID, 16 retired, 11 new; `person_id_before`/`person_id_after`/`person_id_note` record the three district-qualified person IDs |
| `data/manual/elections/alabama_1994_incumbency_adjudications.csv` | `ADJ-1994-AL-INC-SD031-ELLIS-NOT-INCUMBENT` (owner-approved 2026-10-04) |
| `project_docs/DATA_CONTRACTS.md` | Clause permitting reviewed official-summary party relabels, and reviewed-evidence relabels where no official summary for the office exists |

The adapter fix does not change stored rows. Compared with the stored 1994 rows, the fixed reader
differs on 40,909 party labels (votes and cell grain are identical apart from the adjudicated
Morgan cell):
- 27,000+ non-legislative lone-candidate rows (judges, clerks) are now unresolved where storage
  has an inferred D.
- 564 local B…1 rows are now R where storage has D (State Board of Education District 1 and
  several local judges).

Outside the owner's scope these stored rows stay as they are. A **fresh bootstrap**
(`build_election_database.py`) would leave every 1994 lone candidate without a party, so the
bootstrap identity build would omit uncontested 1994 winners until it adopts these adjudications.

## 5. Dry run against the warehouse (read-only, 2026-10-04)

`& .venv/Scripts/python.exe scripts/repair_alabama_1994_party_labels.py` returned
`State: pending`, exit 0, in about 60 s. The full proposal (every source column and every canonical
row, before and after) was written to a scratch JSON and is reproduced by rerunning the command.

| Item | Count |
|---|---|
| Source selectors / county columns / rows | 45 / 267 / 11,259 (legislative 61 columns, 1,752 rows; statewide/federal 9,507 rows) |
| Covington district corrections | 3 columns, 171 rows (NULL→92, NULL→92, 1→92) |
| Contests rewritten in canonical and in the `ALCANON-1994` materialized sets | 38; rows 54 → 49 (1994 canonical total 211 → 206) |
| Adjudications / source registrations | 42 / 2 |
| Corrected-source recomputation of the 38 contests with the identity-build rule | matches the reviewed after-images exactly |
| Manual files referencing re-keyed IDs | none, so no manual-file rewrite is needed |
| New people / district-qualified person IDs | 11 / 3 (HD51 Rogers, HD92 Martin, SD11 Hill); the after-review rerun matches the first run on every other count |
| Manual files referencing retired IDs | finance archival requests 16; ideology research attempts 14, exclusions 7, aliases 2, findings 1, quality flags 1 (left as historical references and explained in the supersession record) |

1994 seats won (canonical winners), before → after:
- House: 86 D / 18 R → **74 D / 31 R**
- Senate: 29 D / 6 R → **23 D / 12 R**

The "before" counts include the 19 conflicting districts. The "after" counts equal Klarner. The
seats-by-cycle rebuild should then show no 1994 unknowns.

1994 D-vs-R contests (the historical WAR universe): **72 → 66**.
- Enter: HD 11, 21, 51, 91, 92, 101; SD 11, 31.
- Leave: HD 8, 19, 29, 53, 58, 67, 69, 72, 86, 97, 103; SD 18, 23, 25.
- Vote changes in contests that stay: HD1 R 4,946 → 4,396; HD12 R Bowling 6,564 → Hollis 3,551;
  HD32 R Montgomery 2,241 → Bradford 1,452.
- Historical race total: 510 → **504** D-vs-R races, or 503 scored after the owner's HD1 exclusion (§0). `EXPECTED_RACES` and the race-count tests must change.

Precinct-cell sums vs official county totals, recorded per adjudication:
- Zero difference for most contests.
- Small differences: HD47 −1; SD16 −24 (Shelby); SD11 +27/+129 (Elmore calculated vs reported);
  SD25 −129 (Elmore).
- Wilcox is absent from the precinct archive for HD69 and SD23. These contests leave the D/R
  universe.

## 6. Ordered commands for the primary session

Before applying:
- Confirm the latest run is still `RUN-DFB1D093D7594AB68A264292050E924D`.
- Confirm about 6 GB of free disk for the backup.
- The independent review returned PASS on 2026-10-04 (§0). Confirm that the reviewer accepts the follow-up
  changes (person IDs, guard, SD31 override, contract sentence) against the reviewed hash.

```powershell
& .venv/Scripts/python.exe scripts/repair_alabama_1994_party_labels.py
& .venv/Scripts/python.exe scripts/repair_alabama_1994_party_labels.py --apply `
  --expected-run RUN-DFB1D093D7594AB68A264292050E924D `
  --backup data/processed/elections/backups/pre-1994-party-labels-2026-10-04.sqlite `
  --authorized-by "owner decisions 2026-10-04 (ALABAMA-1994-PARTY-LABELS-20261004); independent review PASS 2026-10-04 <record>"
& .venv/Scripts/python.exe scripts/repair_alabama_1994_party_labels.py   # expect warehouse_status unchanged
```

Rebuild, one heavy step at a time (each step marked W writes the warehouse):
1. `scripts/build_1994_cmo_baseline.py` (W) — fixes the Covington → House 1 weights and adds House 92.
2. `scripts/build_1994_context_features.py` (W, heavy) — refuses until the repair is applied; party now comes from canonical, with the SD31 incumbency override; it reads
   step 1's weights.
3. `scripts/build_canonical_cmo_features.py` — then check that rows outside 1994 are byte-identical.
4. `scripts/rebuild_cmo_candidate_quality_v5.py`.
5. Update `EXPECTED_RACES` (510 → 504 rows; the HD1 exclusion withholds one score but keeps the row) in `scripts/build_alabama_historical_war_v1.py` and the
   counts in `test_cmo_candidate_quality_v5.py` and `test_alabama_historical_war_v1.py`.
6. `scripts/build_alabama_historical_war_v1.py`, then
   `pytest -p no:cacheprovider scripts/tests/test_alabama_historical_war_v1.py scripts/tests/test_cmo_candidate_quality_v5.py scripts/tests/test_1994_context_features.py`.
7. `scripts/build_alabama_career_war.py`.
8. `scripts/build_democratic_caucuses_v1.py`, then `scripts/build_democratic_caucus_page.py`.
9. `scripts/build_war_story_page.py --artifact-only`.
10. `scripts/build_alabama_seats_by_cycle.py`, then `pytest scripts/tests/test_alabama_seats_by_cycle.py`.

Do not run:
- `build_candidate_identity.py` — it would revert the certified and Marshall repairs, and its rule
  would rename SD25 "Dixion".
- `build_historical_federal_baselines.py` (owner decision).
- The Southern chain, `build_alabama_war_v1.py`, or anything that writes `docs/`.

Rollback: restore the backup.

## 7. Stale artifacts and remaining risks

**Stale until rebuilt or reviewed:**
- Identity snapshots: `candidate_aliases`, `candidate_alias_match_candidates`,
  `candidate_party_affiliations` and `candidate_party_switches`. The switches table holds false
  1994→1998 switches such as Haney, Sanderford, Waggoner and Turner.
- `mart_historical_*` 1994 tables; `mart_candidate_resources` 1994 rows.
- `data/raw/sos_normalized/1994_general_precinct.csv`: stale adapter output, left under raw.
- `canonical_cmo_*` exports, `cmo_v5_*`, historical and career WAR, caucuses, seats by cycle.
- Derived ideology/finance exports that copy 1994 IDs, for example
  `candidate_ideology_full_universe.csv`, `candidate_legislator_identity_crosswalk.csv` and
  `democratic_caucuses_v1/member_cycles.csv`.
- The 1994 counts in `ALABAMA_BASELINE_PLAN_CERTIFICATION_2026_09_11.md` (54/18 races).
- The Klarner House 92 set beside the new ALCANON set, until rematerialization.
- Published `docs/cmo.html` keeps the old 1994 rows until republication is authorized.

**Risks needing an owner or reviewer decision:**
- **HD1 1994 federal baseline stays contaminated.** Because the federal baselines are not rebuilt,
  HD1 still includes Covington's U.S. House 2 votes (8,287 of 19,855 two-party votes; index
  −20.5 against about +3 without them). HD1 is WAR-scored on `same_cycle_federal`. **Owner
  decision 2026-10-04: exclude HD1 1994 from WAR scoring** (implemented by the primary session in
  the historical WAR builder). No scoped tool exists for a 1994-only federal rebuild, and a full
  rebuild drifts the 2018/2022 baselines
  (`ALABAMA_WAR_DEPENDENCY_REBUILD_2026_09_10.md`). U.S. House 1 also stays absent from that
  baseline, and House 92 has no federal row (it uses the state fallback).
- **Surname incumbency matcher.** The SD31 Ellis false match is resolved by an owner
  adjudication (§0). Still open:
  - HD75 Jack Holley is matched to 1990 HD91 Jimmy Holley, a cross-person false positive that
    predates the repair.
  - 18 incumbents that Klarner flags are not matched (§0).
  The matcher rule is unchanged.
- **Surname-only identities.** 1994 `person_id`s are surname-only, as before. The three new
  people who would have joined another contest's ID now carry district-qualified IDs (§0). Of the
  16 person IDs shared across 1994 contests before the repair, 14 remain; they are listed in §0
  and left unchanged. The other two, ANDERSON and WILLIAMS, resolve because their R rows are
  retired. Dell Hill's (SD11) 1994-1998 career link is not made, because 1998 SD11 keeps
  `ALPERSON-HILL`.
- **Statewide/federal relabels rest on the export-code convention and two-way vote shares.** No
  local party source exists for those offices (medium confidence). Other non-legislative 1994
  mislabels are out of scope: State Board of Education District 1 (`BBOE1`/`CBOE1`), several local
  judges, and lone local candidates stored as D.
- **SD25's candidate set stays unresolved.** Elmore's Anderson column is unexplained.

## 8. Applied and rebuilt (primary session, 2026-10-04 to 2026-10-05 UTC)

### Apply

- **Command.** `repair_alabama_1994_party_labels.py --apply --expected-run RUN-DFB1D093D7594AB68A264292050E924D --backup data/processed/elections/backups/pre-1994-party-labels-2026-10-04.sqlite --authorized-by "owner decisions ...; review PASS; delta review PASS; sha256"`.
- **Script.** The applied script has sha256 `ceab71fd8a88dc249c3b89c06936d1b13e20eb53eba09dc5aa76cb430d44d651`. A delta review accepted it before the apply.
- **Result.**
  - The new validated run is `RUN-9BDA412C4AD042C9A1F048C781525670`.
  - The 5.8 GB backup and its `.application.json` were written.
  - 1994 canonical holds 206 rows.
  - Recorded winners: House 74 D / 31 R, Senate 23 D / 12 R.
  - A dry rerun reports `warehouse_status: unchanged`.
- **Operator error during verification.** The script was invoked twice more with `--apply` and placeholder arguments.
  - The first call (`--expected-run X`) stopped at the snapshot check, which runs before any backup or write.
  - The second carried `--help` and exited while parsing arguments.
  - The warehouse has no build run after `RUN-9BDA412C...`, and no stray backup file exists.

### Rebuild chain (foreground, one step at a time)

1. **`build_1994_cmo_baseline.py`** (warehouse write scoped to 1994).
   - The 56 Covington precinct weights moved from House 1 to House 92.
   - 1994 race features went from 139 to 140 districts and from 72 to 66 contested races.
2. **`build_1994_context_features.py`.**
   - Incumbents went from 75 to 73: the Shor override was retired, and SD31 Ellis is now `owner_adjudicated`.
   - **A pre-existing regression was found and fixed.**
     - The 2026-09 re-parse (commit `f407b9d0`) changed the 1994 weight precinct keys from printed polling-place names to export codes.
     - This builder matches the 1992 presidential workbooks by name, and it had not been rerun since 2026-08-16.
     - On the first rerun, 2,043 of 2,105 presidential precincts went unmatched. The 1994 prior-presidential lag context fell back to county level (mean fallback share 1.0), and 119 of 140 districts changed.
     - `presidential_features()` now maps each county and code to its unique printed name from `vote_observations.precinct`. Two codes print two different names; they keep the code and fall back.
     - After the fix there are 663 exact and 238 fuzzy matches, with a mean fallback share of 0.605 (HEAD: 0.604).
     - Only two districts move by more than 0.5 points: House 1 (Covington removed) and House 32 (independent votes no longer counted as Republican activity).
     - The second run rewrote the warehouse's 1994 context tables.
3. **`build_canonical_cmo_features.py`.** Rows outside 1994 are byte-identical in `canonical_cmo_features.csv`, `canonical_cmo_candidates.csv` and `canonical_cmo_district_office_baselines.csv`.
4. **`rebuild_cmo_candidate_quality_v5.py`.** 504 races and 1,008 candidates.
   - The legacy CMO v5 tournament now runs on 503 races instead of 509, and it re-selected its structural specification: `structural_residual_predetermined_lag_alpha_30` replaces `cycle_centered`. The script itself has not changed since 2026-08-26.
   - Its fitted quality columns therefore change in every cycle. No current product reads them: historical WAR, the WAR page, career WAR, caucuses and the forecast use only vote and baseline fields.
   - These other readers of `cmo_v5_*` are now stale: `analyze_absolute_ideology_rebuild.py`, `audit_alabama_backcast_sensitivity.py`, `build_southern_war_panel_v1.py` and `rebuild_cmo_southern_prior_v6.py`.
5. **`EXPECTED_RACES` changed from 510 to 504.**
   - The owner's HD1 exclusion, `EXCL-AL-HISTWAR-1994-HOUSE-1`, is recorded in `data/manual/elections/alabama_historical_war_exclusions.csv`.
   - `build_alabama_historical_war_v1.apply_exclusions()` applies it as `scoring_scope = excluded_by_adjudication` and leaves WAR empty.
6. **`build_alabama_historical_war_v1.py`** produced run `AL-HIST-WAR-V1-F9D2E0FDE6D38F490402`: 504 races, 503 scored, 407 backcast.
   - Non-1994 WAR is unchanged (maximum difference 0).
   - The 1994 enter and leave lists match section 5 exactly.
   - 7 of the 58 shared 1994 races change:
     - House 1 is excluded.
     - House 12 (23.3 to 52.6) and House 32 (-16.0 to 3.0) move because third-party votes no longer count toward the Republican total.
     - House 35, 85 and 93 and Senate 28 move by 0.4 points or less, from small shifts in split-precinct lag shares.
   - Senate 25's former +120.4 is gone.
   - **First build attempt refused.** The release gate stopped it because `ALABAMA_WAR_FORECAST_FIELD_CONTRACT.md`, a declared input of `alabama_war_v1`, had changed: it carried a forecast-only edit. That text was moved to `project_docs/model/ALABAMA_WAR_FORECAST_GRAPHICS_EXPORTS.md`, and the contract was restored byte-for-byte.
7. **`build_alabama_career_war.py`** was rebuilt.
8. **`build_democratic_caucuses_v1.py`** produced run `AL-DEM-CAUCUS-V1-50163B73E5B72BC8A0F9`.
   - It selected k = 2, with status `descriptive_groupings`, under the labels the owner approved on 2026-10-04.
   - Membership is 55 Progressive and 186 Traditional; at approval it was 52 and 194.
   - Every family profile keeps the sign and rough size described in the approved labels. For example, immigration is +0.75 versus -0.69, and order/justice is -0.17 versus +0.66.
   - `build_democratic_caucus_page.py` then rendered the candidate page.
9. **`build_war_story_page.py --artifact-only`.**
   - House 1 1994 renders through the no-score panel ("WAR withheld by adjudication ...").
   - 1994 now shows 48 scored House races and 17 scored Senate races.
10. **`build_alabama_seats_by_cycle.py`.** 1994 shows House 74 D / 31 R and Senate 23 D / 12 R with no unknown seats, matching Klarner. Six unknown seats remain in other cycles.
11. **Forecast.** The `build_forecast_candidate_history.py` outputs are byte-identical, so the repair does not reach the 2026 forecast.
    - The forecast was rerun so its manifest records the restored contract. It reproduces the original build `08feb2c9669842846d3f`, and every export is byte-identical.
    - The run ledger also keeps a row for the intermediate build `ebf2d7e172b6f0e1a66a`, whose toplines are identical.

### Tests after the rebuild

Each file was run on its own with `-p no:cacheprovider`.

| Test file | Result |
|---|---|
| `test_alabama_historical_war_v1` | 6 passed |
| `test_cmo_candidate_quality_v5` | 7 passed |
| `test_alabama_career_war` | 3 passed |
| `test_1994_context_features` | 12 passed |
| `test_1994_cmo_baseline` | 3 passed |
| `test_alabama_seats_by_cycle` | 16 passed |
| `test_democratic_caucus_page` | 10 passed |
| `test_historical_war_story_page` | 7 passed |
| `test_forecast_dashboard` | 24 passed |
| Repair, adapter and warehouse tests in section 0 | all pass |

- **Tests updated for the post-repair state:**
  - Race counts: 510 to 504, and 413 to 407. Excluded rows must match the exclusion record exactly.
  - The seat-history unknown check is now tied to the seats product's `unknown` statuses, instead of requiring 1994 seats to be unknown.
- **Expected failure:** `test_published_site_consistency::test_publication_exports_match_current_model_outputs`. The published `docs/data` historical WAR files now lag the repaired outputs. That signals republication is pending; the test was not altered.

### Pre-existing items found, not fixed

- Every 1994 race has `incumbency_balance = 0` in historical WAR, because `canonical_cmo_features` carries no 1994 incumbency. The 1994 matcher's output therefore never reaches the backcast.
- The HD75 Holley false incumbency match is unchanged. For the same reason it currently has no effect on WAR.

### Stale until republication

- `docs/cmo.html` and its `docs/data` historical WAR downloads
- the published seats chart and caucus page
- `data/raw/sos_normalized/1994_general_precinct.csv` (derived adapter output, kept unchanged)
- the 1994 plan-certification counts
- the CMO v5 consumers listed in step 4
