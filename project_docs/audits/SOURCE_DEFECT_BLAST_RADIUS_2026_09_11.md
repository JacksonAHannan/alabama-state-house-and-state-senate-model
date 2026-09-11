# Source-defect blast radius — 2002 Marshall legacy parse and the 2014 ×2 vote_observations blocks

Internal read-only evidence audit for checklist item `warehouse-05`, task
`WAREHOUSE-05-BLAST-RADIUS-20260911`. Scope is two previously-scoped defects in
`vote_observations` / `canonical_candidates`:

1. the legacy `_legacy_2002` parse of the 2002 `MARSHALL` county sheet, and
2. the "every candidate block stored twice" observation for 2014 HD31/HD66/SD30.

**This file is evidence and proposed dispositions only. No disposition is
selected, no warehouse/code/publication change was made.** Every warehouse
connection was `sqlite3.connect('file:...?mode=ro', uri=True)` with
`PRAGMA query_only=ON`; the pre-repair backups were opened the same way. No LLM
call, no `docs/` write, no repository write except this file and its JSON
companion.

- `generated_at_utc` in the JSON companion.
- Warehouse: `data/processed/elections/alabama_elections.sqlite`
  (5,819,064,320 bytes), read-only.
- Backups used read-only: `backups/pre-source-repair-2026-09-05.sqlite` (the
  state the 2026-09-02 identity build consumed),
  `backups/pre-2002-marshall-canonical-2026-09-11.sqlite` (pre-image of today's
  canonical repair).
- Raw sources re-read in memory: 2002 `…PrecinctLevel_0.xls` (xlrd 2.0.2,
  sha256 `9400cfa1…5ed45e`), 2014 `2014General-precinctLevel.zip` (openpyxl
  3.1.5), `openelections/20141104__al__general__precinct.csv`.
- Runtime: `.venv` Python 3.9.6, SQLite 3.35.5.

Relevant runs:

| run | target | when (UTC) | note |
|---|---|---|---|
| `RUN-16A85CF9DA9E4233A55619147EE1ED4C` | `election_source_layer` | 2026-08-16T19:07:59Z | original load; no locator columns |
| `RUN-872E84CE49F34E46A3B71A275F9C8890` | `canonical_candidate_identity` | 2026-09-02T02:51:42Z | last identity build before the Marshall source repair |
| `RUN-40A033B9854141F6B05A76173E66D17B` | `source_quality_repair_2026_09_05` | 2026-09-05T21:25:47Z | re-parsed the 2002 `MARSHALL` sheet (2,950 cells) |
| `RUN-70A750C82BEC43D686E5F4B1FE13461C` | `historical_federal_district_baseline` | 2026-09-11T04:44:47Z | current federal baseline CSV |
| `RUN-DFB1D093D7594AB68A264292050E924D` | `alabama_2002_marshall_canonical_repair` | 2026-09-11T15:43:36Z | today's canonical repair (HD26 A1, HD27 B1, SD9) |

---

# Part 1 — 2002 Marshall legacy-parse blast radius

## 1.1 Raw workbook: `MARSHALL` sheet carries exactly three legislative contests

`MARSHALL` sheet of `2002-GeneralElection-PrecinctLevel_0.xls` (67 county sheets;
header rows 1–3; data rows 4–82; precinct cells in columns H onward because the
sheet duplicates `County`/`Contest Title` so its printed `Total Of Number Votes`
sits in column G, not F). Legislative rows, worksheet-verified:

| sheet row | contest | party | candidate | printed | precinct cells (n) |
|---|---|---|---|---:|---:|
| MARSHALL!r65 | STATE SENATE, DISTRICT 9 | DEM | Mitchem, Hinton | 15,689 | 15,689 (50) |
| MARSHALL!r66 | STATE SENATE, DISTRICT 9 | REP | Edmonds, Doris | 7,557 | 7,557 (50) |
| MARSHALL!r68 | STATE HOUSE OF REPRESENTATIVES, DISTRICT 26 | DEM | McDaniel, Frank | 5,967 | 5,967 (50) |
| MARSHALL!r69 | STATE HOUSE OF REPRESENTATIVES, DISTRICT 26 | REP | Patterson, Jeffrey | 3,861 | 3,861 (50) |
| MARSHALL!r71 | STATE HOUSE OF REPRESENTATIVES, DISTRICT 27 | DEM | McLaughlin, Jeffrey | 7,724 | 7,724 (50) |
| MARSHALL!r72 | STATE HOUSE OF REPRESENTATIVES, DISTRICT 27 | LIB | Driggers, Allen Eugene | 662 | 662 (50) |
| MARSHALL!r73 | STATE HOUSE OF REPRESENTATIVES, DISTRICT 27 | REP | Hawkins, Gerald (Jerry) | 4,789 | 4,789 (50) |

