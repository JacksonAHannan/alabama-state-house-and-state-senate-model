# Forecast polling/environment snapshot and refresh policy

Dated audit (`forecast-04`), generated 2026-09-11T14:59Z. Companion machine
record: `FORECAST_POLLING_SNAPSHOT_POLICY_2026_09_11.json`.

Scope: inventory the polling/environment inputs of the published forecast build
`368bb272a990ff436e56` (`scripts/run_alabama_war_generic_forecast.py`), document
the eligibility/weighting/cutoff logic exactly as implemented, and propose a
refresh/freeze policy with a reproducible command sequence. This audit **does
not download, refresh, or rebuild anything** and does not adjudicate sources; it
records evidence and options. No file outside the two audit paths was written.

## 1. What was checked, and how

| Check | Command / path | Result |
|---|---|---|
| Declared forecast inputs | read `data/processed/forecast_calibration/alabama_war_forecast_v1_manifest.json` | 9 `inputs[]` entries; 1 under `data/processed/polling/` |
| Scenario poll fields | `pandas.read_csv("data/processed/forecast_calibration/alabama_war_forecast_v1_2026_scenarios.csv")` | 6 `poll*` fields, all carrying as-of `2026-08-17` |
| Baseline environment | read `data/processed/war/2026_poll_adjusted_baseline.csv` | 140 rows, all as-of `2026-08-17`, `poll_staleness_days_at_download=1` |
| Registered sources | read-only SQL on `data/processed/elections/alabama_elections.sqlite` (`file:...?mode=ro`, `PRAGMA query_only=ON`): `SELECT provider, local_path, original_url, retrieved_at_utc, sha256, license, extraction_status FROM warehouse_source_file WHERE local_path LIKE '%poll%'` | 9 rows: 8 `pollster_document` raw PDFs/XLSX (all `license IS NULL`) + 1 unrelated Arkansas SOS file whose name contains "Polling" |
| Raw polling files registered? | exact-path `SELECT ... WHERE local_path=?` for each raw polling file | `fivethirtyeight_raw_polls.csv`, `nate_silver_pollster_ratings.csv`, `votehub_generic_ballot_catalog.json`, `votehub_crosstabs_reviewed.csv`, the two `generic_ballot_environment/*.csv`: **NOT REGISTERED** |
| Hashes | `hashlib.sha256(path.read_bytes())` for 24 processed/raw polling paths | recorded in the companion JSON |
| Code | full read of `run_alabama_war_generic_forecast.py`, `build_2026_poll_adjusted_baseline.py`, `build_silver_bplus_polling_environment.py`, `download_votehub_generic_ballot.py`, `build_historical_silver_generic_ballot.py`, `build_silver_pollster_quality_gate.py`, `build_votehub_crosstab_source_inventory.py`, `download_recent_silver_poll_assets.py`, `refresh_yougov_generic_ballot.py`, `run_robust_forecast_pipeline.py`, `refresh_2026_forecast.py`, `build_2026_forecast_dashboard.py` | logic quoted below |

## 2. Tier 1 — inputs the forecast build actually reads

The manifest declares **one** polling input directly and two more
polling-derived inputs outside `data/processed/polling/`. All three are also
declared by `sha256` in `inputs[]`.

### 2.1 `data/processed/polling/historical_silver_a_generic_ballot_cycles.csv`

| Field | Value |
|---|---|
| Role | Historical election-day national environment for the 2018/2022 forward test; also the sole source of `national_sd` (pooled `poll_error` SD) |
| Forecaster use | `historical_panel()` filters `cycle ∈ {2018, 2022}`; `final_poll_margin` → `generic_ballot_environment_margin`; `poll_implied_national_swing` → `environment_ticket_change` |
| Manifest declaration | `inputs[]` entry, sha256 `52e4ab48342c5550b4ecb1d146914a4120c777d4b888f4cbae88d32684817010` |
| Hash / size / mtime | same; 1,883 B; 2026-08-17T18:01:21Z |
| Rows | 7 (cycles 1998, 2002, 2006, 2010, 2014, 2018, 2022); 2018 and 2022 consumed |
| Acquisition script | `scripts/build_historical_silver_generic_ballot.py` |
| Upstream raw inputs | `data/raw/polling/fivethirtyeight_raw_polls.csv`; `data/raw/polling/nate_silver_pollster_ratings.csv` |
| Manifest / registration | none in `data/processed/polling/`; not in `warehouse_source_file` |
| Source URL | unknown (no acquisition record for either raw input) |
| Retrieval time | unknown (no acquisition record; local mtime proxy 2026-08-17T17:56Z and 2026-08-15T06:53Z) |
| As-of date | election day per cycle by construction; latest poll dates 2018-11-02 and 2022-11-06 |
| License / terms | unknown |
| Current staleness | not applicable — a frozen historical election-day panel, not a live environment |

