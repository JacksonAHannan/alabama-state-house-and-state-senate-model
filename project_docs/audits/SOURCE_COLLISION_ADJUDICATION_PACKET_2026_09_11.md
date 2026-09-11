> **Erratum (2026-09-11, `SOURCE_DEFECT_BLAST_RADIUS_2026_09_11.md`):** Case C's
> "legacy ×2 block duplication" is a mischaracterisation. The two rows per 2014
> precinct are `alabama_sos` (authority rank 1) and `openelections` (rank 2),
> stored by design; `canonical_vote_observations` keeps rank 1 only and every
> product consumer filters to `alabama_sos`. No intra-source duplicate exists (0
> of 110,189 SOS rows). The party-label defects in Case C are provider-printed
> and remain as described. Case A/B findings stand and were applied as
> `RUN-DFB1D093D7594AB68A264292050E924D`.

# Source collision adjudication packet — 2002 HD26/HD27 and 2014 HD31/HD66/SD30

Internal evidence packet for checklist item `warehouse-05` (owner adjudication of
remaining natural-key collisions). Task `WAREHOUSE-05-SOURCE-ADJUDICATION-EVIDENCE-20260911`.

**This is a read-only evidence packet. No data, code, model output, published
export or coordination file was changed. No disposition is selected here** — each
case presents options with consequences and the additional evidence each would
need. The owner decides.

- Working date: 2026-09-11 (host clock). `generated_at_utc` is in the companion JSON.
- Warehouse: `data/processed/elections/alabama_elections.sqlite`
  (5,819,064,320 bytes, mtime 2026-09-11 00:25), opened
  `sqlite3.connect('file:...?mode=ro', uri=True)` + `PRAGMA query_only=ON`.
  `writes_performed = 0` against the live warehouse.
- Pre-repair reference: `data/processed/elections/backups/pre-source-repair-2026-09-05.sqlite`
  (5,746,839,552 bytes), opened read-only. This is the state the 2026-09-02
  canonical build consumed.
- Raw workbooks opened in memory from the registered immutable sources below;
  on-disk SHA-256 re-verified against `warehouse_source_file`.
- Runtime caveat: `PRAGMA query_only` is a guard, not a sandbox; all statements
  issued were SELECT.

## Registered sources used

| id | local path | sha256 | status / scope |
|---|---|---|---|
| `SRC-9E0F7297AEB976F98688` | `data/raw/alabama_elections_and_geography/2002-GeneralElection-PrecinctLevel_0.xls` | `9400cfa16da62d303fac0115707ad3f71fc9d29a36f157ac17e0792d2a5ed45e` | normalized; `official_vote_counts` |
| `SRC-EB647D3AA2049AD37AD6` | `data/raw/alabama_elections_and_geography/2014General-precinctLevel.zip` | `a4facea99c554d855eabe098305df4f2b73431ec57b64c1c46080abecb725e67` | normalized; `official_vote_counts` |
| `SRC-F88A7698F08358C9E20B` | `data/raw/openelections/20141104__al__general__precinct.csv` | `a5b7ef896c78db994c0842d3f7aa9466a8d054ce7246a73e5b0ed9fcf6ec5933` | normalized; `identity_enrichment` |

On-disk hashes of all three matched the registry values exactly.

**No 2014 certified canvass is registered.** The only canvass PDFs in
`warehouse_source_file` are `2018_general_certified_canvass.pdf`
(`SRC-A3632F0E8738FDFB544D`) and `2022_general_certified_canvass.pdf`
(`SRC-DD940F20743C33261CC2`). For 2014 the nearest registered official record is
the SOS precinct ZIP above. Cross-checks below therefore use its printed cells,
not a separate canvass.

## Layer map (what each artifact is)

| Layer | Object | Owner |
|---|---|---|
| source observations | `vote_observations` (locator columns `source_file`, `source_sheet`, `source_row`, `source_column`, `source_file_id`, `build_run_id`, `authority_rank`) | `scripts/build_election_database.py` (registry: lifecycle `replace`) |
| identity build | `canonical_candidates` | `scripts/build_candidate_identity.py` |
| compatibility export | `data/processed/elections/canonical_cmo_features.csv`, `canonical_cmo_candidates.csv` | `scripts/build_canonical_cmo_features.py` |
| compatibility WAR input | `data/processed/war/cmo_v5_races.csv`, `cmo_v5_candidates.csv` | `scripts/rebuild_cmo_candidate_quality_v5.py` |
| historical WAR export | `data/processed/war/alabama_historical_war_v1/race_war.csv` (`AL-HIST-WAR-V1-76814789B2F7641E4255`) | `scripts/build_alabama_historical_war_v1.py` |

