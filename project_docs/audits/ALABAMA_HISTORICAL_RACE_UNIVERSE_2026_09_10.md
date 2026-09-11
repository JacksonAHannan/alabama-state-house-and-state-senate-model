# Alabama historical race universe reconciliation — 2026-09-10

Internal execution evidence for checklist items `alabama-02` (reconcile the 509-race /
1,018-candidate-orientation universe against current repaired sources) and
`alabama-03` (revalidate candidate/party identity, incumbency, stage, D/R/other
totals, margins and source-cell lineage for affected years).

This is a **read-only audit**. No data, code, model output or publication file was
changed. The machine-readable companion is
[ALABAMA_HISTORICAL_RACE_UNIVERSE_2026_09_10.json](ALABAMA_HISTORICAL_RACE_UNIVERSE_2026_09_10.json)
(`generated_at_utc` `2026-09-11T03:48:12Z`; the file is named for the local
2026-09-10 working date).

## Connection and method

Central warehouse `data/processed/elections/alabama_elections.sqlite`, opened as
`sqlite3.connect('file:...?mode=ro', uri=True)` with `PRAGMA query_only=ON`.
No write statement was issued; `writes_performed = 0`. Latest analytical build on
that snapshot: `RUN-92AB8DE353AC47D6AECE3D7767C29FCD`
(`southern_war_preparation_no_finance`, `validated`).

Two directories are being rebuilt concurrently by the primary agent and were
**not read for content** — only hashed:
`data/processed/war/alabama_war_v1/` and
`data/processed/war/alabama_historical_war_v1/`.

Objects queried: `mart_southern_war_outcome`, `mart_southern_war_context_feature`,
`canonical_candidates`, `canonical_southern_legislative_candidate_election`,
`bridge_alabama_canonical_candidate_certified_result`, `vote_observations`,
`warehouse_source_file`, `warehouse_build_run`.

Recomputed universe is derived from the same compatibility inputs the historical
builder consumes (`scripts/build_alabama_historical_war_v1.py`):

- `data/processed/war/cmo_v5_races.csv` (509 data rows),
- `data/processed/war/cmo_v5_candidates.csv` (1,018 data rows),
- `data/processed/elections/canonical_cmo_features.csv` (1,055 data rows),
- `data/processed/elections/canonical_cmo_candidates.csv` (1,564 data rows),
- `data/manual/ideology/candidate_research_aliases.csv`.

## Input freshness

| Input | sha256 | vs HEAD historical manifest |
|---|---|---|
| `cmo_v5_races.csv` | `a8745953…04024` | matches |
| `cmo_v5_candidates.csv` | `be5ce113…e500c` | matches |
| `canonical_cmo_features.csv` | `b72934f5…856d0` | matches |
| `candidate_research_aliases.csv` | `a764a270…ea51` | matches |
| `alabama_war_v1/race_war.csv` | `a971d5e8…aa59e` | **differs** (manifest recorded `1115eeee…25cd`) |
| `post2016_southern_war_v3/manifest.json` | `c6c09e19…05a6` | **differs** (manifest recorded `ca792a69…800b`) |

The published historical run `AL-HIST-WAR-V1-1FBFE5489CAEFA2E77AB` (git HEAD
manifest, 2026-09-02) is therefore bound to superseded inputs: warehouse build
`RUN-A4718C009110424B872392120C7F7E9F` and Southern source
`WAR-POST2016-V3-D9C7EE17BD14B8C7D23A`. The currently approved Southern source is
`WAR-POST2016-V3-4AF79A70EAA8F39EBD49`
(`SOUTHERN_V3_RELEASE_DECISION.json`, `approved_for_descriptive_historical_use`).
The compatibility CSVs themselves are unchanged; only the downstream published
modern source and the Southern manifest moved.

## Recomputed universe

Recomputed by re-running the compatibility pipeline's own filters:

- `canonical_cmo_features.csv` retains a row where
  `war_eligible == 1 AND model_eligible == 1`; `model_eligible` is `True` for all
  1,055 rows, so `war_eligible` alone splits the file.
- `cmo_v5_candidates.csv` is `canonical_cmo_candidates.csv` inner-joined to those
  races; every candidate row is `canonical_party ∈ {D, R}`.
- The builder's own guards then require unique race keys, a non-null context join
  for every retained race, and explicit non-null incumbency.