Used-cycle values: 2018 final poll D+8.88 (5 A-rated pollsters, actual D+8.51,
poll error +0.37); 2022 final poll D−1.97 (8 pollsters, actual D−2.64, poll
error +0.67). `national_sd` = the SD (ddof=1) of all seven `poll_error` values
= **2.20385**.

Rating policy recorded in-file: `current_2026_silver_A_plus_A_A_minus_survivorship_screen`.
The 1998–2022 panel is therefore built by applying **today's** Silver A-range
ratings retroactively — a documented survivorship screen, not a contemporaneous
rating snapshot.

### 2.2 `data/processed/war/2026_poll_adjusted_baseline.csv`

| Field | Value |
|---|---|
| Role | Live national environment mapped onto all 140 districts; supplies `votehub_2026_dem_margin`, `national_dem_swing_2024_2026`, `uniform_poll_adjusted_dem_margin`, `poll_average_as_of`, `poll_staleness_days_at_download` |
| Forecaster use | `prospective_features()`: `generic_ballot_environment_margin = votehub_2026_dem_margin`; `environment_baseline_margin = uniform_poll_adjusted_dem_margin`; `environment_ticket_change = national_dem_swing_2024_2026` |
| Manifest declaration | `inputs[]`, sha256 `eb730a46c6ea2ef02ccc26fc03bc833fb2747c076196d6ac477fc06b88837b9f` |
| Hash / size / mtime | same; 35,663 B; 2026-08-19T04:57:29Z |
| Rows | 140 (`cycle=2026`) |
| Builder | `scripts/build_2026_poll_adjusted_baseline.py` |
| Live source | `data/processed/polling/votehub_silver_bplus_topline_environment.csv` (preferred branch; exists, so the VoteHub-API fallback `votehub_generic_ballot_snapshot.csv` is **not** used) |
| Source URL | VoteHub polls API `https://api.votehub.com/polls` (recorded in `scripts/download_votehub_generic_ballot.py`) |
| Retrieval time | the live poll's `retrieved_on` = 2026-08-18 (from `silver_recent_generic_ballot_cells.csv`) |
| As-of date | `poll_average_as_of = 2026-08-17` on all 140 rows |
| Staleness | declared `poll_staleness_days_at_download = 1`; **25 days as of 2026-09-11** |
| License / terms | VoteHub `CC BY 4.0 / VoteHub` — an in-code constant in the downloader, not a verified source-terms record |
| Status column | `catalist_yougov_demographic_transfer_selected` (the demographic branch was present at build time; see §3.3) |
| Registration | not in `warehouse_source_file` |

Values in force: `votehub_2026_dem_margin = +7.554772`; `national_2024_dem_margin
= −1.48`; `national_dem_swing_2024_2026 = +9.034772`; `uniform_poll_adjusted_dem_margin
= pres_2024_dem_margin + 9.034772`.

### 2.3 `data/processed/forecast_calibration/robust_forecast_v1_error_components.csv`

| Field | Value |
|---|---|
| Role | `national_sd = 2.20385` → `environment_dem_favorable` / `environment_rep_favorable` scenario shifts and the national simulation component |
| Forecaster use | `prospective()` shift ±`national_sd`; `simulate()` draws `national ~ N(0, national_sd)` |
| Manifest declaration | `inputs[]`, sha256 `4085d289d65d17b847bad2d314356d70d0ffd5ab3bc72633e1b07aa69eef5d68` |
| Hash / mtime | same; 156 B; 2026-08-23T01:54:33Z |
| Builder | `scripts/run_robust_forecast_pipeline.py` (`error_components()`), which reads the historical cycles file of §2.1 |
| As-of | inherits the §2.1 election-day freeze (2018/2022) |
| License / terms | n/a (derived); upstream terms unknown |