Relevant recorded build runs:

| run | target | when | note |
|---|---|---|---|
| `RUN-16A85CF9DA9E4233A55619147EE1ED4C` | `election_source_layer` | 2026-08-16T19:07:59Z | initial `vote_observations` load, pre-locator |
| `RUN-872E84CE49F34E46A3B71A275F9C8890` | `canonical_candidate_identity` | 2026-09-02T02:51:42Z | **last identity build** |
| `RUN-40A033B9854141F6B05A76173E66D17B` | `source_quality_repair_2026_09_05` | 2026-09-05T21:25:47Z–21:34:14Z | reparsed 2002 `MARSHALL`; added locator columns |

`canonical_candidates` is therefore **staler than `vote_observations`** for 2002
Marshall: it predates the repair by three days and has not been rebuilt since.

---

## Case A — 2002 House District 26: two observation sets, one contest

### Raw workbook cells (worksheet-verified, in memory)

Source `SRC-9E0F7297AEB976F98688`, member/sheet `MARSHALL` and sheet `DEKALB`
(sheets are county workbooks; both were opened from the single registered `.xls`).

| Raw cell(s) | Value |
|---|---|
| `MARSHALL` row 68, cols D/E/F/G = title `STATE HOUSE OF REPRESENTATIVES, DISTRICT 26` / `DEM` / `McDaniel, Frank` / `5,967`; precinct cells cols H–BE (50 cells) sum to 5,967 (col C is the repeated county name) | HD26 Marshall D |
| `MARSHALL` row 69, cols D/E/F/G = … / `REP` / `Patterson, Jeffrey` / `3,861`; cols H–BE sum 3,861 | HD26 Marshall R |
| `MARSHALL` row 70, cols D/E/F/G = … / `WI` / `WRITE-IN` / `5` | HD26 Marshall write-in |
| `DEKALB` row 71, cols C/D/E/F = title / `DEM` / `McDaniel, Frank` / `1,102`; precinct cells cols G–CE (77 cells) sum to 1,102 | HD26 DeKalb D |
| `DEKALB` row 72, cols C/D/E/F = … / `REP` / `Patterson, Jeffrey` / `598`; cols G–CE sum 598 | HD26 DeKalb R |
| `DEKALB` row 73, cols C/D/E/F = … / `WI` / `WRITE-IN` / `0` | HD26 DeKalb write-in |

A scan of **all 67 sheets** of the workbook for `STATE HOUSE OF REPRESENTATIVES,
DISTRICT 26` returns exactly two sheets: `DEKALB` (rows 71–73) and `MARSHALL`
(rows 68–70). Both carry the identical contest title and the identical two
candidates. `RECONCILIATION`: the repair evidence row `WQA-01-02`
(`qa_warehouse_source_repair`, run `RUN-40A033B9854141F6B05A76173E66D17B`)
records `MARSHALL` source rows 68/69/71/72/73 each reconciling to their printed
county totals (50 precinct cells; `summary_column` 7 = printed `Total Of Number
Votes`).

**Factual reading of the raw source:** the two sets are **complementary county
segments of the same district-26 contest** (DeKalb + Marshall), not two competing
versions. The district-wide printed total is D 7,069 / R 4,459 (+ 5 write-ins,
Marshall).

### Stored `vote_observations` rows (2002, `office='State House'`, `district=26`)

| set | rows (`rowid` range) | D | R | `source_file` | sheet | `source_row` | `source_column` | `source_file_id` | `build_run_id` | `authority_rank` |
|---|---|---|---|---|---|---|---|---|---|---|
| NULL-source (legacy) | 154 (394138–394291) | 1,102 (77 rows) | 598 (77 rows) | NULL | NULL | NULL | NULL | NULL | NULL | 1 |
| locator set | 100 (2449719–2449818) | 5,967 (50) | 3,861 (50) | `2002-GeneralElection-PrecinctLevel_0.xls::MARSHALL` | `MARSHALL` | 68 (D) / 69 (R) | 8–57 | `SRC-9E0F7297AEB976F98688` | `RUN-40A033B9854141F6B05A76173E66D17B` | 1 |

- The NULL-source rows carry `county_key='DEKALB'` only. Their 77 `precinct_key`
  values are **set-identical** to the 77 precinct names in the `DEKALB` sheet
  header (row 2, columns G–CE), in the same order, and their values match that
  sheet's HD26 column cell-for-cell (verified cell-by-cell sum 1,102 / 598).
  Their `build_run_id` is NULL because they predate the locator columns
  (added by `ALTER TABLE` in the 2026-09-05 repair) — the owning load is
  `election_source_layer` `RUN-16A85CF9DA9E4233A55619147EE1ED4C` (2026-08-16),
  whose target has been run exactly once.