Result: **509 races and 1,018 candidate rows (509 D + 509 R)**, identical to the
git-HEAD manifest diagnostics (412 backcast, 97 published modern, 21
lag-context-missing). The builder hard-asserts these two counts, so any drift
aborts rather than silently resizing the product.

| cycle | chamber | compat races | features rows | features war-eligible | `canonical_candidates` strict | materialized AL strict | `mart_southern_war_outcome` |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1994 | house | 54 | 104 | 54 | 54 | 54 | 0 |
| 1994 | senate | 18 | 35 | 18 | 18 | 18 | 0 |
| 1998 | house | 57 | 57 | 57 | 57 | 57 | 0 |
| 1998 | senate | 28 | 28 | 28 | 28 | 28 | 0 |
| 2002 | house | 51 | 104 | 51 | 51 | 51 | 0 |
| 2002 | senate | 23 | 35 | 23 | 23 | 23 | 0 |
| 2006 | house | 40 | 98 | 40 | 40 | 40 | 0 |
| 2006 | senate | 22 | 34 | 22 | 22 | 22 | 0 |
| 2010 | house | 42 | 105 | 42 | 42 | 42 | 0 |
| 2010 | senate | 21 | 35 | 21 | 21 | 21 | 0 |
| 2014 | house | 40 | 105 | 40 | 40 | 40 | 0 |
| 2014 | senate | 16 | 35 | 16 | 16 | 16 | 0 |
| 2018 | house | 49 | 105 | 49 | 49 | 49 | 49 |
| 2018 | senate | 15 | 35 | 15 | 15 | 15 | 15 |
| 2022 | house | 25 | 105 | 25 | 25 | 25 | 25 |
| 2022 | senate | 8 | 35 | 8 | 8 | 8 | 8 |
| **total** | | **509** | **1,055** | **509** | **509** | **509** | **97** |

Lag-context-missing races retained explicitly (21):
1994 house 5, 1998 house 2, 2002 house 5, 2002 senate 2, 2006 house 2,
2006 senate 2, 2014 house 3.

## Exclusion ledger

| Step | Rows in | Rows out | Removed |
|---|---:|---:|---:|
| `canonical_cmo_features.csv`, all cycles | — | 1,055 | — |
| `contest_status = unopposed_democrat` (R votes absent) | 1,055 | 789 | 266 |
| `contest_status = unopposed_republican` (D votes absent) | 789 | 509 | 280 |
| `contest_status = no_major_party_votes` | 509 | 509 | 0 |
| `model_eligible = False` | 509 | 509 | 0 |
| not retained as a WAR race (546 = 266 + 280) | | | **546** |
| `canonical_cmo_candidates.csv` D/R rows | — | 1,564 | — |
| candidate rows of non-war-eligible races | 1,564 | 1,018 | **546** |
| candidate rows of non-major party | 1,018 | 1,018 | 0 |
| committee-like candidate names | 1,018 | 1,018 | 0 |
| blank candidate names | 1,018 | 1,018 | 0 |
| identifier-shaped names resolved by verified alias | 50 | 0 unresolved | 0 |
| duplicate race keys / candidate keys | 509 / 1,018 | same | 0 |
| missing context on a retained race key | 509 | 509 | 0 |
| missing explicit incumbency on a retained race key | 509 | 509 | 0 |

Notes.

- The candidate-level publication gate is the strength of this compatibility
  layer: 50 rows carry an identifier-shaped source label (`^[A-Z]{3}\d{3}[A-Z]{4,}$`,
  e.g. `GSL032DBOY`); all 50 resolve through
  `candidate_research_aliases.csv` rows with a `verified_*` `identity_status`, and
  the malformed source value is retained in `source_candidate_name`. Zero
  unresolved. `498` verified alias rows exist; only the 50 identifier-shaped rows
  change `display_name_source`.
- The compatibility inputs are **already** the contested D-vs-R universe. The
  builder's `prepare_historical_races` and `build_candidate_rows` apply no
  additional exclusion; they raise on any drift.
- Districts with **no** D/R candidate record at all, so no race row exists:
  1994 house {92}; 1998 house 48 districts (`7, 15, 19, 33, 34, 36, 37, 39, 40,
  41, 43–48, 50, 52, 53, 56–59, 61, 68–78, 82, 83, 85, 88, 90, 92–94, 97–101,
  103`); 1998 senate {15, 17, 19, 23, 28, 33, 34}; 2006 house {1, 2, 3, 5, 18,
  24, 86}; 2006 senate {1}. The registered SOS precinct source records a single
  candidate with `party_norm = 'O'` in the 1998 cases; whether those contests were
  unopposed or carry an unlabelled party is **not established** here.

