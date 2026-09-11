# Forecast 2024 baseline certification — 2026-09-11

Task `FORECAST-2024-BASELINE-CERTIFICATION-20260911` (checklist `forecast-03`:
"Certify the 2024 baseline on the 2026 plans"). Read-only audit; no builders were
run, no published export was written, no warehouse write was performed. All
warehouse reads used `sqlite3.connect('file:data/processed/elections/alabama_elections.sqlite?mode=ro', uri=True)`
with `PRAGMA query_only=ON` and bounded queries. Lineage pinned to HEAD
`d93dd8c6` (`.git/refs/heads/master`), forecast build
`b76d607f2d81e54697a3` (manifest `git_commit` `55b7734bb118c08f153b745a448375acca1ec018`),
warehouse run `RUN-DFB1D093D7594AB68A264292050E924D`; Alabama historical
`AL-HIST-WAR-V1-44F191EB8D939EF062CC`; Southern v3 `WAR-POST2016-V3-530FBD4238CC483E557C`.

Scope: the 2024 presidential baseline as consumed by the 2026 Alabama forecast
(`baseline_2024_pres_dem_margin`), for every 2026 seat on the plan the forecast
and dashboard use. Observed 2024 election facts, the reconstructed
precinct-to-district allocation, and the model's own uncertainty are kept
distinct below.

## 1. Lineage

The published baseline value is produced by two stages beneath the forecast
builder. `run_alabama_war_generic_forecast.py` reads
`2026_poll_adjusted_baseline.csv`; `build_2026_poll_adjusted_baseline.py` copies
`2026_district_presidential_features.csv.pres_2024_dem_margin` unchanged into
`baseline_2024_pres_dem_margin` (plus a uniform national swing for the separate
`poll_adjusted_dem_margin`, which the published forecast does not use);
`build_2026_geographic_features.py` builds the features file from the official
2024 precinct results and the 2026 plan geometry.

| Stage | Path | Producer (script) | mtime (UTC) | sha256 | Rows |
|---|---|---|---|---|---|
| 2024 precinct votes + geometry | `data/raw/rdh/al_2024_gen_prec.zip` → `al_2024_gen_all_prec/al_2024_gen_all_prec.{shp,dbf}` (extracted at `data/raw/alabama_elections_and_geography/al_2024_gen_prec/al_2024_gen_all_prec/`) | external (Redistricting Data Hub) | 2026-08-16 23:54 | zip not hashed here; `.shp` `3376d310…d665`, `.dbf` `000ab3f1…e137c` | 1,947 precincts |
| 2020 tabulation blocks | `data/raw/census/tl_2020_01_tabblock20.zip` | external (U.S. Census Bureau) | 2026-08-14 23:46 | `86e554ba…2186c` | 185,976 blocks (AL) |
| 2020 PL 94-171 block population | `data/raw/census/al2020.pl.zip` | external (U.S. Census Bureau) | 2026-08-14 21:00 | `bd3fbbf2…7cd77` | — |
| 2026 House plan | `data/raw/alabama_elections_and_geography/tl_2025_01_sldl/tl_2025_01_sldl.{shp,dbf}` | external (TIGER/Line 2025) | 2026-08-14 23:44 | `.shp` `f2840e15…23333`, `.dbf` `d1b77402…c10b65` | 105 |
| 2026 Senate plan | `data/raw/alabama_elections_and_geography/tl_2025_01_sldu/tl_2025_01_sldu.{shp,dbf}` | external (TIGER/Line 2025) | 2026-08-14 23:44 | `.shp` `fbc44220…012b8`, `.dbf` `1fab9ba4…ea534d` | 35 |
| Precinct→district weights | `data/processed/war/2026_geographic_precinct_district_weights.csv` | `scripts/build_2026_geographic_features.py` (`84a43b23…` sha) | 2026-08-14 23:54 | `da7ff150…132070` | 4,546 |
| Crosswalk QA | `data/processed/war/2026_geographic_crosswalk_qa.csv` | same | 2026-08-14 23:54 | `95b73464…d451697` | 2 |
| Plan source manifest (local) | `data/processed/war/2026_geography_source_manifest.csv` | same | 2026-08-16 15:21 | `87674816…e060893` | 14 |
| **District 2024 features** | `data/processed/presidential/2026_district_presidential_features.csv` | same | 2026-08-14 23:54 | `4e7fc286…32a83` | **140** |
| Poll-adjusted baseline | `data/processed/war/2026_poll_adjusted_baseline.csv` | `scripts/build_2026_poll_adjusted_baseline.py` (`9867f5ce…`) | 2026-08-19 04:57 | `eb730a46…37b9f` | 140 |
| Scenarios export | `data/processed/forecast_calibration/alabama_war_forecast_v1_2026_scenarios.csv` | `scripts/run_alabama_war_generic_forecast.py` (`19e6cf0d…`) | 2026-09-11 21:08 | `c0e33afc…6b5abb1` | 144 (48×3) |
| Forecast manifest | `data/processed/forecast_calibration/alabama_war_forecast_v1_manifest.json` | same | 2026-09-11 21:08 | `6760a36d…a54536c` | — |
| Error components | `data/processed/forecast_calibration/robust_forecast_v1_error_components.csv` | `scripts/run_robust_forecast_pipeline.py` | 2026-08-23 01:54 | `4085d289…eef5d68` | 1 |