- No write-in rows are stored for HD26 from either sheet (`is_pseudocandidate`
  filters `WRITE-IN`).
- There is no *third* HD26 set, and the two sets cannot be the same county read
  twice: in the **current** warehouse, `county_key='MARSHALL'` for 2002 has
  0 NULL-locator rows (all 2,950 are the repaired locator set). The pre-repair
  database did contain 4,029 2002 Marshall rows, but they were the malformed
  legacy parse (`office='MARSHALL'`, `district IS NULL`; see Case B) and were
  deleted/replaced by the 2026-09-05 repair. The DeKalb set is a different county
  with a different precinct universe, so the two sets are disjoint sources, not
  duplicate readings of one.

### Canonical and downstream layers as stored

- `canonical_candidates` (2002, house, 26): **2 rows** — D `McDaniel, Frank`
  1,102; R `Patterson, Jeffrey` 598 (`canonical_source='alabama_sos'`;
  ids `AL-2002-house-26-D-MCDANIEL-FRANK` / `…-R-PATTERSON-JEFFREY`).
  This is the **DeKalb segment only**.
- `canonical_cmo_features.csv` (2002/house/26): `dem_votes=1102`, `rep_votes=598`,
  `two_party_votes=1700`, `legislative_dem_margin=29.647059`, `war_eligible=True`,
  `contest_status=contested_two_party`, `core_index_margin=-24.189062`,
  `core_index_offices=2`, `baseline_fallback_share=0.0510023`,
  `baseline_allocation_method=county_population_fallback`,
  `raw_overperformance=53.836121`, `model_tier=core_1998_2022`,
  `readiness_status=experimental_complete_context`.
- `cmo_v5_races.csv` 2002/house/26: same 1,102 / 598 / margin 29.647059 /
  `selected_ticket_margin=-39.648808`.
- Historical WAR `race_war.csv` **line 180** (`AL-HIST-WAR-V1-76814789B2F7641E4255`):
  `dem_votes=1102`, `rep_votes=598`, `legislative_dem_margin=29.647059`,
  `selected_ticket_margin=-39.648808` (`same_cycle_federal`), `raw_gap=69.295867`,
  `fitted_structural_expected_gap=12.065240`, `war=57.230626`,
  `scoring_scope=post2016_southern_model_backcast`, `backcast_extrapolation_years=16`.

### Quantified effect if the district total (7,069 / 4,459) were adopted

Holding everything else fixed:

| quantity | today (DeKalb only) | district total | Δ |
|---|---:|---:|---:|
| legislative WV margin | 29.6471 | 22.6405 | **−7.0065 pp** |
| `raw_gap` (leg − ticket) | 69.2959 | 62.2893 | −7.0065 |
| `war` (raw_gap − fitted expected 12.0652) | 57.2306 | 50.2241 | −7.0065 |

The ticket baseline (`selected_ticket_margin=-39.648808`) is a same-cycle federal
allocation; it is not a function of the legislative observation sets, so this
adjudication does not itself change the baseline. (The baseline did move
independently, −17.7 → −39.6, in the 2026-09-10 identity re-keying recorded in
`ALABAMA_WAR_DEPENDENCY_REBUILD_2026_09_10.md`; that is a separate issue.)

### Finding

> **2002 HD26 is not a conflict between two versions — it is a district split
> across two county sheets of one registered workbook; the canonical layer
> carries only the DeKalb half (1,102/598) and omits the Marshall half
> (5,967/3,861), understating the legislative margin by 7.01 pp.**

### Disposition options (not selected)

**A1 — Adopt the county-complement district total (7,069 / 4,459).**
Change `canonical_candidates` (2 rows), regenerate `canonical_cmo_features.csv`,
`cmo_v5_races`/`cmo_v5_candidates`, and the historical WAR export.
Consequence: HD26 row changes as quantified; `alabama_historical_war_v1`
(509 races), the Alabama slice of the Southern historical WAR, `docs/cmo.html`
and its downloads, and the release card's "baseline-sensitive districts" table
are invalidated and must be rebuilt and re-reviewed. Evidence needed: an owner
instruction that printed county portions sum to district totals under the 2002
plan for multi-county legislative districts, and re-verification that no other
2002 multi-county district carries the same split (HD24/HD29 also appear on the
DeKalb sheet).

**A2 — Retain the DeKalb-only canonical total and record the Marshall segment as
a distinct source observation with an explicit known-undercount flag.**
No numeric change; `vote_observations` already preserves both. Consequence:
HD26 keeps a wrong legislative margin and a wrong WAR score (57.23); the
published pages remain internally consistent but the release card must carry the
undercount as a limitation. Evidence needed: owner acceptance that the product
may ship a knowingly understated race, or an exclusion.