**No other legislative contest appears on the `MARSHALL` sheet.** A 2002 county
sheet prints every contest on that county's ballot, so any district containing
Marshall precincts would have to appear here.

## 1.2 Answer to "other Marshall-touching legislative districts"

**There are none.** Proposed examples resolve outside Marshall:

| district | 2002 counties carrying it (from stored `alabama_sos` rows) | touches Marshall? |
|---|---|---|
| State House 21 | MADISON | no |
| State House 25 | LIMESTONE, MADISON | no |
| State House 28 | ETOWAH | no |
| State Senate 8 | DEKALB, JACKSON, MADISON | no |
| State Senate 10 | CHEROKEE, ETOWAH | no |

Independently, the live warehouse holds `county_key='MARSHALL'` 2002 legislative
rows for exactly three offices: `State House` 26 (100 rows / 50 precincts /
9,828 votes), `State House` 27 (150 / 50 / 13,175), `State Senate` 9
(100 / 50 / 23,246). Nothing else.

**Why the scratch identity diff changed only HD26/HD27/SD9.** The diff
(`artifacts/war/canonical_identity_rebuild_20260911/identity_rebuild_diff.json`)
compares `canonical_candidates`, which is *state legislative only*. Marshall's
only legislative contests are the three above, so the Marshall segment can only
move those three: HD26 (+5,967 D / +3,861 R), SD9 (+15,689 D / +7,557 R), and
HD27 (two new rows). All 20 other Marshall contests on the sheet are statewide,
judicial, BOE, county or federal offices, which `canonical_candidates` does not
carry — they could not appear as "changes" in that diff even though the
2026-09-05 source repair restored them.

## 1.3 The 2002 Marshall contests restored by the repair run

Every 2002 `county_key='MARSHALL'` row in the live warehouse carries
`build_run_id='RUN-40A033B9854141F6B05A76173E66D17B'`, `source_file_id='SRC-9E0F7297AEB976F98688'`,
`authority_rank=1`, 50 precincts each. Twenty-three `(office, district)` groups:

| office | district | rows | precincts | votes | candidates |
|---|---:|---:|---:|---:|---|
| State Senate | 9 | 100 | 50 | 23,246 | Mitchem/Edmonds |
| State House | 26 | 100 | 50 | 9,828 | McDaniel/Patterson |
| State House | 27 | 150 | 50 | 13,175 | McLaughlin/Driggers/Hawkins |
| Governor | — | 150 | 50 | 23,480 | Siegelman/Sophocleus/Riley |
| Lieutenant Governor | — | 150 | 50 | 22,967 | Baxley/Adams/Armistead |
| Attorney General | — | 150 | 50 | 22,577 | Whigham/Myers/Pryor |
| Secretary of State | — | 150 | 50 | 21,833 | Worley/Bodenhausen/Thomas |
| State Treasurer | — | 150 | 50 | 22,002 | Black/Garland/Ivey |
| State Auditor | — | 150 | 50 | 21,304 | Gibson/Reeves/Chapman |
| Commissioner of Ag. & Industries | — | 150 | 50 | 21,562 | Sparks/Hulcher/Alley |
| PUBLIC SERVICE COMMISSION, PLACE #1 | — | 150 | 50 | 21,704 | Cook/Clark/Martin |
| PUBLIC SERVICE COMMISSION, PLACE #2 | — | 150 | 50 | 21,895 | Pierce/Abernathy/Wallace |
| ASSOCIATE JUSTICE, SUPREME COURT | — | 150 | 50 | 22,520 | Anderson/Bear/See |
| COURT OF CIVIL APPEALS | — | 100 | 50 | 21,260 | Toles/Thompson |
| COURT OF CRIMINAL APPEALS, PLACE #1 | — | 150 | 50 | 20,914 | Funderburk/Allen/McMillan |
| COURT OF CRIMINAL APPEALS, PLACE #2 | — | 100 | 50 | 20,435 | Cauthen/Baschab |
| STATE BOE, DISTRICT 6 | 6 | 100 | 50 | 18,264 | Vines/Byers |
| U.S. Senate | — | 150 | 50 | 23,352 | Parker/Allen/Sessions |
| U.S. House | 4 | 100 | 50 | 20,463 | McLendon/Aderholt |
| DISTRICT COURT, MARSHALL CO., PLACE #1 | — | 50 | 50 | 17,197 | Hawk |
| STATEWIDE AMENDMENT #1 | — | 100 | 50 | 19,580 | YES/NO |
| STATEWIDE AMENDMENT #2 | — | 100 | 50 | 18,040 | YES/NO |
| STATEWIDE AMENDMENT #3 | — | 100 | 50 | 17,630 | YES/NO |