## 3. Implemented eligibility, weighting, and cutoff (exactly as coded)

### 3.1 Current 2026 topline environment — `scripts/build_silver_bplus_polling_environment.py`

1. **Frame** = VoteHub API poll catalog
   (`data/raw/polling/votehub_generic_ballot_catalog.json`, refreshed by
   `build_votehub_crosstab_source_inventory.py`) merged with the manually
   curated supplement `data/processed/polling/silver_recent_generic_ballot_cells.csv`.
2. **Eligibility**: Silver grade in `{A+, A, A−, A/B, B+, B}` (the code column is
   named `b_plus_or_better` and is set from `ELIGIBLE = {"A+","A","A-","A/B","B+","B"}`;
   the file label `minimum_silver_grade=B` is therefore accurate — the column
   name is a compatibility misnomer, not a B+ threshold). Also required:
   `internal` false and `partisan` null.
3. **Window / cutoff**: `as_of = max(end_date)` over the merged frame; the
   window keeps `end_date >= as_of − 59 days` (inclusive 60-day window).
   `as_of` is the latest **poll field date**, never the download/run date.
4. **Deduplication**: sort by `end_date`, keep the last row per
   `silver_pollster` (one poll per rated pollster); supplement rows are
   concatenated after the catalog and therefore win ties.
5. **Weight**: `population_weight × 0.5^(age_days / 21)` with
   `POP = {lv: 1.0, rv: 0.75, a: 0.5}`, missing population → 0.5.
6. **Aggregate**: weighted mean of `dem_pct / (dem_pct + rep_pct)`;
   `dem_two_party_margin = 200 × share − 100`.
7. **Missing data**: no zero fill; a poll missing either share yields NaN share
   and would propagate NaN (see §6, flag P4). Downstream, `prospective_features()`
   raises `RuntimeError` on any NaN in `FEATURES`, so a broken environment fails
   closed rather than becoming zero.

Result in force: as-of `2026-08-17`, D+7.5548, 6 pollsters
(Beacon Research/Shaw & Co. Research, Cygnal, Echelon Insights,
Hart Research Associates/Public Opinion Strategies, Quinnipiac University,
YouGov), 60-day window, minimum grade B.

### 3.2 Historical 2018/2022 environment — `scripts/build_historical_silver_generic_ballot.py`

1. **Frame**: FiveThirtyEight raw polls (`type_simple == "House-G-US"`), cycles
   1998–2022, non-partisan only.
2. **Eligibility**: pollster must match a **current 2026** Silver A+/A/A− rating
   (fuzzy `difflib` match ≥ 0.78, plus explicit `ABC News/The Washington Post →
   The Washington Post` alias). Unmatched pollsters are dropped.
3. **Window**: `days_before_election = electiondate − polldate` in `[0, 21]`.
4. **Deduplication**: latest poll per pollster per cycle.
5. **Weight**: population `{lv: 1.0, rv: 0.8, a: 0.55, v: 0.9}`, default 0.7 —
   a **different table** from §3.1's `{lv 1.0, rv 0.75, a 0.5}`.
6. **Environment** = weighted mean two-party Democratic margin;
   `poll_implied_national_swing = margin − fixed prior presidential margin`
   (`PRIOR_PRES_MARGIN` dict literal in the script).
7. **As-of**: implicit election day (polls within 21 days before it).

### 3.3 How the forecaster consumes it — `scripts/run_alabama_war_generic_forecast.py`

- `SEED = 20260831`, `SIMULATION_DRAWS = 50_000`, `ALPHA = 100.0`,
  specification `decaying_lag`.
- Historical panel: `environment_baseline_margin = prior_pres_margin +
  poll_implied_national_swing` for 2018/2022; the 2022 rows are the advisory
  forward test (MAE 7.651 structural vs 7.072 generic-ballot baseline).
- Prospective: `environment_baseline_margin = uniform_poll_adjusted_dem_margin`
  (**uniform** branch). `poll_adjusted_dem_margin` (the Catalist/YouGov
  demographic branch) is carried in the export but is **not** an input to the
  published WAR forecast; the demographic branch only changes the baseline
  file's `status` string.
- Scenario shifts: `environment_dem_favorable` = headline + `national_sd`,
  `environment_rep_favorable` = headline − `national_sd`.