**A3 — Remove HD26 from the 509-race universe as unresolved-source.**
Consequence: the builder's hard assert of 509 races / 1,018 candidates aborts
until the contract is changed; the universe, `cmo_v5_*`, the historical export
and every published count change; the removal must be recorded in the exclusion
ledger with reviewer status. Evidence needed: owner decision to shrink the
published universe plus updated field contract and release decision.

**Not established for A:** whether any other 2002 (or 1994–2010) multi-county
district has one county segment missing from `canonical_candidates`; whether the
`county_population_fallback` baseline method interacts with the corrected
margin; and whether the underlying cause (legacy parse) also dropped *other*
Marshall legislative rows besides HD26/HD27 (see out-of-scope).

---

## Case B — 2002 House District 27: contested in the source, absent from canonical

### Raw workbook cells

Source `SRC-9E0F7297AEB976F98688`, sheet `MARSHALL`:

| Raw cell | Value |
|---|---|
| row 71, cols D/E/F/G | `STATE HOUSE OF REPRESENTATIVES, DISTRICT 27` / `DEM` / `McLaughlin, Jeffrey` / `7,724` (50 precinct cells H–BE) |
| row 72, cols D/E/F/G | … / `LIB` / `Driggers, Allen Eugene` / `662` |
| row 73, cols D/E/F/G | … / `REP` / `Hawkins, Gerald (Jerry)` / `4,789` |
| row 74, cols D/E/F/G | … / `WI` / `WRITE-IN` / `14` |

A scan of all 67 sheets for `…DISTRICT 27` returns **`MARSHALL` only** (rows
71–74): the district is Marshall-only in this source, so no other county sheet
can supply the missing half.

### Stored `vote_observations`

150 rows, `rowid` 2449819–2449968: 50 precincts × {D 7,724, LIB 662, R 4,789};
`source_file='2002-GeneralElection-PrecinctLevel_0.xls::MARSHALL'`,
`source_sheet='MARSHALL'`, `source_row` 71/72/73, `source_column` 8–57,
`source_file_id='SRC-9E0F7297AEB976F98688'`,
`build_run_id='RUN-40A033B9854141F6B05A76173E66D17B'`, `authority_rank=1`.
Write-in row excluded. The repaired rows are present and correct.

### Canonical

`canonical_candidates` 2002/house/27: **0 rows**. Per-2002 counts: 155 canonical
rows over 104 districts, **51 two-party races** — HD26 among them (DeKalb only),
HD27 absent.

### Root cause (source gap, not a builder rule)

`scripts/build_candidate_identity.py` (lines ~131–153) selects aliases from
`vote_observations` with `office in ('State House','State Senate') and district is
not null`, then keeps `resolved_party in ('D','R')`. There is **no** multi-county,
office-string or district-parse rule that excludes HD27. The exclusion happened
upstream of the identity build:

- The legacy 2002 adapter `_legacy_2002` (git `7ffd27e3:scripts/sos_precinct.py`,
  the code in place for the 2026-08-16 ingest) read
  `title, party, candidate = row[2:5]` and paired
  `precincts = padded[header_row-1][5:]` with `row[6:]`. That offset is correct
  for the `DEKALB`-style layout (contest title in column C, party D, candidate E)
  but wrong for the `MARSHALL`-style layout (`County Code, County, Contest Title,
  Contest Title, Party Code, Candidate`): it took the **county name as the office**
  and the **party code as the candidate**, and it treated the printed
  `Total Of Number Votes` column as a precinct.
- Verified in the pre-repair backup (`pre-source-repair-2026-09-05.sqlite`):
  all **4,029** 2002 `MARSHALL` rows have `office='MARSHALL'`, `district IS NULL`;
  **204** of them carry `party='STATE HOUSE OF REPRESENTATIVES, DISTRICT 27'`
  and sum 26,378 (= 2 × the printed 13,189, because the summary column was
  counted). Rows with `office IN ('State House','State Senate') AND district=27` in
  the pre-repair database: **0**.
- The 2026-09-05 repair `WQA-02` re-parsed `MARSHALL` with the corrected
  metadata-header adapter (2,950 retained cells; summary column excluded), which
  is why the correct HD26/HD27 rows exist today.
- `canonical_candidates` was last written 2026-09-02
  (`RUN-872E84CE49F34E46A3B71A275F9C8890`), i.e. **before** the repair, and has
  not been rebuilt. Simulating the identity selection over the pre-repair rows
  (offline) yields no HD27 candidate rows; simulating it over the repaired rows
  would yield D `McLaughlin, Jeffrey` and R `Hawkins, Gerald (Jerry)` (and LIB
  `Driggers, Allen Eugene` as `party_norm='O'`, which canonical would drop).