(`TOTAL BALLOTS CAST`, 50 rows / 23,808, is also present as the source's printed
summary row and is not a contest.)

**20 non-legislative contests + 3 legislative = 23.** Before the 2026-09-05
repair all 23 were stored under `office='MARSHALL'`, `district IS NULL` and were
therefore unusable by every office-keyed consumer.

## 1.4 Do legacy `office='MARSHALL'` rows still exist? (double-count check)

| check | live warehouse | pre-repair backup (2026-09-05) |
|---|---:|---:|
| 2002 rows with `upper(office)='MARSHALL'` | **0** | **4,029** |
| 2002 Marshall rows, all offices | 2,950 | 4,029 (all `office='MARSHALL'`) |
| of those, `district IS NULL` | 0 | 4,029 |
| `authority_rank` values | 1 only | 1 only |

- The repair replaced the scoped rows (`DELETE FROM vote_observations WHERE
  <2002/MARSHALL/office='MARSHALL'>` then insert; evidence row `WQA-01-02`), so
  **the two sets never coexist and no SUM over 2002 Marshall double counts.**
- `authority_rank` of both the legacy and the repaired rows was 1. This matters:
  `canonical_vote_observations` is
  `authority_rank = MIN(authority_rank) per (year, county_key)` — it de-duplicates
  *across sources by rank*, not by natural key within a rank. Had the legacy rows
  survived at rank 1 beside the repaired rank-1 rows, **both** would satisfy the
  view and a canonical-layer SUM would double count. The repair's DELETE is what
  prevents that today; the view itself has no same-rank guard.
- 2002 has no `openelections` rows (OpenElections cycles loaded are 2012/2014/
  2016/2018/2020), so the only 2002 rank-1 rows are `alabama_sos`.
- The pre-repair 2002 office census shows `MARSHALL` was the **only** misparsed
  office that year: 2002 `State House` 20,886 / `State Senate` 12,361 and every
  other office carried its correct label; `district IS NULL` legislative rows: 0.
  So the layout defect was confined to the single `MARSHALL` sheet.

## 1.5 Canonical layer before vs after today's repair

| contest | pre-image (`pre-2002-marshall-canonical-2026-09-11.sqlite`) | live (after `RUN-DFB1D093D…`) |
|---|---|---|
| HD26 D / R | 1,102 / 598 (DeKalb segment only) | 7,069 / 4,459 (DeKalb + Marshall) |
| HD27 D / R | **absent (0 rows)** | 7,724 / 4,789 (new) |
| SD9 D / R | 8,914 / 9,438 (Blount + Madison only) | 24,603 / 16,995 (adds Marshall) |

So before today's repair the canonical layer **did** omit the Marshall segment
for HD26 and SD9, and omitted HD27 entirely. That is exactly the 4 changed vote
values + 2 added rows in `identity_rebuild_diff.json`; no other canonical row
moved on account of 2002.

## 1.6 Did statewide/federal consumers miss the Marshall segment?

Consumer routing (read from source):