The published forecast manifest declares only `2026_poll_adjusted_baseline.csv`
(sha `eb730a46…`, matched on disk) among the baseline chain; it does **not**
declare the district features file, the weights file, or the raw precinct/plan
sources. The features file is declared by hash only in the separate research
manifest `robust_forecast_v1_manifest.json` (sha `4e7fc286…`, matched on disk).

**Producer-revision caveat:** the current `build_2026_geographic_features.py`
mtime (2026-08-16 15:15) postdates the features/weights outputs (2026-08-14
23:54), and there is no `warehouse_build_run` row for this crosswalk (it writes
CSVs only). The exact script revision that produced the published features file
is therefore not recorded; the two files were not regenerated together with the
later-run source manifest (2026-08-16 15:21).

## 2. Registered raw sources (read-only `warehouse_source_file`)

| Source id | Local path | URL | Retrieved (UTC) | Terms | Scope |
|---|---|---|---|---|---|
| `CENSUS-2020-AL-TABBLOCK20` | `data/raw/census/tl_2020_01_tabblock20.zip` | `https://www2.census.gov/geo/tiger/TIGER2020PL/STATE/01_ALABAMA/01/tl_2020_01_tabblock20.zip` | 2026-08-14T23:46:02Z | "U.S. Census Bureau public data; TIGER/Line attribution required" | statewide TIGER/Line 2020 Census block polygons |
| `SRC-58F03B523F0C2DAD7D7D` | `data/raw/census/al2020.pl.zip` | `https://www2.census.gov/programs-surveys/decennial/2020/data/01-Redistricting_File--PL_94-171/Alabama/al2020.pl.zip` | **not recorded** | **not recorded** | PL 94-171 2020 block population |
| `SRC-E603613A507B7FFA6C25` | `data/raw/alabama_elections_and_geography/2024-General Precinct Level Results.zip` | **not recorded** | 2026-08-16T19:15:03Z | **not recorded** | official vote counts (SOS; no shapefile members — not the file consumed here) |

Not registered in `warehouse_source_file` (verified: `%gen_prec%`, `%tl_2025%`,
`%rdh%` return no matching local path):

- **The 2024 precinct source actually consumed** — `data/raw/rdh/al_2024_gen_prec.zip`
  (its `.shp` member sha `3376d310…d665` equals the extracted shapefile the builder
  reads). Its embedded `README.txt` records RDH retrieval 04/21/25, sources the
  Alabama Secretary of State and county GIS/records, and states that county-level
  (and Jefferson Judicial Division) votes are allocated to precincts by each
  precinct's share of election-day votes; counties not individually listed use the
  Alabama 2022 precinct file, which draws on the 2020 file. No registry URL,
  retrieval timestamp, or license row exists for this archive.
- **The 2026 plans** — `tl_2025_01_sldl` / `tl_2025_01_sldu`. They are recorded
  only in the local `2026_geography_source_manifest.csv` (per-component sha256,
  `applicable_cycle=2026`, `legislative_session_year=2024`,
  `selection_basis=user_supplied_reinstated_original_2021_plan`), not in the
  warehouse registry. Their hashes match on disk.

For parity, the warehouse separately holds `NYT-NATIONAL-2024-PRES-PRECINCT-RESULTS`
(1,945 AL precinct rows, method `provider_reported_precinct_official_boundary`)
with 2024 statewide totals D 772,335 / R 1,461,592 — 77 D and 1,024 R below the
RDH source used here. The forecast baseline does not consume that source.

## 3. Source totals and vote conservation

Source: the RDH 2024 precinct shapefile (`G24PREDHAR` Dem, `G24PRERTRU` Rep),
1,947 precincts, 67 counties, no null vote cells.

| | Dem votes | Rep votes | Two-party | Dem margin |
|---|---|---|---|---|
| Statewide source (RDH 2024 precinct file) | 772,412 | 1,462,616 | 2,235,028 | −30.88122385938789% |
| Features — House (105 districts) | 772,412 | 1,462,616 | 2,235,028 | — |
| Features — Senate (35 districts) | 772,412 | 1,462,616 | 2,235,028 | — |

Conservation difference (allocated district sum − statewide source total):

| Chamber | Dem diff | Rep diff |
|---|---|---|
| House (105) | **0.0** | **0.0** |
| Senate (35) | **0.0** | **0.0** |