### Finding

> **HD27's omission is a source gap — a 2002 Marshall-sheet layout parse defect
> in the legacy adapter (fixed 2026-09-05) combined with a stale
> `canonical_candidates` (last built 2026-09-02) — not a canonical-builder
> exclusion rule.**

### Disposition options (not selected)

**B1 — Rebuild identity/canonical from the repaired warehouse.**
`canonical_candidates`, `canonical_cmo_features.csv`, `cmo_v5_*`, the 509-race
universe and the historical WAR export all change; HD27 would enter as a
contested D-R race (D 7,724 / R 4,789, LIB 662 excluded from the two-party
margin), making 510 races / 1,020 candidate rows. Consequence: the builder's hard
asserts (`509`/`1,018`), the release card, the exclusion ledger and every
published count change; the model must be re-run and reviewed. Evidence needed:
owner authorization to expand the published race universe, plus a decision on
the LIB row (currently dropped as non-major-party).

**B2 — Keep HD27 excluded and record it explicitly as a known source-covered but
unmodelled race.**
No numeric change; add HD27 to the release card/limitations and the exclusion
ledger with cause `legacy_2002_marshall_parse_defect; identity build stale`,
reviewer status, and the raw-cell reference. Consequence: the 509 contract stays
intact, but the product declares an incomplete universe. Evidence needed: owner
acceptance of the declared gap; a follow-up identity rebuild is still owed
independently of publication.

**B3 — Rebuild only `canonical_candidates` + `canonical_cmo_features` (not
`cmo_v5`/WAR), so HD27 is visible in the canonical layer while the published
509-race universe is unchanged.**
Consequence: canonical and compat features disagree; `canonical_cmo_features.csv`
would contain HD27's row while `cmo_v5_races.csv` does not, and the features
export is a declared input to `rebuild_cmo_candidate_quality_v5.py`; the
divergence must be documented or the chain re-run in order. Evidence needed:
confirmation that no consumer treats "features row exists" as "race in universe".

**Not established for B:** nothing further — the raw source, the pre-repair
database and the builder code all agree on the mechanism. Remaining uncertainty
is only whether the owner wants the universe expanded.

---

## Case C — 2014 HD31 / HD66 / SD30: corrupted party labels and duplicated blocks

### Raw workbook cells

Source `SRC-EB647D3AA2049AD37AD6` (`2014General-precinctLevel.zip`), opened per
member. Matrix-style county workbooks carry the office in header row 1 and the
printed candidate label (with party in parentheses) in row 2; wide-sheet
counties carry `Contest Title | Party | Candidate` headers.

| contest | raw cells | printed label | distinct precinct cells | printed county totals |
|---|---|---|---:|---|
| HD31 | `Elmore 2014 General Precinct.xlsx` :: `Sheet1` col **U** (21): row 1 `State Rep. Dist 31`, row 2 `Holmes (D)`, values rows 3–32 | `(D)` | **10,766** (27 cells) | grid rows 33/34 `CALCULATED TOTALS` 10,766 / `REPORTED TOTALS` 10,766 |
| HD31 | `2014-General-Autauga.xlsx` :: `Precinct Results` row **101**: A `STATE REPRESENTATIVE, DISTRICT NO. 31`, B `REP`, C `Mike Holmes`, values cols D+ | `REP` | **178** (3 cells) | — |
| HD66 | `Escambia 2014 General Precinct.xlsx` :: `Sheet1` col **S** (19): row 1 `State Rep. Dist 66`, row 2 `Baker (D)` | `(D)` | **4,862** (23 cells) | rows 34/35 `CALCULATED TOTALS` 4,862 / `REPORTED TOTALS` **5,293** (internally inconsistent) |
| HD66 | `2014-General-Baldwin.xlsx` :: `Precinct Results` row **142**: A `STATE REPRESENTATIVE, DISTRICT NO. 66`, B `REP`, C `Alan Baker` | `REP` | **2,217** (15 cells) | — |
| SD30 | `Elmore …` :: `Sheet1` col **R** (18): row 1 `State Sen. Dist. 30`, row 2 `Chambliss, Jr. (R )` | `(R )` | **8,050** (21 cells) | rows 33/34 = 8,050 / 8,050 |
| SD30 | `Chilton 2014 General Precinct.xlsx` :: `Sheet1` col **R** (18): row 2 `Chambliss Jr. (R )` | `(R )` | **2,444** (8 cells) | 2 totals × 2,444 |
| SD30 | `Coosa 2014 General Precinct.xlsx` :: `Sheet1` col **P** (16): row 2 `Chambliss, Jr. (D)` | **`(D)`** | **2,020** (14 cells) | 2 totals × 2,020 |
| SD30 | `2014-General-Autauga.xlsx` :: `Precinct Results` row **120**: B `REP`, C `Clyde Chambliss, Jr.` | `REP` | **9,639** (20 cells) | — |
| SD30 | `2014-General-Tallapoosa.xlsx` :: `Precinct Results` row **134**: B `REP`, C `Clyde Chambliss, Jr.` | `REP` | **763** (8 cells) | — |