| consumer | rows read for 2002 Marshall | affected by today's canonical repair? |
|---|---|---|
| `build_candidate_identity.py` → `canonical_candidates` | `vote_observations` `office IN ('State House','State Senate') AND district IS NOT NULL` | yes (that is today's repair) |
| `build_canonical_cmo_features.py` (Governor/AG office baseline) | `vote_observations` `source='alabama_sos' AND office IN ('Governor','Attorney General')` | no |
| `build_historical_federal_baselines.py` | `vote_observations` `source='alabama_sos'` for 1994…2022, office titles re-parsed by `federal_office()` | no |
| `build_canonical_geographic_weights.py`, `build_1994_cmo_baseline.py`, `build_presidential_district_features.py`, `build_1998_2006_context_features.py`, `build_alabama_race_ei.py` (`authority_rank=1`), `build_war_story_page.py` (`authority_rank=1`) | `source='alabama_sos'` (or rank 1) | no |

- **Canonical (state legislative): yes**, missing until today's repair (1.5).
- **Governor/AG and federal: not missing as of today's repair, but they were
  missing between 2026-08-16 and 2026-09-05.** They read `vote_observations`
  directly and filter on the *correct* office string, so the pre-repair
  `office='MARSHALL'` rows were outside their predicate — the Marshall precincts
  were absent from their observation set entirely, not merely fallback-allocated.
  The 2026-09-05 source repair fixed that three days before today's canonical
  change. Today's `RUN-DFB1D093D…` writes only `canonical_candidates` /
  `canonical_southern_legislative_candidate_election` / adjudication tables and
  does not touch `vote_observations`.

**Verification that the 2002 Governor/AG baseline does consume Marshall
precincts.** Re-running the builder's allocation slice offline (observations =
SOS 2002 Governor/AG D/R; activity = SOS 2002 `State House`/`State Senate` with
`district IS NOT NULL`; `allocation_weight = district_activity / precinct_activity`):

| chamber | Marshall precincts matched (direct) | unmatched | allocated Governor votes | allocated AG votes |
|---|---:|---:|---:|---:|
| house → districts 26 + 27 | 50 / 50 | 0 | 9,076.8 (HD26) + 12,566.2 (HD27) | 8,715.4 + 11,988.6 |
| senate → district 9 | 50 / 50 | 0 | 22,934.0 | 21,963.0 |

The current `canonical_cmo_district_office_baselines.csv` (mtime 2026-09-11
15:47:32Z, produced after the canonical repair) carries 2002 Governor/AG rows for
HD26/HD27/SD9. Its Marshall share is material: Marshall supplies ~9,077 of
HD26's 11,494 Governor D+R baseline votes. `baseline_allocation_method` is
labelled `county_population_fallback` (the builder labels a group by *any*
fallback row), but `baseline_fallback_share` is only 0.0510 (HD26) / 0.0541
(HD27) / 0.0 (SD9) — i.e. ~95–100% of those rows came from the direct
activity match, including all 50 Marshall precincts.

The current `historical_federal_district_baselines.csv` (mtime 2026-09-11
04:44:47Z) carries 2002 rows for HD26 (`federal_index_margin=-39.648808`,
`us_senate_two_party_votes=11,299.2`, coverage 0.563), HD27 (`5.554516`,
13,241.2, 0.571) and SD9 (`0.207234`, 41,981.0, 0.740). The HD26 value is the
`selected_ticket_margin=-39.648808` used by the historical WAR row, so the
Marshall restoration propagates into the ticket baseline comparison as well.

## 1.7 Part 1 — what is NOT established

- Whether any non-Marshall 2002 sheet has a *different*, still-undetected layout
  defect. The office census (1.4) found `MARSHALL` to be the only 2002 office
  label that is a county name, and 2002 has no `district IS NULL` legislative
  rows; that is strong but not an exhaustive cell-level re-verification of all
  67 sheets.
- The exact downstream numeric delta of the pre-2026-09-05 omission (no
  pre-repair baseline CSV was preserved; the 2026-08-26 exports were later
  overwritten).
- Whether the `canonical_vote_observations` per-`(year,county)` rank rule is
  intended to drop same-rank duplicates, or whether the natural-key uniqueness
  it implies is tested anywhere.

---

# Part 2 — 2014 "×2 block duplication"

## 2.1 Correction of the packet's mechanism

The packet (Case C) described the observed 2× totals for HD31/HD66/SD30 as
"legacy ×2 duplication … the legacy 2014 ingest read each file through more than
one code path (or more than once)". The source column resolves it differently:

```
rowid 1311012  source='alabama_sos'   ELMORE TALLAWEEKA BAPT. State House 31 HOLMES D 701
rowid 1353989  source='openelections' ELMORE TALLAWEEKA BAPT. State House 31 HOLMES D 701
```

The two rows are **different registered sources**, not a double read of one file:

- `alabama_sos` — `2014General-precinctLevel.zip`, `SRC-EB647D3AA2049AD37AD6`,
  `authoritative_scope='official_vote_counts'`, `authority_rank=1`;
- `openelections` — `20141104__al__general__precinct.csv`,
  `SRC-F88A7698F08358C9E20B`, `authoritative_scope='identity_enrichment'`,
  `authority_rank=2`.