- `build_id = sha256(sha256(race_war.csv) + sha256(post2016_southern_war_v3/manifest.json)
  + sha256(2026_poll_adjusted_baseline.csv) + sha256(CONTRACT) + spec + features)[:20]`.

### 3.4 Scenarios CSV `poll*` fields

`alabama_war_forecast_v1_2026_scenarios.csv` (144 rows) carries
`poll_average_as_of` (all `2026-08-17`), `poll_staleness_days_at_download`
(all `1`), `poll_adjusted_dem_margin`, `uniform_poll_adjusted_dem_margin`,
`polling_error_adjustment` (`-2.20385`, `0`, `+2.20385`),
`current_national_poll_margin` (all `7.554772`).

### 3.5 Dashboard staleness

`build_2026_forecast_dashboard.py` recomputes
`pollStalenessDays = (build_date − poll_average_as_of).days` at render time and
publishes `pollAsOf`, `buildDate`, and `pollStalenessDays` in the page payload,
plus `polling_environment.csv` (a copy of the topline environment). So the
rendered staleness advances with the render date while the underlying as-of is
fixed — a page rebuilt today would display 25 days.

## 4. Tier 2 — upstream polling lineage files

Raw files are untracked in git; only `silver_recent/*` documents are in the
warehouse registry.

| Path | Role | Raw/hash | Source URL | Retrieval | Terms | Registered |
|---|---|---|---|---|---|---|
| `data/raw/polling/silver_recent/manifest.csv` | manifest of 8 curated docs | 2,458 B `aeed9cf6152e11a1…` | per-row `source_url` | 2026-08-15T07:30:57Z | **unknown** | n/a |
| `data/raw/polling/silver_recent/*.pdf/.xlsx` (8) | curated A-/B+ poll documents | per-row hashes in manifest + warehouse | per-row | 2026-08-15T07:30:57Z | `license IS NULL` → **unknown** | yes (8 `pollster_document` rows) |
| `data/raw/polling/silver_recent/yougov_economist_2026-08-17_81771ca9479c.pdf` | auto-discovered Economist/YouGov topline | 86,438 B `81771ca9479c5745…` | `https://d3nkl3psvxxpe9.cloudfront.net/documents/econtoplines_8q3E3LQ.pdf` | 2026-08-18 | **unknown** | **no** |
| `data/raw/polling/votehub_generic_ballot_catalog.json` | VoteHub API catalog | 5,765 B `6560eb7cd9a4f29a…` | `https://api.votehub.com/polls?poll_type=generic-ballot&from_date=…` | not recorded (mtime 2026-08-19) | **unknown** | no |
| `data/raw/polling/nate_silver_pollster_ratings.csv` | Silver pollster grades | 31,959 B `bbc4d969873902b9…` | **unknown** (`REPOSITORY_LAYOUT.md` maps it from a file named `data-GiFps.csv`) | unknown (mtime 2026-08-15) | **unknown** | no |
| `data/raw/polling/fivethirtyeight_raw_polls.csv` | FTE raw poll records, 1998–2023 | 4,961,378 B `9f0b185506e59117…`; `.sha256` sidecar matches | **unknown** | unknown (mtime 2026-08-17) | **unknown** | no |
| `data/raw/polling/votehub_crosstabs_reviewed.csv` | manually reviewed crosstab cells | 35,367 B `4bf23f4f93bd2aed…` | **unknown** | unknown (mtime 2026-08-15) | **unknown** | no |
| `data/raw/polling/generic_ballot_environment/*.csv` (2) | FTE generic-ballot averages for the Virginia 2019/2023 environment product | `caae521c…`, `3881963f…` | FTE GitHub + commit-pinned archive | 2026-08-31T02:26:35Z | FTE LICENSE URL recorded | no |
| `data/raw/polling/Catalist_What_Happened_2024_Public_National_Crosstabs_2025_05_19.xlsx` | Catalist national demographic estimates | 82,677 B `f76b4e849e772286…` | `https://catalist.us/whathappened2024/` (recorded in builder) | unknown (mtime 2026-08-15) | **unknown** | no |
| `data/processed/polling/historical_silver_a_generic_ballot_polls.csv` | per-poll historical selection | `c88655c65fa14bf8…` | derived (§3.2) | derived | unknown | no |
| `data/processed/polling/historical_silver_a_pollster_crosswalk.csv` | pollster → Silver match | `4bdb2e682f7a4fad…` | derived | derived | unknown | no |
| `data/processed/polling/historical_silver_a_current_2026.csv` | 2026 A-rated snapshot | `631a47a4cd09cc6a…` | derived | derived | unknown | no |
| `data/processed/polling/votehub_silver_bplus_topline_environment.csv` | **live environment used** | 311 B `7c09eb6e37eb9f8c…` | derived from VoteHub catalog | as-of 2026-08-17 | CC BY 4.0 (in-code) | no |
| `data/processed/polling/votehub_silver_bplus_demographic_environment.csv` | demographic branch of the baseline | `b763a884b310d47e…` | derived | as-of 2026-08-17 | CC BY 4.0 (in-code) | no |
| `data/processed/polling/votehub_crosstab_documents_with_silver_grades.csv` | grade crosswalk | 20 rows `7b835edb5144b110…` | derived | 2026-08-21 | unknown | no |
| `data/processed/polling/silver_recent_generic_ballot_cells.csv` | curated + auto poll cells | 23 rows `2a26b20427565c6e…` | mixed | 2026-08-18/19 | unknown | no |
| `data/processed/polling/votehub_crosstab_source_manifest.csv` | 101 discovered source docs | `c3278ea193e04e64…` | per-row | 2026-08-21 | unknown | no |
| `data/processed/polling/votehub_generic_ballot_snapshot.csv` | **fallback** environment (unused today) | as-of 2026-06-30, staleness 45 | VoteHub API | 2026-08-14 | CC BY 4.0 (in-code) | no |
| `data/processed/polling/catalist_national_demographic_master.csv` | Catalist master | 255,555 B `c62f0f8f94cd4f1f…` | `https://catalist.us/…` per-row | unknown | unknown | no |
| `data/processed/polling/yougov_generic_ballot_election_snapshots.csv` | YouGov tracker snapshots | `f0904133b567dcf6…` | per-row `source` | unknown | unknown | no |
| `data/processed/polling/virginia_generic_ballot_environment.csv` (incl. its `source_audits` manifest) | separate Virginia environment product | `db746e2f…` / `7558763e…` | FTE GitHub | 2026-08-31 | FTE LICENSE URL | no |