Raw sums: HD31 10,766 + 178 = **10,944**; HD66 4,862 + 2,217 = **7,079**;
SD30 8,050 + 2,444 + 2,020 + 9,639 + 763 = **22,916**.

### Parser path (`scripts/sos_precinct.py` party assignment)

- Matrix workbooks (`Elmore`, `Escambia`, `Chilton`, `Coosa`) dispatch through
  `normalize_workbook` → `_county_matrix_sheets` (lines 149–173): `party` is
  `re.search(r"\(([DR])\s*\)", candidate_label).group(1)` and the candidate is
  the label with the suffix stripped. The `(D)`/`(R )` labels are **printed in
  the source**; the parser reproduces them faithfully and normalizes via
  `norm_party`. Re-running the current adapter on these five members reproduces
  the raw table above cell-for-cell (`Holmes`/D 10,766; `Baker`/D 4,862,
  `Chambliss, Jr.`/D 2,020; `Mike Holmes`/REP 178; `Alan Baker`/REP 2,217;
  `Clyde Chambliss, Jr.`/REP 9,639 and 763; `Chambliss, Jr.`/R 8,050 and
  `Chambliss Jr.`/R 2,444).
- Wide workbooks (`Autauga`, `Baldwin`, `Tallapoosa`) dispatch to `_wide_sheet`
  (lines 132–146), which reads the printed `Party` column directly.

So the corrupted party labels are a **provider (source workbook) defect**, not a
parser invention and not a warehouse edit.

### Stored `vote_observations` (2014; all locators NULL, `build_run_id` NULL)

Every candidate block is stored **twice** (two identical rows per precinct), so
each stored total is exactly 2 × the raw precinct cells:

| contest | stored `candidate_key` | party | county | rows | stored sum | = 2 × raw |
|---|---|---|---|---:|---:|---:|
| HD31 | `HOLMES` | D | ELMORE | 54 | 21,532 | 2 × 10,766 |
| HD31 | `MIKE HOLMES` | R | AUTAUGA | 6 | 356 | 2 × 178 |
| HD66 | `BAKER` | D | ESCAMBIA | 46 | 9,724 | 2 × 4,862 |
| HD66 | `ALAN BAKER` | R | BALDWIN | 30 | 4,434 | 2 × 2,217 |
| SD30 | `CHAMBLISS JR` | R | ELMORE | 42 | 16,100 | 2 × 8,050 |
| SD30 | `CHAMBLISS JR` | R | CHILTON | 16 | 4,888 | 2 × 2,444 |
| SD30 | `CHAMBLISS JR` | **D** | COOSA | 28 | 4,040 | 2 × 2,020 |
| SD30 | `CLYDE CHAMBLISS JR` | R | AUTAUGA | 40 | 19,278 | 2 × 9,639 |
| SD30 | `CLYDE CHAMBLISS JR` | R | TALLAPOOSA | 16 | 1,526 | 2 × 763 |
| SD30 | `BRYAN MORGAN` / `MORGAN` / `MORGAN IND` | O | AUTAUGA / ELMORE / CHILTON / COOSA / TALLAPOOSA | 40 / 21+21 / 14+14 / 8+8 / 16 | 3,868 / 2,326×2 / 806×2 / 349×2 / 476 | (independent, also duplicated) |

Note the intra-county key split: the same `Elmore`/`Chilton`/`Coosa` independent
column appears under both `MORGAN` and `MORGAN IND`, which is additional evidence
that the legacy 2014 ingest read each file through more than one code path (or
more than once). The legacy `load_sos_year` prefers the archive over the extracted
directory, so the duplication is not explained by that branch alone; it is not
resolved here.

### Canonical, official-consolidated link, and downstream

| contest | canonical row | votes | `canonical_source` |
|---|---|---:|---|
| 2014 house 31 | R `Mike Holmes` (`AL-2014-house-31-R-MIKE-HOLMES`) | 10,944 | `official_consolidated_candidate_results` |
| 2014 house 66 | R `Alan Baker` (`AL-2014-house-66-R-ALAN-BAKER`) | 7,079 | `official_consolidated_candidate_results` |
| 2014 senate 30 | R `Clyde Chambliss, Jr.` (`AL-2014-senate-30-R-CLYDE-CHAMBLISS-JR`) | 22,916 | `official_consolidated_candidate_results` |