This is by design: `build_election_database.py` stores *all* providers in
`vote_observations` ("conflicting providers coexist") and exposes
`canonical_vote_observations` as `MIN(authority_rank) per (year, county_key)`
to select SOS over OpenElections. For 2014 every county has rank-1 SOS rows, so
`canonical_vote_observations` for 2014 contains **SOS only** (110,189 rows;
verified with the equivalent `MIN(rank) per (year,county)` join).

The packet's "MORGAN"/"MORGAN IND" and "Holmes"/"Mike Holmes" key splits are the
same two-source effect: SOS stores the single-token label (`MORGAN IND`, `HOLMES`)
and OpenElections the other (`MORGAN`, `HOLMES`), each once.

## 2.2 Raw member vs stored rows (per county sheet)

| check | result |
|---|---|
| Re-parse raw SOS ZIP via `sos_precinct.load_sos_year(2014)` | 110,189 rows, 67 counties |
| Stored `source='alabama_sos'` rows | 110,189 |
| Groups `(county, office, district, candidate)`, raw vs stored sum | 717 groups, **0 mismatched sums** |
| Raw OE CSV via `oe_normalize.load_oe` | 74,525 rows |
| Stored `source='openelections'` rows | 74,525, per-precinct values equal |

So each stored source is exactly one copy of its parsed member. The OE CSV's
per-county `Total` rows (e.g. Elmore Governor `Total` Bentley 15,215) are removed
by `load_oe`'s `SUMMARY_ROW_RE`; the remaining 30 precinct rows carry the true
values that match SOS cell-for-cell.

## 2.3 Within-source duplication: none

Grouping 2014 `vote_observations` by
`(source, county_key, precinct_key, office, district, candidate, party)` and by
the `candidate_key`/`party_norm` variant, `HAVING COUNT(*)>1` returns **zero
groups** under either key. The 2× totals are entirely cross-source.

## 2.4 Cross-source overlap

Row-level, at the exact natural key
`(county_key, precinct_key, office, district, candidate_key, party_norm)`:
22,619 of the 74,525 OpenElections keys match an SOS key, and **all 22,619 have
identical vote sums** (5,887,393 OE votes). That count understates the overlap
because candidate-key and office-label spelling differ between providers.

Contest-level (aggregating D/R over candidates, key = `county × office ×
district`, `district=-1` for statewide; office strings must match between
providers, which holds for statewide and legislative races):

| bucket | contests |
|---|---:|
| contest groups total | 1,968 |
| SOS only | 1,299 |
| OpenElections only | 137 |
| both sources | **532** |
| both, identical D/R sum | **511** (96.1% of both) |
| both, different D/R sum | 21 |

Per office (SOS-covered groups / both / identical):

| office | SOS groups | both | identical |
|---|---:|---:|---:|
| State House | 208 | 188 | 187 |
| State Senate | 120 | 112 | 111 |
| Governor | 67 | 67 | 49 |
| Attorney General | 67 | 49 | 49 |
| Lieutenant Governor | 48 | 48 | 48 |
| State Treasurer | 67 | 67 | 66 |
| U.S. Senate | 1 | 1 | 1 |
| Secretary of State / State Auditor | 67 / 67 | 0 / 0 | 0 / 0 |

So for the seven offices whose labels agree between providers, **511 of 578
SOS-covered contests (88.4%) are stored exactly twice** (stored D/R sum = 2 ×
SOS). The remaining 67 are SOS-only because OpenElections lacks the contest in
that county (see 2.6), not because of any intra-source duplication.

## 2.5 Which counties

- **Legislative:** 66 counties have both-source legislative contests. 298 of 300
  are exactly doubled; the only exceptions are **CLAY HD33** (SOS 795 vs OE 678)
  and **CLAY SD12** (SOS 1,858 vs OE 1,611). Clay's OE member has one fewer
  precinct (HD33: 9 vs 10; SD12: 11 vs 12; Treasurer 17 vs 18), so OE is a
  genuinely smaller read of Clay, not a duplicate.
- **Jefferson** has **no** OpenElections `State House`/`State Senate` rows
  (OE covers 66 counties there), so its 29 legislative county-contests are
  SOS-only and are *not* doubled. (The packet already notes
  `build_war_database.py` special-cases 2014 Jefferson.)