## 5. Proposed refresh and freeze policy

### 5.1 Authoritative sources and cadence

| Environment component | Authoritative source | Cadence | Refreshable reproducibly? |
|---|---|---|---|
| 2026 live national generic ballot | VoteHub polls API (`https://api.votehub.com/polls?poll_type=generic-ballot`) | weekly during the active forecast window; on demand before publication | yes, **conditional on the API being reachable and returning new field dates** (not attempted here) |
| Curated high-grade poll documents | publisher URLs in `download_recent_silver_poll_assets.py::ASSETS` + auto-discovered Economist/YouGov topline | weekly; the `ASSETS` list is **manual** and must be extended by a human | partially — no discovery mechanism; stale list silently yields no new polls |
| Silver pollster grades | `nate_silver_pollster_ratings.csv` | **freeze** | **no** — no recorded URL, retrieval time, or terms |
| Historical FiveThirtyEight raw polls | `fivethirtyeight_raw_polls.csv` | **freeze** | **no** — no recorded URL, retrieval time, or terms; upstream FTE data publication is not an active feed |
| Catalist national demographics | Catalist "What Happened 2024" workbook | **freeze** to the current workbook vintage; refresh only with a new human-reviewed workbook | no scripted download |
| WAR model inputs (`race_war.csv`, `post2016_southern_war_v3/manifest.json`, roster, incumbency) | WAR pipelines | **unchanged** by a polling refresh | n/a |

Rationale for freezing the last four: they determine the *historical* forward
test, `national_sd`, and the demographic branch. Changing them changes validated
diagnostics, so they need their own re-validation rather than a routine refresh.

### 5.2 As-of cutoff and staleness rule

- Environment `as_of` = `max(end_date)` over eligible polls (already implemented).
- **Accept** for publication when `as_of ≥ build_date − 21 days`.
- **Accept with an explicit `stale_environment` label** when 22–60 days: publish
  only with the label and the recomputed `pollStalenessDays` visible in the page
  and manifest; do not silently re-date.