## Warehouse cross-check per cycle/chamber

Three independent warehouse derivations were compared against the compatibility
universe.

1. **`mart_southern_war_outcome`** — the strict outcome mart the Southern route
   consumes. Its selection
   (`load_southern_war_preparation_warehouse.select_model_outcomes`) requires
   exactly one D and one R with `votes > 0`, no `dontuse`/`uncont` flag, and a
   general-stage `source_etype`. Its scope is **`cycle BETWEEN 2016 AND 2024`**,
   so Alabama contributes only 2018 (64) and 2022 (33) = **97** rows, all
   `election_stage='general'`, `selection_status='canonical_model_eligible'`,
   `source_family='alabama_canonical'`.
   Difference keys vs compatibility: **0** for 2016–2022; **412** for 1994–2014,
   which is the entire backcast key set and is a scope boundary, not a defect.

2. **`canonical_candidates`** — grouped by `year, chamber, district` and keeping
   groups holding both `'D'` and `'R'`: **509** races, per cycle/chamber identical
   to the table above. Symmetric difference vs the compatibility keys: **0** (no
   key in either direction). All 1,018 compatibility candidate rows join by
   `canonical_candidate_id`; the 546 rows without a compatibility counterpart are
   exactly the non-war-eligible candidates.

3. **`canonical_southern_legislative_candidate_election`** — restricted to
   `state_code='AL'`, `source_family='alabama_canonical'`, cycles 1994–2022:
   **509** strict races, identical per cycle/chamber, symmetric difference **0**.
   Every Alabama row in that table is `election_stage='general'`. 73 rows with
   `source_family='klarner'` (65 races not present in `canonical_candidates`)
   coexist there and do not enter the outcome mart; see out-of-scope observations.

**Race-universe conclusion:** the documented 509 races are fully reproduced by the
current repaired warehouse for every cycle and chamber, with no set difference.
The compatibility inputs carry no `election_stage` column, so stage for
1994–2014 is not established from those files (see *Not established*).

## `alabama-03`: 2018/2022 certified totals and identity revalidation

The 2026-09-08 certified integration
(`RUN-DD7FF8C9ACBE4EAAA026AD1046693CA9`, `RUN-4C2EF8D12CC442D99A516E0D393DE157`)
bridged 377 Alabama canonical candidates to certified canvass cells and corrected
21 totals: 2018 house 5, 2018 senate 6, 2022 house 10, 2022 senate 0.

### Compatibility totals are pre-repair, exactly

For all **97** modern races
`cmo_v5_races.csv` (and `canonical_cmo_features.csv`) D/R votes equal the bridge's
`canonical_votes_before` (97/97 for each party), and
`mart_southern_war_outcome` D/R votes equal the bridge's `certified_votes`
(97/97 for each party). The compatibility inputs therefore demonstrably predate
the certified repair.

### Races with superseded totals inside the 509 universe — 7

| cycle | chamber | district | compat D | compat R | compat margin | warehouse D | warehouse R | warehouse margin | ΔD | ΔR | Δmargin |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2018 | house | 81 | 4,696 | 12,823 | −46.389634 | 4,697 | 12,823 | −46.381279 | +1 | 0 | +0.008356 |
| 2018 | house | 83 | 8,940 | 5,142 | 26.970601 | 8,943 | 5,143 | 26.977140 | +3 | +1 | +0.006540 |
| 2018 | senate | 14 | 13,171 | 34,953 | −45.262239 | 13,173 | 34,957 | −45.260752 | +2 | +4 | +0.001487 |
| 2018 | senate | 27 | 20,586 | 29,741 | −18.191031 | 20,587 | 29,741 | −18.188682 | +1 | 0 | +0.002348 |
| 2022 | house | 32 | 5,519 | 4,389 | 11.404925 | 5,522 | 4,390 | 11.420500 | +3 | +1 | +0.015575 |
| 2022 | house | 68 | 9,517 | 8,948 | 3.081506 | 9,537 | 8,981 | 3.002484 | +20 | +33 | −0.079021 |
| 2022 | house | 92 | 1,789 | 11,778 | −73.627184 | 1,795 | 11,812 | −73.616521 | +6 | +34 | +0.010663 |