Each precinct's weights sum to 1.0 within each chamber (max weight-sum error
3.33e-16; QA file reports `max_weight_sum_error=0.0` for both chambers), and all
1,947 precincts appear in each chamber's weights (no precinct dropped), so the
per-chamber totals recover the statewide source total exactly. Every seat is
assigned a value on the 2026 plan; no seat falls back to a statewide or
prior-plan number.

## 4. Per-seat allocation method and fallback

Allocation is a modeled reconstruction, not an observed district total. The
method label on all 4,546 weight rows is
`2020_block_population_to_2025_tiger_sld`: 2020 census block representative
points are assigned to 2026 SLD polygons, and each precinct's votes are split
across the districts its blocks fall in, weighted by 2020 block population
(not turnout). Because the 2026 plan differs from the 2024 precinct geography,
there is no "reported single-district precinct total" anywhere — every seat value
is this block-population-weighted allocation.

| Measure | House | Senate | Total |
|---|---|---|---|
| Seats | 105 | 35 | 140 |
| Seats containing ≥1 split precinct | 100 | 33 | **133** |
| Whole-precinct-only seats | 5 | 2 | 7 |
| Seats with `pres_2024_fallback_share > 0` | 0 | 0 | **0** |
| Mean split share of allocated votes | 0.2105 | 0.0964 | — |
| Max split share of allocated votes | 0.8468 | 0.2874 | — |

- Whole-precinct-only seats: House 31, 42, 67, 74, 92; Senate 4, 23.
- Highest split shares: House 79 (0.8468), House 32 (0.7084), House 73 (0.6477).
- Split precincts (weight < 1 in ≥1 district): 405 in the House geometry, 169 in
  the Senate geometry, 461 unique precincts overall; 574 precinct-district-pair
  groupings span >1 district; 303 of 4,546 weight rows are zero-population rows.