- **Refuse** to advance the environment when `as_of` is older than 60 days or
  when a refresh returns no new field date: record the attempt and keep the
  previous snapshot. Never interpolate, zero-fill, or back-date.
- A refresh must not change the historical cycles file, the error components'
  *method*, or the WAR inputs.

Current state: as-of 2026-08-17 is **25 days** before 2026-09-11, i.e. in the
"accept with `stale_environment` label" band if published today without a
refresh.

### 5.3 Identity and manifest effect

- A live refresh changes `data/processed/war/2026_poll_adjusted_baseline.csv`
  → **new `build_id`** (that hash is in the build-id preimage) → regenerate the
  forecast manifest. The dashboard's `require_fresh_inputs()` refuses to render
  until every declared input/output hash matches disk, so the rebuild is
  mandatory before any render.
- A change to `historical_silver_a_generic_ballot_cycles.csv` or
  `robust_forecast_v1_error_components.csv` alone would **not** change
  `build_id` (they are only in `inputs[]`, not the preimage) — see flag P2.
- The policy must record the environment identity as the tuple
  `(as_of, poll margin, pollster list, schema) + sha256 of the three Tier-1
  inputs + build_id`, so a same-`build_id` historical change is still visible.

### 5.4 Reproducible command sequence

Polling snapshot only (no download — inventory/metadata and local derivation):

```powershell
python scripts/build_votehub_crosstab_source_inventory.py --from-date <YYYY-MM-DD> --skip-document-downloads
python scripts/build_silver_pollster_quality_gate.py
python scripts/refresh_yougov_generic_ballot.py
python scripts/build_silver_bplus_polling_environment.py
python scripts/build_2026_poll_adjusted_baseline.py
```

Full refresh (adds document downloads and the downstream forecast chain):

```powershell
python scripts/build_votehub_crosstab_source_inventory.py --from-date <YYYY-MM-DD> --download --workers 8
python scripts/build_silver_pollster_quality_gate.py
python scripts/refresh_yougov_generic_ballot.py
python scripts/build_silver_bplus_polling_environment.py
python scripts/build_2026_catalist_yougov_transfer.py
python scripts/build_2026_poll_adjusted_baseline.py
python scripts/run_robust_forecast_pipeline.py
python scripts/run_alabama_war_generic_forecast.py
.venv/Scripts/python.exe -m pytest --testmon --testmon-noselect -p no:cacheprovider scripts/tests/test_alabama_war_generic_forecast.py -q
python scripts/build_2026_forecast_dashboard.py --artifact-only
```