These carry 12 of the 21 corrected candidate rows. `mart_southern_war_outcome`
flags exactly these 7 races with a non-empty
`alabama_certified_bridge.corrected_candidates` list. The residual impact is small
but real: `raw_gap = direct_cmo = legislative_dem_margin − selected_ticket_margin`,
so each of the 7 races carries a superseded `raw_gap` and — for 2018/2022 — the
compatibility cycle context is inconsistent with the certified warehouse margin.

### Remaining 9 corrections are in WAR-excluded races

Nine corrected candidates sit in unopposed races that the WAR universe excludes;
they affect no WAR score but do leave stale totals in
`canonical_cmo_features.csv` (`canonical_cmo_candidates.csv` likewise):

| cycle | chamber | district | party | candidate | compat votes | certified votes | Δ | compat status |
|---|---|---:|---|---|---:|---:|---:|---|
| 2018 | house | 49 | R | April Weaver | 10,794 | 10,795 | +1 | unopposed_republican |
| 2018 | house | 67 | D | Prince Chestnut | 11,239 | 11,635 | +396 | unopposed_democrat |
| 2018 | senate | 23 | D | Malika Sanders-Fortier | 29,920 | 30,193 | +273 | unopposed_democrat |
| 2018 | senate | 28 | D | Billy Beasley | 28,442 | 28,445 | +3 | unopposed_democrat |
| 2018 | senate | 30 | R | Clyde Chambliss, Jr. | 35,256 | 35,259 | +3 | unopposed_republican |
| 2022 | house | 16 | R | GSL016RSOU | 13,174 | 13,177 | +3 | unopposed_republican |
| 2022 | house | 56 | D | GSL056DTIL | 8,986 | 9,008 | +22 | unopposed_democrat |
| 2022 | house | 73 | R | GSL073RPAS | 10,343 | 10,404 | +61 | unopposed_republican |
| 2022 | house | 75 | R | GSL075RING | 11,688 | 11,690 | +2 | unopposed_republican |

In total **16** rows of `canonical_cmo_features.csv` carry superseded totals
(7 in-universe + 9 excluded); 11 stale D values, 10 stale R values.

The compat inputs carry **no** third-party/other vote column at all, whereas
`mart_southern_war_outcome` records `third_party_votes` (2018: 5,302; 2022: 4,559
across the 97 races; two-party totals 1,571,806 and 667,171). Third-party totals
for 1994–2014 are therefore not carried by the historical WAR compatibility
inputs.

### Identity comparison, 2018 and 2022

Joining `cmo_v5_candidates.csv` to `canonical_candidates` on
`canonical_candidate_id` (all 1,018 rows match; 194 of them fall in the 97 modern
races):

| Field | Mismatches (1,018 rows) | Mismatches (194 modern rows) |
|---|---:|---:|
| `canonical_name` | 0 | 0 |
| `canonical_party` | 0 | 0 |
| `winner` | 0 | 0 |
| `person_id` | 0 | 0 |
| `canonical_source` | 0 | 0 |
| `canonical_votes` | 12 | 12 |
| `incumbent` | **17** | **17** |

- **Identity (name/party/winner/person/source) is clean** for the whole file and
  for the 97 modern races. The 12 vote mismatches are exactly the certified
  corrections above.
- **All 17 incumbency mismatches are 2022** and all run compat `0` → warehouse
  `1`. They are the same 17 districts for which
  `mart_southern_war_context_feature` records a `source_validated` incumbent
  (12 R-held, 5 D-held, `strict_incumbency_eligible = 1`) while
  `canonical_cmo_features.csv` records `dem_incumbent = 0` and
  `rep_incumbent = 0`:
  2022 house 12, 27, 32, 33, 41, 43, 63, 65, 68, 69, 82, 85 and senate 2, 7, 21,
  29, 33. `2018` has zero incumbency mismatches.
- Because 2018/2022 WAR uses the published same-cycle residual, this stale
  incumbency does not change the published 2018/2022 scores, but it does change
  `incumbency_balance` in the historical export and any modelling that consumes
  it. Whether the compat file or the warehouse is authoritative here is **not
  adjudicated** by this audit.
- `cmo_v5_candidates.csv` carries no `election_stage`; stage is established only
  warehouse-side (`election_stage='general'` for all 97 mart rows).

## Source-cell lineage availability

**The compatibility inputs carry no source-cell lineage columns at all.** Scanning
every column of all four compatibility files for `source`/`file`/`cell`/`sheet`/
`row`/`column`/`page`/`locator` yields only provenance *labels*, never a pointer
to a source cell:

- `cmo_v5_races.csv`: `selected_ticket_source`
- `canonical_cmo_features.csv`: `*_source_complete` booleans only
- `cmo_v5_candidates.csv`: `canonical_source`, `selected_ticket_source`,
  `pre_election_quality_source`

Consequences:

- For 1998 — a compatibility cycle, and one of the two years whose physical
  locators were repaired — the WAR inputs cannot be traced to a source workbook
  cell. Warehousing-wise the lineage does exist: `vote_observations` holds
  196,769 rows for 1998 and 196,455 of them carry `source_file`,
  `source_sheet`, `source_row` and `source_column`. None of it reaches the
  compatibility files.
- For 2004 — the other repaired year — the compatibility inputs contain **no 2004
  rows at all**: 2004 is not an Alabama legislative general-election cycle in the
  1994–2022 product (cycles are 1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022).
  `vote_observations` does hold 127,069 rows for 2004, only 32,427 of which carry
  the locator triple.
- For 2018/2022 the warehouse mart does carry scalar lineage
  (`source_file_id`: `SRC-A3632F0E8738FDFB544D` for the 2018 certified canvass,
  `SRC-DD940F20743C33261CC2` for 2022, all 97 rows) plus per-candidate precinct
  cells on the observation sets. Those identifiers are absent from the
  compatibility CSVs, so the current historical WAR export cannot carry the
  certified canvass lineage it depends on.

## Source coverage gap: 2002 house district 27

The registered SOS precinct source records 2002 State House district 27 as a
contested D–R race (all rows from source member
`2002-GeneralElection-PrecinctLevel_0.xls::MARSHALL`):

- McLaughlin, Jeffrey (DEM) 7,724
- Hawkins, Gerald (Jerry) (REP) 4,789
- Driggers, Allen Eugene (LIB) 662

`canonical_candidates` has **no rows** for 2002 house 27, `canonical_cmo_features.csv`
has no row, and the race is absent from the 509-race universe. Every other 2002
house district reconciles exactly to the raw source (103 of 105 districts match
to the vote). Whether this omission is an intended coverage exclusion or a
canonical identity defect is **not established** by this audit; it is reported,
not adjudicated.

## Out-of-scope observations (reported, not changed)

1. `canonical_candidates` 2002 house 26 holds 1,102 D + 598 R while
   `vote_observations` holds two conflicting row sets for the same contest:
   77 rows with `source_file IS NULL` (1,102/598) and 50 rows from
   `2002-GeneralElection-PrecinctLevel_0.xls::MARSHALL` (5,967/3,861). This is
   natural-key duplication adjudication (`warehouse-04`), not part of this audit.
2. 2014 house 31, house 66 and senate 30 carry corrupted party labels in
   `vote_observations` — e.g. `Holmes` (D) 21,532 beside `Mike Holmes` (R) 356,
   and `Chambliss, Jr.` printed as both D 4,040 and R 16,100.
   `canonical_candidates` uses the consolidated official result
   (10,944 / 7,079 / 22,916) and did not adopt those rows. Positive finding: the
   canonical layer did not propagate the corruption; the class is otherwise
   outside this audit's scope.
3. `canonical_southern_legislative_candidate_election` holds 73 Alabama
   `source_family='klarner'` rows across 65 races absent from
   `canonical_candidates`; none is a strict D–R race in the certification path and
   none enters the 97-row outcome mart.
4. `scripts/repair_alabama_canonical_certified_totals.py` already declares
   `canonical_cmo_candidates.csv`, `canonical_cmo_features.csv`,
   `historical_cmo_extension.csv`, `alabama_war_v1`, `alabama_historical_war_v1`
   and `alabama_war_forecast_v1` stale. This audit quantifies that declared list
   (7 in-universe races, 12 candidate rows, 16 stale feature rows) rather than
   discovering it.

## What is established

- The 509 races and 1,018 candidate rows recompute exactly from the current
  compatibility inputs, and no cycle/chamber has any set difference against
  `canonical_candidates` or the Alabama rows of
  `canonical_southern_legislative_candidate_election`.
- `mart_southern_war_outcome` reproduces exactly the 97 Alabama 2018/2022 races
  and carries the certified totals; the compatibility inputs instead carry the
  pre-certified totals for 7 of those races and pre-certified incumbency for 17
  of the 97 race contexts.