- The canonical figures come from `data/processed/war/race_candidate_results.csv`
  (196 rows for 2014), produced by `scripts/build_war_database.py`'s
  `race_tables` consolidation: surname-only fragments (single-token names such as
  `Holmes`, `Baker`, `Chambliss, Jr.`) are reattached to the full-name record's
  candidate and party within the same race, and `oe_normalize.load_oe` drops the
  county summary rows (`CALCULATED TOTALS` / `REPORTED TOTALS`). The single-token
  match is what removes the mis-printed `(D)` labels; the summary-row filter is
  what removes the duplication in the OpenElections input.
- **Verification:** the three canonical totals equal the sum of the *distinct*
  raw precinct cells of the registered 2014 SOS ZIP exactly (10,944 / 7,079 /
  22,916). The internal printed discrepancy in Escambia HD66
  (`CALCULATED 4,862` vs `REPORTED 5,293`) does **not** enter the canonical total.
- Because canonical has no D row for these races, `canonical_cmo_features.csv`
  records `contest_status='unopposed_republican'`, `dem_votes=0`,
  `rep_votes=10,944 / 7,079 / 22,916`, `legislative_dem_margin=-100`,
  `war_eligible=False`. They are **not** in the 509-race universe and have no
  `race_war.csv` row (`cmo_v5_races.csv` 2014 excludes house 31, house 66 and
  senate 30).
- No registered 2014 certified canvass exists to compare against; the SOS
  precinct ZIP is the official 2014 record in this repository.

### Finding

> **The 2014 HD31/HD66/SD30 party corruption is a provider-printed defect
> (`Holmes (D)` in Elmore, `Baker (D)` in Escambia, `Chambliss, Jr. (D)` in Coosa)
> compounded by a legacy ×2 duplication in `vote_observations`; the canonical
> layer is correct and equals the distinct SOS precinct sums, and all three races
> are (correctly) unopposed-Republican and excluded from the 509-race universe.**

### Disposition options (not selected)

**C1 — Leave canonical and the WAR universe as they are; record the
`vote_observations` defect as a source-preservation note.**
The corrupted rows are *source observations* the warehouse is required to
preserve; no product consumes them for these three races. Consequence: no
numeric change anywhere; precinct-level consumers and any future
`build_candidate_identity.py` run over the repaired/locator columns should be
warned that these three contests carry mislabelled and duplicated rows. Evidence
needed: a decision that the legacy 2014 duplication is a preservation artifact,
not a defect to repair, plus a documented consumer warning.

**C2 — Repair the legacy 2014 rows in `vote_observations` (remove the duplicate
precinct blocks; correct the three `(D)` labels to R per the official precinct
records).**
Consequence: `vote_observations` row counts for 2014 drop (the scoped ×2
duplication is eliminated); the source-observation layer no longer reflects the
raw workbook verbatim, so the repair must be an auditable adjudication with a
before-image, reviewer status and a build run, mirroring the Morgan-1994
pattern. Rebuild of `canonical_candidates`/features is **not** required for these
races (canonical already uses the official consolidated figures), but the
`qa_vote_observation_quality` collision census would change and the 2014
sources' claimed preservation would need restating. Evidence needed: a scoped
census of the 2014 duplication (not limited to these three races), a decision on
whether provider-printed labels or the official consolidated result are
authoritative for party, and confirmation the defect affects no in-universe race.

**C3 — Quarantine the three contested 2014 contests from any precinct-level
allocation until the duplication is resolved.**
Consequence: any geographic/weight allocation that uses `vote_observations` for
2014 HD31/HD66/SD30 must refuse or flag; `build_canonical_geographic_weights.py`
and its downstream depend on 2014 precinct keys. No WAR change (the races are
already excluded). Evidence needed: a trace of every 2014 precinct-level consumer
and which of them touch these three districts.

**Not established for C:** the exact mechanism of the ×2 duplication (two code
paths vs a double read); whether the legacy 2014 duplication affects other
contests (it almost certainly does, since the pattern is per-candidate-block, but
this packet only verified these three races); and whether the printed `(D)`
labels are a vendor error or reflect a real (e.g. cross-filed) candidacy. Also
not established: whether `REPORTED TOTALS 5,293` in Escambia HD66 contains a
legitimate correction that the canonical 4,862 discards.

---

## Query log (exact statements)

All SELECTs, read-only connection, `PRAGMA query_only=ON`. Representative set:

```sql
-- Case A: the two sets
SELECT source_file, source_sheet, candidate_key, party_norm, sum(votes), count(*)
FROM vote_observations
WHERE year=2002 AND office='State House' AND district=26
GROUP BY source_file, source_sheet, party_norm, candidate_key;
-- 4 rows: 2 NULL-source (DEKALB) + 2 MARSHALL

SELECT rowid, county_key, precinct_key, candidate_key, party_norm, votes,
       source_file, source_sheet, source_row, source_column, source_file_id, build_run_id
FROM vote_observations
WHERE year=2002 AND office='State House' AND district=26 AND source_file IS NULL
ORDER BY candidate_key, rowid;               -- 154 rows

-- Case A: locator coverage
SELECT source_file, source_sheet, count(*) FROM vote_observations
WHERE year=2002 AND source_file IS NOT NULL GROUP BY 1,2;   -- MARSHALL 2,950 only

-- Case B
SELECT office, district, candidate_key, party_norm, sum(votes), count(*), min(source_row), max(source_column)
FROM vote_observations
WHERE year=2002 AND office='State House' AND district=27
GROUP BY 1,2,3,4;                            -- D 7,724; LIB 662; R 4,789

SELECT district, group_concat(canonical_party), group_concat(canonical_votes)
FROM canonical_candidates WHERE year=2002 AND chamber='house'
GROUP BY district;                           -- 104 districts, no 27

-- Case B: pre-repair backup (read-only)
SELECT count(*) FROM vote_observations WHERE year=2002 AND upper(county_key)='MARSHALL';  -- 4,029
SELECT office, count(*) FROM vote_observations
WHERE year=2002 AND upper(county_key)='MARSHALL' GROUP BY office;   -- MARSHALL 4,029
SELECT count(*) FROM vote_observations
WHERE year=2002 AND office IN ('State House','State Senate') AND district=27;  -- 0

-- Case C
SELECT office, district, candidate_key, party_norm, county_key, count(*), sum(votes)
FROM vote_observations
WHERE year=2014 AND ((office='State House' AND district IN (31,66))
                  OR (office='State Senate' AND district=30))
GROUP BY 1,2,3,4,5;

-- Build runs / registry
SELECT build_run_id, target, started_at_utc, completed_at_utc, status, code_commit
FROM warehouse_build_run WHERE target IN
 ('election_source_layer','canonical_candidate_identity','source_quality_repair_2026_09_05');
```

Raw evidence was read with `xlrd 2.0.2` (the 2002 `.xls`) and `openpyxl 3.1.5`
(the 2014 `.xlsx` members, read from the ZIP in memory), and cross-checked by
re-running `scripts/sos_precinct._legacy_2002` / `normalize_workbook` for 2014.

## What is NOT established (packet-level)

1. No owner disposition is selected; this packet does not authorize any change.
2. The full blast radius of the 2002 Marshall parse defect on other legislative
   districts (Marshall contributes HD26; the workbook also contains HD25/HD27 and
   other county splits) is not enumerated here.
3. The full blast radius of the 2014 legacy duplication across all contests is
   not enumerated; only HD31/HD66/SD30 were verified.
4. The 2014 HD66 Escambia `REPORTED TOTALS` (5,293) vs `CALCULATED TOTALS`
   (4,862) contradiction is not adjudicated.
5. No claim is made that the canonical/official-consolidated figures are
   themselves certified by a 2014 canvass — none is registered.
6. `warehouse-08` provenance limits remain: most `vote_observations` rows carry
   no physical locators (2002: 2,950 of 180,723; 2014: 11,059 of 184,714), so
   several raw-cell attributions in this packet rest on registered-source +
   value/name identity rather than stored locators. Those are marked where used
   (Case A DEKALB set, Case C 2014 sets).
7. No downstream rebuild, model re-run, publication or release gate was touched.

## Out-of-scope findings (evidence, not acted on)

- `qa_vote_observation_quality` (recreated by the 2026-09-05 repair) still
  exposes the collision census; the 2014 duplication is not separately flagged in
  it as a duplicate-block condition distinct from a natural-key collision.
- The registered OpenElections 2014 CSV itself contains the duplicated blocks and
  the summary rows; `load_oe`'s summary-row filter is the only guard, and
  `build_war_database.py` special-cases 2014 Jefferson replacement. This is a
  latent risk for any consumer that reads that CSV without `load_oe`.
- The 2002 legacy ingest (`RUN-16A85CF9DA9E4233A55619147EE1ED4C`) predates the
  locator columns; its target has run once and is not idempotent with the
  post-repair adapter, so re-running `build_election_database.py` would need its
  own review.