- **Statewide Governor:** 49 of 67 counties doubled; the other **18** are the
  matrix-layout counties where SOS "Governor" also contains the Lieutenant
  Governor candidates (2.7). Those 18 are the same counties where OpenElections
  has no `Attorney General` rows: BIBB, BLOUNT, BUTLER, CALHOUN, CHILTON, CLAY,
  COOSA, DALLAS, DEKALB, ELMORE, ESCAMBIA, GENEVA, GREENE, LAMAR, MACON,
  PICKENS, WALKER, WILCOX.
- Federal: SOS `U.S. House`/`US Rep, Dist…` labels differ from OE `U.S. House`,
  so the contest-level match above does not join them; `federal_office()` in the
  federal baseline normalizes both.

## 2.6 Consumers of 2014 `vote_observations`

| consumer | predicate | exposure to the cross-source overlap |
|---|---|---|
| `build_canonical_geographic_weights.py` | `source='alabama_sos' and year in (2010,2014,2018,2022)` | **none** (SOS only) |
| `build_historical_federal_baselines.py` | `source='alabama_sos' and year in (…)` | **none** |
| `build_canonical_cmo_features.py` | `source='alabama_sos'` (Governor/AG and legislative) | **none** |
| `build_1994_cmo_baseline.py` | `source='alabama_sos'` | none |
| `build_presidential_district_features.py` | `source='alabama_sos'` | none |
| `build_1998_2006_context_features.py` (`legislative_weights`, 2004 President) | `source='alabama_sos'` | none |
| `build_alabama_race_ei.py` | `authority_rank = 1` | none |
| `build_war_story_page.py` | `authority_rank = 1` | none |
| `build_adjacent_precinct_alias_graph.py`, `build_historical_precinct_adjudication_queue.py`, `build_same_year_primary_precinct_aliases.py`, `run_top_ticket_experiments.py` | `source='alabama_sos'` | none |
| `build_candidate_identity.py` | no source filter, but groups by `source` in the alias aggregation | both sourced, kept separate — safe by construction |
| `build_precinct_identity.py` | no source filter; `match_sources(nodes, totals, 'alabama_sos', 'openelections')` | deliberate two-source identity linking |
| `analyze_canonical_baselines.py` | no source filter, no rank filter, six statewide offices | **would double count 2014** if run over 2014; analysis script only, not in `CANONICAL_PIPELINES.md` |
| `stage/apply_precinct_identity_repair.py` | `SOURCE_SCOPE = source='alabama_sos' AND …` | none |

No product-route consumer reads both 2014 sources together; the only unfiltered
product-adjacent reader is `analyze_canonical_baselines.py`.

## 2.7 Additional 2014 source-layer defect found while enumerating

Not a duplication, but discovered by the same raw-vs-stored pass and material to
any Governor consumer: in the 18 matrix-layout counties the SOS parse stores the
**Lieutenant Governor** candidates under `office='Governor'`.

- Raw `Elmore 2014 General Precinct.xlsx` row 1: `B1='Governor'`,
  `E1='Lt. Governor'`; row 2: `B=Griffith (D)`, `C=Bentley (R )`,
  `D=Write-in`, `E=Fields (D)`, `F=Ivey (R )`, `G=Write-in`.
- `scripts/sos_precinct.py::_office` maps by substring, and its mapping table key
  is `"LIEUTENANT GOVERNOR"`, which does not match the workbook's
  `"LT. GOVERNOR"`. The later `"GOVERNOR"` needle then matches, so
  `_office('LT. GOVERNOR')` returns `('Governor', None)` (verified by direct
  call).
- Effect: in those 18 counties SOS `Governor` D/R includes Fields + Ivey
  (Lt. Governor), and SOS has no `Lieutenant Governor` rows at all. Example
  Elmore: SOS Governor D/R = Bentley 15,215 + Ivey 15,737 + Griffith 5,561 +
  Fields 4,919 = 41,432, while the OpenElections Governor (and the true race) is
  20,776. Statewide, SOS `Lieutenant Governor` covers 48 counties; OpenElections
  covers 66.
- The 17 unequal Governor contests in 2.4 are this defect (the 18th, CLAY, is
  the Clay precinct-count discrepancy). This is a *separate* source-layer defect
  from the ×2 overlap and is out of the task's stated scope; recorded here as an
  out-of-scope finding (see also §Out-of-scope).

## 2.8 Hypothetical impact if the duplication were consumed

Uniform duplication of an entire contest scales every candidate block by 2:

| measure | effect of uniform doubling | observed effect today |
|---|---|---|
| absolute vote totals (e.g. `*_two_party_votes`) | ×2 | none (SOS-filtered consumers) |
| margins / shares (D−R over D+R) | unchanged (ratio) | none |
| allocation weight `district_activity / precinct_activity` | unchanged (both numerator and denominator ×2) | none |
| `federal_contested_coverage` (= contested / all major) | unchanged | none |
| candidate identity/alias counts | would change if aggregated without `source` | `build_candidate_identity.py` groups by source → unchanged |

So **ratio-based consumers are structurally immune to a uniform ×2 while totals
are not**, and the duplication is *not* perfectly uniform (Clay precinct counts,
the Governor/Lt-Governor merge), which is why a consumer-side `source` filter is
the correct guard rather than arithmetic cancellation. In practice every 2014
product consumer already filters `source='alabama_sos'`, so the observed
downstream effect of the overlap is nil.

## 2.9 Part 2 — what is NOT established

- Exact pre-image of the 2014 `canonical_precinct_district_weights.csv` /
  federal baselines before 2026-09-05 (no preserved copy), so the numeric effect
  of the historical Marshall omission is not measured, only its mechanism.
- Whether `analyze_canonical_baselines.py` was ever run on 2014 or is a dead
  analysis path.
- Whether the Clay 2014 precinct-count difference and the Clay OE/US reporting
  discrepancy share a cause.
- Whether the `LT. GOVERNOR` mapping defect also affects other cycles that use
  `_county_matrix_sheets` with a `Lt. Governor` header (2006/2008/2010/2012/2016
  were not re-parsed here; only 2014 was in scope).
- Governmental authority of the OpenElections 2014 file beyond its registered
  `identity_enrichment` scope.

---

# Part 3 — Proposed dispositions (not selected)

## 3.1 2002 Marshall legacy rows

The legacy rows themselves are already gone (1.4); the live question is
guarding the pattern and finishing the downstream chain.

**M1 — No further source-layer action; treat `WQA-01-02` + this audit as the
record.**
Consequence: `vote_observations` preserves no `office='MARSHALL'` before-image
(the pre-repair backup is the only copy on disk). Consumers continue to be
correct. Evidence needed: confirmation the backup is retained as the before-image.

**M2 — Add a uniqueness/parse guard so a re-run of the 2026-08-16 ingest cannot
silently re-introduce `office='MARSHALL'`.**
Consequence: `build_election_database.py` / `sos_precinct.py` changes; no numeric
change to current data; a re-run of `election_source_layer` (currently
non-idempotent with the post-repair adapters and the locator columns) must be
reviewed separately before use. Consumers to rebuild: none if no data changes.

**M3 — Build the remaining post-Marshall compat chain now.** The canonical
repair invalidated `canonical_cmo_features.csv`, `canonical_cmo_candidates.csv`,
`canonical_cmo_district_office_baselines.csv`, `historical_cmo_extension.csv`,
`cmo_v5_*`, `alabama_historical_war_v1`, the Alabama 2002 rows of
`southern_war_panel_v1`, the ideology page and `docs/cmo.html`. The first four
and `cmo_v5_races.csv` carry mtimes of 2026-09-11 15:47Z (post-repair); the
historical WAR export and the published pages are the open question.
Consequence: an unrebuilt historical export keeps HD26/SD9/HD27 wrong at the
published grain. Evidence needed: the actual mtime/run of
`alabama_historical_war_v1/race_war.csv` and the page artifacts.

## 3.2 2014 cross-source ×2

**D1 — Leave `vote_observations` as-is; document the cross-source semantics and
the Clay/Governor exceptions.**
Rationale: the layer's contract is "preserve all sources"; the overlap is not an
accident, and `canonical_vote_observations` already drops OE for 2014.
Consequence: no numeric change; add a consumer warning that `vote_observations`
is not unique per natural key across providers and that `source`/`authority_rank`
must be filtered. Consumers to rebuild: none.

**D2 — Repair the source layer by deleting/flagging the 2014 OpenElections
overlap.**
Consequence: loses the registered `identity_enrichment` rows for 2014
(`build_precinct_identity.py` consumes them); `qa_vote_observation_quality`
census changes; must be a guarded adjudication with before-image and reviewer
status. Consumers to rebuild: precinct identity products, any 2014 alias graph.
Not recommended for the duplicated subset alone, and it does not fix Clay.