Mapping to `CANONICAL_PIPELINES.md` ("polling snapshot per the refresh policy →
`run_alabama_war_generic_forecast.py` → test → `build_2026_forecast_dashboard.py`"):
the refresh step above is exactly the first five/six commands; the documented
product route resumes at `run_alabama_war_generic_forecast.py`. Pass
`--artifact-only` for a candidate; omit it **only** to publish `docs/index.html`
(separate authorization required). `scripts/refresh_2026_forecast.py` bundles
the same polling steps plus the *robust* tournament/dashboard chain but does
**not** run `run_alabama_war_generic_forecast.py` (flag P1).

### 5.5 What must be re-run vs must not change

Re-run after a live environment refresh: `build_silver_bplus_polling_environment.py`,
`build_2026_poll_adjusted_baseline.py`, `run_robust_forecast_pipeline.py`
(only if the historical cycles file changed — otherwise its output is unchanged),
`run_alabama_war_generic_forecast.py`, `build_2026_forecast_dashboard.py`.

Must NOT change: `data/raw/polling/fivethirtyeight_raw_polls.csv`,
`nate_silver_pollster_ratings.csv`, the Catalist workbook, the WAR training
warehouse/run (`RUN-504CE4C4DF904D88A5A40D268F3FCEAB`),
`data/processed/war/alabama_war_v1/`, and the approved Southern v3 lineage.
Refreshing any of these changes validated diagnostics and requires its own
review, not a polling refresh.

## 6. Flags

- **P1 — the packaged refresh script omits the WAR forecast rebuild.**
  `scripts/refresh_2026_forecast.py` refreshes the environment and rebuilds the
  robust chain but not `run_alabama_war_generic_forecast.py`; since it changes
  `2026_poll_adjusted_baseline.csv`, a following dashboard render would be
  refused by `require_fresh_inputs()`. Either insert the forecast script or
  document that the packaged script is not the forecast-product refresh path.
- **P2 — `build_id` does not cover two Tier-1 polling inputs.**
  `historical_silver_a_generic_ballot_cycles.csv` and
  `robust_forecast_v1_error_components.csv` are declared by hash but excluded
  from the build-id preimage. Options: (a) add their hashes to the preimage
  (code change, needs a forecast rebuild), or (b) keep the build-id scheme and
  make the *environment identity* the declared input-hash tuple. Not adjudicated
  here.
- **P3 — inconsistent population weights across the two environment builders.**
  Current environment `{lv 1.0, rv 0.75, a 0.5}`; historical environment
  `{lv 1.0, rv 0.8, a 0.55, v 0.9}` (default 0.7). Either document this as
  intentional (different source population labels/vintages) or unify it.
- **P4 — no NaN guard on a poll with one missing share.** `build_silver_bplus_polling_environment.py`
  computes `share = dem/(dem+rep)` without a denominator check; a poll with only
  one party present would yield NaN and propagate. Mitigated downstream
  (the forecast raises on NaN), but the topline environment would silently
  become NaN. Recommend an explicit drop-and-count.
- **P5 — missing terms for every non-FTE polling raw source.** The eight
  `silver_recent` documents carry `license IS NULL` in `warehouse_source_file`;
  `fivethirtyeight_raw_polls.csv`, `nate_silver_pollster_ratings.csv`,
  `votehub_generic_ballot_catalog.json`, `votehub_crosstabs_reviewed.csv`, the
  Catalist workbook, and the YouGov/Economist topline have no recorded terms.
  The VoteHub `CC BY 4.0` string is an in-code constant, not a verified record.
- **P6 — two polling raw files cannot be refreshed reproducibly at all**
  (no URL, retrieval time, terms, or acquisition script): the FTE raw polls and
  the Silver ratings. They feed the historical forward test and `national_sd`.
- **P7 — the historical rating screen is survivorship-biased by construction**
  (2026 A-range ratings applied to 1998–2022 polls). It is labeled in-file, but
  the policy must state that this panel is frozen and not "refreshed" as if it
  were a live environment.
- **P8 — curated document list is manual.** `download_recent_silver_poll_assets.py::ASSETS`
  is a hardcoded list; `refresh_yougov_generic_ballot.py` only auto-discovers
  the Economist/YouGov page. A weekly cadence therefore depends on a human
  extending the list.
- **P9 — declared download staleness is computed at download time.**
  `poll_staleness_days_at_download = 1` is frozen in the baseline file while
  the true staleness today is 25 days; the dashboard recomputes its own value.
  Do not quote the baseline column as current staleness.

## 7. Not established (explicit)

- Whether the VoteHub API currently returns an as-of newer than 2026-08-17 —
  no download was performed (audit-only task).
- Whether the published VoteHub `CC BY 4.0` claim is correct — not verified
  against VoteHub's terms of service.
- The exact source URLs, retrieval timestamps, and terms of
  `fivethirtyeight_raw_polls.csv`, `nate_silver_pollster_ratings.csv`,
  `votehub_crosstabs_reviewed.csv`, and the Catalist workbook.
- Whether the 1998–2014 rows in the historical cycles file are consumed by any
  product other than the `national_sd` computation (they are not used by this
  forecast).
- The numerical effect of any refresh on the published forecast — this audit
  rebuilt nothing; a refresh requires a separate authorized run.
- Whether `data/processed/polling/votehub_generic_ballot_snapshot.csv` (fallback,
  as-of 2026-06-30) is consumed by any current build other than the fallback
  branch of the baseline builder.
- Whether any product consumes the Virginia generic-ballot environment files;
  they are not forecast inputs and were only noted for completeness.

## 8. Out-of-scope findings

- `warehouse_source_file` contains one row whose provider is "Arkansas Secretary
  of State" for a file named `…2010_General_Election_Results_-_Fed__State_-_by_Polling_Location.xlsx`;
  it matched a `%poll%` path filter by filename only and is a precinct-results
  file, not a polling input.
- `REPOSITORY_LAYOUT.md` records that `nate_silver_pollster_ratings.csv`
  originates from a loose file named `data-GiFps.csv`; that is the only
  in-repo provenance note and it names no URL or date.