- Candidate names, parties, winners, person IDs and canonical sources match
  exactly between the compatibility candidates file and the warehouse for all
  1,018 rows.
- The compatibility inputs carry zero source-cell lineage, and the 2018/2022
  certified canvass lineage present in the warehouse does not reach them.
- One contested D–R race (2002 house 27) recorded by the registered SOS source is
  absent from the canonical record and from the 509-race universe.

## What is not established

- Whether the certified-bridge votes are the correct authority for the affected
  contests (no adjudication performed here).
- Whether the concurrent `data/processed/war/alabama_war_v1/` rebuild carries the
  certified totals; that directory was not read.
- Whether 1994–2014 compatibility totals reconcile to physical source cells —
  the inputs carry no lineage at all, so this cannot be checked from them.
- Whether the 48 (1998 house) and 7 (1998 senate) districts with no D/R candidate
  row were unopposed or carry an unlabelled party.
- Whether the missing 2002 house 27 race is an intended exclusion or a defect.
- Whether the 2022 incumbency difference is a compat-input defect or a
  warehouse-side plan/redistricting reassignment.
- Whether `election_stage` for 1994–2014 compatibility races is `general` as a
  matter of source record (no stage column; the materialized table records
  `general` for the Alabama rows it holds).
- Whether 546 is a complete exclusion count: the ledger is derived from the
  compatibility files, not from an independent raw-source enumeration of every
  1994–2022 legislative contest.

## Regeneration requirement

**`cmo_v5_races.csv` and `cmo_v5_candidates.csv` must be regenerated before the
historical WAR can be certified.** They embed superseded 2018/2022 D/R totals for
7 of the 509 races (and their source feature files carry them for 16 races), plus
stale 2022 incumbency for 17 race contexts. Any historical WAR built from them
would be scored against pre-certified outcomes while the modern Southern source is
the certified, approved one.

Order, with hazards:

1. `canonical_candidates` is already repaired in place
   (`RUN-4C2EF8D12CC442D99A516E0D393DE157`). Rerun
   `scripts/build_canonical_cmo_features.py` to refresh
   `canonical_cmo_features.csv` and `canonical_cmo_candidates.csv`.
   **Do not** regenerate `canonical_candidates` through a full identity rebuild:
   `repair_alabama_canonical_certified_totals.py` records that
   `build_candidate_identity.py` would recreate the pre-certified totals.
2. Rerun `scripts/rebuild_cmo_candidate_quality_v5.py` to refresh
   `cmo_v5_races.csv` / `cmo_v5_candidates.csv`. This recomputes `direct_cmo` and
   `candidate_quality_index`, so every v5 consumer is invalidated — including the
   ideology page's CQI join — not only the historical WAR.
3. Rerun `scripts/build_alabama_historical_war_v1.py`. Note its guards: 509 races
   and 1,018 rows asserted, and for 2018/2022
   `raw_gap == published alabama_war_v1 raw_gap` is asserted, so the modern
   `alabama_war_v1` export must itself already carry the certified totals when the
   historical rebuild runs.

Regeneration, the warehouse rebuild and publication are outside this audit's
read-only scope and were not performed.

## Reproducing the checks

All warehouse queries used one read-only connection. Representative queries:

```sql
SELECT cycle, chamber, COUNT(*) FROM mart_southern_war_outcome
WHERE state_code='AL' GROUP BY cycle, chamber;

SELECT year, chamber, district, canonical_party, canonical_votes
FROM canonical_candidates;

SELECT cycle, chamber, district, canonical_party, canonical_name,
       canonical_votes_before, certified_votes, vote_delta, correction_status
FROM bridge_alabama_canonical_candidate_certified_result
WHERE correction_status='corrected_to_certified';

SELECT year, COUNT(*) AS rows,
       SUM(source_row IS NOT NULL) AS row_loc
FROM vote_observations WHERE year IN (1998, 2004) GROUP BY year;
```

Filter recomputation (pandas, no warehouse write):

```python
feat = pd.read_csv("data/processed/elections/canonical_cmo_features.csv")
feat[feat.war_eligible & feat.model_eligible]        # -> 509 races
cands = pd.read_csv("data/processed/war/cmo_v5_candidates.csv")  # -> 1018 rows
```

No pytest run, formatter, linter or project-wide suite was executed: this unit
changes no code and no testable artifact. `data/processed/elections/backups/` and
the central warehouse were not written.