**D3 — Consumer-side `distinct`/source filtering.**
Change `analyze_canonical_baselines.py` to the `source='alabama_sos'` (or
`authority_rank=1`) predicate its peers already use. Consequence: no
`vote_observations` change; the analysis output changes for 2014–2020.
Evidence needed: confirm the script's consumers and whether any published number
derives from it.

**D4 — Separate: repair `_office('LT. GOVERNOR')` and re-load the 2014 SOS rows.**
Consequence: changes `vote_observations` for 18 counties (Governor totals drop to
the true race; `Lieutenant Governor` gains 18 counties); a guarded source repair
with before-image, then every 2014 statewide consumer and any 2014–2022
same-cycle baseline rebuild. This is a distinct defect from the ×2 and should be
authorized separately.

---

# Query log (representative, all read-only)

```sql
-- 2002 Marshall census
SELECT office,district,COUNT(*),SUM(votes),MIN(authority_rank),MAX(authority_rank),
       group_concat(DISTINCT build_run_id)
FROM vote_observations WHERE year=2002 AND upper(county_key)='MARSHALL' GROUP BY 1,2;
SELECT COUNT(*) FROM vote_observations WHERE year=2002 AND upper(office)='MARSHALL';   -- 0

-- pre-repair backup
SELECT COUNT(*) FROM vote_observations WHERE year=2002 AND upper(county_key)='MARSHALL';   -- 4029
SELECT authority_rank,COUNT(*) FROM vote_observations
WHERE year=2002 AND upper(office)='MARSHALL' GROUP BY 1;                                   -- 1 -> 4029
SELECT office,COUNT(*) FROM vote_observations WHERE year=2002 GROUP BY 1 ORDER BY 2 DESC;

-- pre-image canonical
SELECT canonical_candidate_id,canonical_votes,winner FROM canonical_candidates
WHERE year=2002 AND ((chamber='house' AND district IN (26,27)) OR (chamber='senate' AND district=9));

-- 2014 within-source duplicates
SELECT source,COUNT(*) FROM (SELECT source,COUNT(*) n FROM vote_observations WHERE year=2014
 GROUP BY source,county_key,precinct_key,office,district,candidate,party HAVING COUNT(*)>1)
GROUP BY source;                                                                            -- no rows

-- 2014 source totals
SELECT source,COUNT(*),SUM(votes) FROM vote_observations WHERE year=2014 GROUP BY 1;

-- canonical-equivalent view for 2014
WITH m AS (SELECT county_key,MIN(authority_rank) r FROM vote_observations WHERE year=2014 GROUP BY county_key)
SELECT v.source,COUNT(*) FROM vote_observations v JOIN m ON m.county_key=v.county_key AND m.r=v.authority_rank
WHERE v.year=2014 GROUP BY 1;                                                               -- alabama_sos 110189
```

Raw reads: `sos_precinct.load_sos_year(Path('.'), 2014)` → 110,189 rows / 67
counties; `oe_normalize.load_oe(2014 csv)` → 74,525 rows; xlrd read of the
`MARSHALL` sheet; openpyxl read of `Elmore 2014 General Precinct.xlsx`.

---

# Out-of-scope findings (evidence, not acted on)

1. **2014 Lt. Governor merged into Governor** in 18 matrix counties via
   `sos_precinct._office('LT. GOVERNOR') → 'Governor'` (§2.7). Affects any
   consumer that reads SOS `office='Governor'` for 2014; the CMO office baseline
   replaces 2014–2022 with `district_baseline_office.csv`, so the exposure there
   is indirect, but `analyze_canonical_baselines.py` and any ad-hoc query are
   exposed.
2. **Clay 2014 OE coverage** is one precinct short of SOS for HD33/SD12 (and one
   row short for Treasurer); values differ, not just duplication.
3. **OpenElections 2014 lacks Jefferson legislative rows**, and only 49 counties
   for Attorney General / U.S. Senate, 64 for U.S. House.
4. **`canonical_vote_observations` de-duplicates by rank, not natural key**
   (§1.4): if two providers ever share a rank for a `(year,county)`, the view
   includes both. No test of same-rank uniqueness was found.
5. **`qa_vote_observation_quality` groups by `source`**, so it cannot flag a
   cross-source duplicated block as a duplicate; nothing currently alerts on the
   2014 SOS∪OE overlap.
6. **`identity_rebuild_diff.json` is legislative-only**, so it can never show the
   20 non-legislative 2002 Marshall contests restored by the source repair.