**Fallback share is hardcoded, not measured.** `build_2026_geographic_features.py`
computes a `precinct_snap_fallback` mask for blocks whose representative point
does not fall inside a precinct (also silently dropping blocks whose point lands
in a different county's precinct), but the mask is never carried into the
weights or features export; the features file sets
`pres_2024_fallback_share = 0.0` and `pres_2024_source_complete = True` as
constants for all 140 rows. The "0 seats with fallback" result is therefore a
property of the code, not a measurement. Source completeness is independently
consistent (0 null vote cells; all 1,947 precincts allocated), but the fallback
rate itself is unmeasured.

## 5. Target district plan

- Files: `tl_2025_01_sldl` (105) and `tl_2025_01_sldu` (35), TIGER/Line 2025
  SLD, attribute `LSY = "2024"`. `build_2026_geographic_features.py` raises
  unless the loaded counts are exactly 105/35 and `LSY == {"2024"}`.
- District set of the features file equals the plan's `SLDLST`/`SLDUST` set
  exactly (House 1–105 complete, Senate 1–35 complete; no duplicates).
- The dashboard (`build_2026_forecast_dashboard.py`) uses the same two `.shp`
  paths (`tl_2025_01_sldl` / `tl_2025_01_sldu`) for geometry and reads
  `2026_poll_adjusted_baseline.csv.baseline_2024_pres_dem_margin` as the
  displayed `pres24`. So the baseline plan and the display plan are the same.
- The local plan manifest labels this plan `applicable_cycle=2026`,
  `legislative_session_year=2024`, `selection_basis=user_supplied_reinstated_original_2021_plan`.
- No 2020- or 2022-plan value is substituted: the published forecast reads only
  `2026_poll_adjusted_baseline.csv` (not the separate
  `2022_district_presidential_features.csv`, which the research manifest lists
  separately). Every feature row carries `cycle = 2026`.

Not established here: whether this TIGER/Line 2025, `LSY 2024` boundary set is
legally byte-identical to the district plan under which the 2024 presidential
votes were cast, and whether the "reinstated original 2021 plan" label matches
the plan actually in force for 2026. That plan-vintage adjudication belongs to
the separate plan-certification task; this audit certifies only that the baseline
is built on the same plan the forecast and dashboard use.

## 6. Uncertainty carried by the allocation, and propagation

What the allocation carries:

- **Split-precinct shares:** up to 84.7% of a seat's allocated votes (House 79)
  come from population-weighted splits of precincts that cross district lines;
  mean 21.1% (House) / 9.6% (Senate). The within-precinct distribution is assumed
  uniform (2020 block population as weight), so a seat's baseline can be wrong
  if partisanship is not uniform across the split precinct.
- **Nested upstream allocation:** the RDH source itself allocates some counties'
  county-level (or Jefferson Judicial Division) reported votes to precincts by
  election-day vote share, and uses 2022/2020 precinct boundaries for counties
  not individually re-sourced in 2024 — so the "precinct" inputs are partly
  reconstructed and their boundary vintage is mixed.
- **Snap fallback:** computed but not exported (see §4), so its contribution is
  unknown.

Does the forecast propagate it? **No.** The chamber simulation adds four
components from `robust_forecast_v1_error_components.csv`: `national_sd` 2.2038,
`state_sd` 2.0073, `chamber_sd` 1.0251, `district_sd` 5.9057, plus a 6.2516 total
residual SD. The `district_sd` is defined by the producing pipeline as
`row_error − state − chamber` on the historical Southern WAR panel — a
district-level model-residual term added i.i.d. per seat. It is not the
precinct-allocation uncertainty, and no allocation/split-share sensitivity
exists in the bundle. Two registered 2024 sources also disagree slightly
(§2), which the forecast does not reflect.

## 7. Modeled-race baseline reconciliation

48 modeled races (33 House, 15 Senate); scenarios export = 144 rows (48 × 3
scenarios). For all 48, the scenarios `baseline_2024_pres_dem_margin` and
`prior_pres_margin` equal the features file's `pres_2024_dem_margin` exactly
(max abs difference **0.0**). The poll-adjusted baseline's
`baseline_2024_pres_dem_margin` equals the features margin within CSV
round-trip tolerance (max abs difference 3.55e-15 on 2 of 140 rows). The
published forecast does not use the demographic/elasticity columns (they are
dropped as legacy); it uses `baseline_2024_pres_dem_margin` and the uniform
`uniform_poll_adjusted_dem_margin`.

## 8. Observed vs modeled

| Value | Status |
|---|---|
| Statewide 2024 D/R totals 772,412 / 1,462,616 | observed (RDH source), reproduced exactly by allocation |
| 2024 precinct votes (`G24PREDHAR`/`G24PRERTRU`) | observed per precinct, but partly RDH-reconstructed from county totals upstream |
| `pres_2024_dem_votes` / `_rep_votes` / `_margin` per district | **modeled** block-population allocation |
| `pres_2024_fallback_share`, `pres_2024_source_complete` | constant placeholders (0.0 / True), not measurements |
| `national_2024_dem_margin` = −1.48 | external anchor constant, not derived in-repo |
| `poll_adjusted_dem_margin` (demographic) | modeled; **not** used by the published forecast |

## Not established

1. Actual block snap-fallback count/share (mask computed then discarded; feature
   column hardcoded 0.0); the real fallback contribution is unknown.
2. The exact script revision that produced the published features file (outputs
   predate the current builder mtime; no run row).
3. Whether the mixed 2022/2020/2024 precinct boundary vintages in the RDH layer
   are consistent with the votes attributed to them.
4. RDH's county→precinct allocation fractions (not re-derived here).
5. Whether the `tl_2025` `LSY 2024` plan is legally identical to the plan in
   force for the 2024 votes / 2026 election (separate plan-cert task).
6. Any propagation of allocation uncertainty (none exists), and any reconciliation
   of the 77 D / 1,024 R gap to the NYT-source totals.

## Out-of-scope findings (not acted on)

- `build_2026_geographic_features.py` computes `precinct_snap_fallback` and then
  discards it; `pres_2024_fallback_share`/`pres_2024_source_complete` are
  hardcoded. Latent provenance defect (a source-repair/feature change, not an
  audit repair).
- The cross-county block filter silently drops blocks whose representative point
  lands in another county's precinct.
- The published forecast manifest does not declare the baseline chain below
  `2026_poll_adjusted_baseline.csv`, so the raw precinct/plan provenance is not
  carried into the published build metadata.
- `2026_poll_adjusted_baseline.csv.status` is
  `catalist_yougov_demographic_transfer_selected` even though the published
  forecast uses the uniform environment and drops the legacy demographic columns.

## Reproduction commands

- Hash/mtime table: `hashlib.sha256(path.read_bytes())` and `path.stat().st_mtime`
  over the §1 paths.
- Conservation and allocation shares: read
  `2026_district_presidential_features.csv`, `2026_geographic_precinct_district_weights.csv`,
  and the precinct `.shp` attributes (`ignore_geometry=True`); sum
  `(G24PREDHAR+G24PRERTRU)*allocation_weight` grouped by chamber/district;
  compare to `G24PREDHAR.sum()` / `G24PRERTRU.sum()`.
- Registered sources:
  `SELECT source_file_id, local_path, original_url, retrieved_at_utc, sha256, license FROM warehouse_source_file WHERE local_path LIKE '%…%'`.
- Plan district sets: `geopandas.read_file(<tl_2025 … .shp>)`, compare
  `SLDLST`/`SLDUST` sets and `LSY` to the features district sets.

JSON companion: `FORECAST_2024_BASELINE_CERTIFICATION_2026_09_11.json`.
