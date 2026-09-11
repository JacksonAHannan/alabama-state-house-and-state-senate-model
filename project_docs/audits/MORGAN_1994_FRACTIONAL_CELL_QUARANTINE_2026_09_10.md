# Morgan 1994 fractional source cell — quarantine audit (2026-09-10)

Internal evidence for internal checklist item `warehouse-06`: "Resolve or explicitly
quarantine the fractional 1994 source cell". This unit resolves nothing about the
cell's true value. It records the cell's identity and the K48/K52/K53 conflict from
the immutable source, states why no authoritative correction is established, lists
every traced consumer with its enforcement status, lists the cached artifacts that
already embed the fraction, and proposes dispositions without choosing one.

No source value was changed, rounded, dropped or substituted. No warehouse row was
written. No baseline, model output, or publication file was rebuilt. `data/raw/`
was read, never modified. Machine-readable counts and hashes:
`MORGAN_1994_FRACTIONAL_CELL_QUARANTINE_2026_09_10.json`.

## Method and commands

- Warehouse evidence: `sqlite3.connect('file:data/processed/elections/alabama_elections.sqlite?mode=ro', uri=True)`
  with `PRAGMA query_only=ON`; bounded `SELECT`/`COUNT` statements only, no whole-table
  pandas loads.
- Raw source evidence: in-memory read of member `94g-prec/MORGAN.XLS` from the
  registered archive `data/raw/alabama_elections_and_geography/94g-prec.zip` with
  `zipfile` + `xlrd` (no extraction to disk, no write under `data/raw/`).
- Consumer trace: `grep` over `scripts/**` for `vote_observations`,
  `canonical_vote_observations`, `94g-prec`, and the 1994 artifact names, followed by
  reading each hit's predicate.
- Artifact evidence: `os.stat().st_mtime` and streamed SHA256 for each embedding file.
- Tests: `.venv/Scripts/python.exe -m pytest --testmon --testmon-noselect -p no:cacheprovider scripts/tests/test_1994_cmo_baseline.py scripts/tests/test_1994_context_features.py scripts/tests/test_source_vote_quality.py scripts/tests/test_morgan_1994_quarantine.py -q`
  → **30 passed** (24.05 s), 0 failed, 0 skipped, 2 pre-existing pandas `FutureWarning`s
  from `scripts/build_1994_context_features.py:165`.

Line numbers below are as read on 2026-09-10. `scripts/build_war_story_page.py` was
being edited concurrently during this audit (its `vote_observations` aggregate moved
from line 119 to line 148 within the session), so boundaries are also named by
function.

## Cell identity in the immutable source

Registered file `SRC-E64FFC4299ED54CB2D3A`, `provider=alabama_sos`,
`scope=official_vote_counts`, `data/raw/alabama_elections_and_geography/94g-prec.zip`,
sha256 `94512391c389c45d2899f06686484790adaf4c99fa638b217e31f54652c55097`, retrieved
2026-08-16T19:15:03Z from
`https://www.sos.alabama.gov/sites/default/files/election-data/2023-06/94g-prec.zip`.
Member `94g-prec/MORGAN.XLS`, 40,960 bytes, sha256
`e00a9c487b38490a9e6d97c2e85b8f2d3dd07d6e5a2cd3d4eb102d70c30a7b39`; the workbook has
one sheet, `Morgan` (53 rows × 63 columns).

| Cell | Printed content |
|---|---|
| Row 3, column K | header `Sessions` (column group header row 1, `Attorney General`) |
| Rows 4–5, column K | printed ballot code `AG2` |
| Row 48, column C (`Precinct Number`) | `26001` |
| Row 48, column B (`Precinct Name`) | empty on this sheet |
| **Row 48, column K** | **`144.4`** |
| Row 48, columns D–J, L–N | integers |
| Row 52, column B / K | `Total Votes - Reported` / `21571` |
| Row 53, column B / K | `Total Votes - Calculated` / `21571.4` |

Rows 6–51 are the 46 precinct data rows for column K. Forty-five of those cells are
integers and sum to **21,427.0**; the only fractional cell in the entire sheet data
block (rows 6–51, columns D–S) is row 48 / column K = **144.4**. Therefore:

- 21,427 + 144 = **21,571** = K52 (`Total Votes - Reported`), and
- 21,427 + 144.4 = **21,571.4** = K53 (`Total Votes - Calculated`).

Both workbook totals are internally consistent with their own reading of the cell.
The worksheet stores values only (no formula text is recoverable through `xlrd`), so
the workbook does not disclose which total is derived from the other.

## The stored observation

`vote_observations` (2,184,861 rows) contains exactly **one** observation whose
`votes` is not an integer; it is this cell:

| column | value |
|---|---|
| rowid (as observed 2026-09-10; not stable across rewrites) | 2424457 |
| source / year / authority_rank | `alabama_sos` / 1994 / 1 |
| county / county_key | `MORGAN` / `MORGAN` |
| precinct / precinct_key / precinct_code | `26001` / `26001` / `26001` |
| office / district | `Attorney General` / `NULL` |
| candidate / candidate_key | `Sessions` / `SESSIONS` |
| party / party_norm / party_method | `R` / `R` / `ballot_order_with_export_code` |
| ballot_code | `AG2` |
| **votes** | **144.4** |
| source_file / source_sheet / source_row / source_column | `94g-prec/MORGAN.XLS` / `Morgan` / 48 / 11 |
| source_file_id | `SRC-E64FFC4299ED54CB2D3A` |
| build_run_id | `RUN-40A033B9854141F6B05A76173E66D17B` (`source_quality_repair_2026_09_05`) |

County totals implied by the stored slice: `MORGAN` Attorney General Republican
(`SESSIONS`) sums to **21,571.4** (matching K53). The 1994 Alabama Attorney General
Republican statewide source sum is **660,998.4**; the 3,026 non-fractional rows
contribute 660,854.0 and this cell contributes 144.4, so an integer reading of the
cell would put the statewide total at 660,998.0 (Δ = 0.4; relative 6.05e-7).

### Recorded QA and review

- `qa_vote_observation_quality` (view) returns exactly one `fractional_source_vote`
  row, and it is this cell.
- `canonical_vote_observations` (authority-ranked view) **retains** the cell unchanged:
  `authority_rank = 1` is the minimum for year 1994 / county `MORGAN`. No stored view
  excludes or filters it; the QA view only flags it.
- `qa_warehouse_source_repair` issue **`WQA-04-fractional-evidence`**, object
  `vote_observations`, scope `1994/MORGAN/26001/AG2`, status `source_review`, recorded
  2026-09-05T21:35:27.638360+00:00 in run `RUN-C7DE0A0267EC4445938D1CA0CB5C4BD3`,
  evidence: `fractional_cell K48`, `reported_county_total 21571` (`K52`),
  `calculated_county_total 21571.4` (`K53`), decision
  *"Retain original fractional observation; reported/calculated discrepancy is
  evidence, not independent precinct adjudication."*
- Adjacent review record `WQA-03-04` (`Alabama 1994`, `repaired_with_review`) states
  `source_cells_preserved: true` and that the fractional source vote remains
  `unresolved`, retained in `qa_vote_observation_quality`.

## Why no authoritative correction is established

Established by this evidence: the printed cell is 144.4; the sheet's two totals differ
by exactly the 0.4 fractional part; the stored value is byte-faithful to the sheet.

Not established, and not establishable from the archive:

- whether the provider intended `144` (typo/punch artifact, making K52 the coherent
  reported total) or `144.4` (making K53 the coherent calculated total);
- which of K52/K53 is an independently reported count versus a recomputation from
  the printed cells;
- the true precinct-26001 Attorney General count.

The archive contains no formula, errata, correction notice, or district-level
reconciliation for this sheet, and no second provider to adjudicate against: 1994
`vote_observations` has exactly one source (`alabama_sos`, 150,753 rows, 67 counties).
A source that *would* settle it: an official Morgan County 1994 precinct canvass or
Alabama SOS re-issue that states the precinct 26001 `AG2` count (or a documented
provider errata/conversion chain). Absent that, any correction would be an invention:
rounding to 144 imports the K52 reading, and deleting/nulling the cell would make the
aggregate look complete at neither K52 nor K53.

Bounded consequence (arithmetic on recorded artifacts, no rebuild performed): the
entire 0.4 is one precinct's Attorney General Republican value; under the stored 1994
allocation weights that precinct's share is < 1 per district, and the smallest
recorded Attorney General district two-party total is 6,236.72199379276 (House) /
22,395.65003983679 (Senate). The gross upper bound on any single district's Attorney
General margin change is therefore ≤ 0.006414 pp (House) and ≤ 0.001786 pp (Senate) —
an upper bound only if the whole 0.4 landed in one district.

## Consumers of 1994 source rows and their enforcement status

`guard_status` is one of `refuses`, `unguarded`, `view_excludes`, `not_reached`.

| # | Consumer (boundary) | Consumed slice | guard_status | Note |
|---:|---|---|---|---|
| 1 | `build_1994_cmo_baseline.py` `load_returns` (L44) | `alabama_sos`, 1994, statewide Governor/AG D/R **and** legislative | `refuses` | Guard added in the current working tree; predicate covers the cell exactly. Now carries a comment naming `WQA-04-fractional-evidence`. |
| 2 | `build_canonical_cmo_features.py` `main` (L25) | `alabama_sos`, Governor/AG + legislative (all cycles) | `refuses` | Guarded 2026-09-08. |
| 3 | `analyze_canonical_baselines.py` `source_votes` (L26) | 7 statewide offices, all cycles | `refuses` | Guarded 2026-09-08. |
| 4 | `build_adjacent_precinct_alias_graph.py` `nodes_and_turnout` (L23) | `alabama_sos`, 1994–2010, all offices | `refuses` | Guarded. |
| 5 | `build_historical_precinct_adjudication_queue.py` `activity` (L57) | `alabama_sos`, 1994/1998/2002/2006 | `refuses` | Guarded. |
| 6 | `build_precinct_identity.py` `build_nodes` caller (L137) | whole `vote_observations` | `refuses` | Guarded; refuses the whole table, not a slice. |
| 7 | `stage_precinct_identity_repair.py` `stage` (L164) | `DEFAULT_PROFILE` = `source='alabama_sos' AND (year=1994 OR …)` | `refuses` | Guarded; the default repair profile contains 1994 wholesale. |
| 8 | `apply_precinct_identity_repair.py` `verified_stage` (L71) | staging profile (same as #7) | `refuses` | Re-verifies the guard before applying a staged repair. |
| 9 | `build_war_story_page.py` `load_data` (L148–152, moved from L119 during this audit) | `authority_rank=1 AND party_norm IN ('D','R')`, all years/offices | `unguarded` | SQL `SUM(votes)` reads the cell (1994 AG R = 660,998.4). The aggregate is consumed only to choose a display-name per (year, office, party); no vote total from it is published, so the 0.4 can affect only tie-breaking inside a name group. Outside this unit's write scope; reported, not changed. |
| 10 | `build_historical_federal_baselines.py` `load_observations` (L41) | `alabama_sos`, 1994–2022, **all offices** | `not_reached` | The `SELECT` is broader than the consumed slice: it fetches the cell unguarded, then drops every non-federal office (`federal_office('Attorney General', None) == (None, None)`), so the value never reaches a federal aggregate. |
| 11 | `build_1994_context_features.py` `candidates` (L172) | `canonical_candidates` (legislative rows only) + legislative weights CSV | `not_reached` | Reads no raw 1994 vote row; the AG cell has no path into this builder. |
| 12 | `build_candidate_identity.py` `main` (L135) | State House/Senate, all cycles | `not_reached` | Guard present; AG is outside the slice. |
| 13 | `build_canonical_geographic_weights.py` (L30) | State House/Senate, 2010–2022 | `not_reached` | Guard present; cycle/office outside the slice. |
| 14 | `build_presidential_district_features.py` (L90) | State House/Senate, 2010–2022 | `not_reached` | Guard present; outside the slice. |
| 15 | `build_1998_2006_context_features.py` (L165, L222) | 1998/2002/2006 legislative and President-2004 | `not_reached` | Guards present; 1994 and AG outside the slices. |
| 16 | `audit_historical_precinct_geography.py` `legislative_assignments` (L112) | `alabama_sos` cycle param, State House/Senate | `not_reached` | Cycles include 1994; office filter excludes the cell. |
| 17 | `validate_1998_2006_model_readiness.py` (L17) | 1998/2002/2006 Governor/AG | `not_reached` | Outside the cycle slice. |
| 18 | `build_same_year_primary_precinct_aliases.py` (L113) | 1998/2002 | `not_reached` | Outside the cycle slice. |
| 19 | `build_alabama_race_ei.py` (L79) | 2010–2022 Governor | `not_reached` | Outside the slice. |
| 20 | `run_top_ticket_experiments.py` (L89) | 2020 President/Senate | `not_reached` | Outside the slice. |
| 21 | `repair_warehouse_source_defects.py` (L92, L209, L290) | 1994 all offices (QC/preservation) | `not_reached` | Integrity/QC path: asserts 1994 vote preservation, emits the `fractional_source_vote` QA issue, and checks the repaired AG2 party encoding. Refusal would be wrong here; it must keep recording the printed value. |
| 22 | `stage_legacy_source_lineage.py` (L153, L186) | 1998/2004 | `not_reached` | Outside the slice. |
| 23 | `repair_sos_cell_lineage.py` (L264) | 1998/2004 | `not_reached` | Outside the slice. |
| 24 | `build_election_database.py` (L68) | ingest of `vote_observations` | `not_reached` | Producer: records the printed value by contract; must not refuse. |
| 25 | `build_data_catalog.py` (L21) | catalog metadata | `not_reached` | No row read. |

Counts: **8 `refuses`**, **1 `unguarded`**, **0 `view_excludes`**, **16 `not_reached`**.

Derived (non-raw) consumers of the cell-carrying artifacts below — these read no raw
1994 row and their inputs predate every refusal, so the raw quarantine does not stop
them: `build_alabama_historical_war_v1.py` (backcasts 1994–2014 from
`cmo_v5_races.csv` / `cmo_v5_candidates.csv` / `canonical_cmo_features.csv`),
`build_war_story_page.py` (also reads `canonical_cmo_features.csv` and
`canonical_cmo_district_office_baselines.csv`), `build_southern_war_panel_v1.py`,
`rebuild_cmo_southern_prior_v6.py`, `rebuild_cmo_methodology_v2.py`,
`rebuild_cmo_direct_estimand.py`, `rebuild_cmo_war_analogue.py`,
`fit_preliminary_war_model.py`, `validate_war_outputs.py`,
`review_historical_fallback_movements.py`, `analyze_black_candidate_turnout.py`,
`analyze_cmo_ideology_research.py`, `analyze_incumbency_survivorship.py`,
`analyze_social_moderation_cmo.py`, `build_cmo_geography_sensitivity.py`,
`calibrate_forward_cmo_uncertainty.py`, `compare_2026_prospective_models.py`,
`compare_expanded_cycle_cmo_models.py`, `compare_federal_cmo_baselines.py`,
`fit_2026_prospective_model.py`, `integrate_votesmart_pct_cmo_features.py`,
`analyze_absolute_ideology_rebuild.py`. Per-script cycle filters were **not**
exhaustively audited; the two checked (`compare_historical_cmo_performance.py`
1998–2006, `run_fcpa_fundraising_experiments.py` 2014+) exclude 1994.

## Cached artifacts that embed the fraction

All were generated 2026-08-16 … 2026-08-26, before any refusal existed on their
producers (the five guarded boundaries were added 2026-09-08; the 1994 baseline guard
is uncommitted working-tree change observed 2026-09-10).

| Artifact | mtime (UTC) | Producer | Carries the cell |
|---|---|---|---|
| `data/processed/elections/1994_baseline_allocation_qa.csv` | 2026-08-16T19:08:30Z | `build_1994_cmo_baseline.main` | **Yes** — AG R `source_votes` = 660,998.4 |
| `data/processed/elections/1994_district_baseline_office.csv` | 2026-08-16T19:08:30Z | `build_1994_cmo_baseline.main` | **Yes** — AG R allocated sums 659,715.4 (house) / 660,399.4 (senate) |
| `data/processed/elections/1994_cmo_race_features.csv` | 2026-08-16T19:08:30Z | `build_1994_cmo_baseline.main` | **Yes** — `core_index_margin` built from the AG/Governor allocation |
| `data/processed/elections/1994_precinct_district_ballot_weights.csv` | 2026-08-16T19:08:30Z | `build_1994_cmo_baseline.main` | No — legislative activity only |
| `data/processed/elections/1994_unmatched_precinct_review.csv` | 2026-08-16T19:08:30Z | `build_1994_cmo_baseline.main` | No for this cell — precinct 26001 has legislative weights; other Morgan AG rows present |
| `data/processed/elections/1994_cmo_context_features.csv` | 2026-08-16T19:08:41Z | `build_1994_context_features.main` | No — no vote columns |
| `data/processed/elections/1994_candidate_incumbency.csv` | 2026-08-16T19:08:41Z | `build_1994_context_features.main` | No |
| `data/processed/demographics/1994_district_demographics.csv` | 2026-08-16T19:08:41Z | `build_1994_context_features.main` | No |
| `data/processed/presidential/1994_district_presidential_features.csv` | 2026-08-16T19:08:41Z | `build_1994_context_features.main` | No (1992 presidential returns) |
| `data/processed/war/1994_candidate_finance_coverage.csv` | 2026-08-16T19:08:41Z | `build_1994_context_features.main` | No |
| `data/processed/elections/historical_federal_district_baselines.csv` | 2026-08-21T15:21:36Z | `build_historical_federal_baselines.main` | No — 1994 federal offices only |
| `data/processed/war/preliminary_cmo_races.csv` | 2026-08-21T15:29:25Z | `fit_preliminary_war_model.py` | **Yes** — 72 rows for cycle 1994 with `core_index_margin` |
| `data/processed/elections/canonical_cmo_features.csv` | 2026-08-26T13:51:58Z | `build_canonical_cmo_features.main` | **Yes** — cycle-1994 `core_index_margin`; producer refuses as of 2026-09-08 |
| `data/processed/elections/canonical_cmo_district_office_baselines.csv` | 2026-08-26T13:51:58Z | `build_canonical_cmo_features.main` | **Yes** — AG 1994 D/R sums 497,446.0 / 659,715.4 / 497,833.0 / 660,399.4 (identical .4 to the 1994 baseline) |
| `data/processed/elections/historical_cmo_extension.csv` | 2026-08-26T13:51:58Z | `build_canonical_cmo_features.main` | **Yes** — 144 rows for 1994 |
| `data/processed/war/cmo_v5_races.csv` | 2026-08-26T13:53:25Z | `rebuild_cmo_candidate_quality_v5.py` | **Yes** — 72 rows for 1994 |
| `data/processed/war/cmo_v5_candidates.csv` | 2026-08-26T13:53:25Z | `rebuild_cmo_candidate_quality_v5.py` | **Yes** — 144 rows for 1994 |

Warehouse tables (not files; same question):

| Table (cycle 1994) | Build run (UTC, code) | Carries the cell |
|---|---|---|
| `mart_historical_precinct_district_weight` | `RUN-ADA16D76E1BB4520ABA370CED9922828`, 2026-08-16T19:08:30Z, `de9e5e59` | No — legislative activity only |
| `mart_historical_district_office_baseline` | same run | **Yes** — AG R allocated .4-ending totals |
| `mart_historical_cmo_race_feature` | same run | **Yes** — `core_index_margin` |
| `qa_historical_baseline_allocation` | same run | **Yes** — `source_votes` AG R = 660,998.4 |
| `mart_historical_cmo_context_feature` | `RUN-2541D303D6A44F3B81075C41CBDE65B2`, 2026-08-16T19:08:41Z | No |

No 1994 baseline or 1994 CMO mart has been rebuilt since 2026-08-16/08-26
(`warehouse_build_run` has no later `historical_1994_*` run). Count of identified
cell-carrying artifacts: **9 files + 3 warehouse tables = 12, all predating the
refusal.**

`data/processed/war/alabama_war_v1/` and `data/processed/war/alabama_historical_war_v1/`
were **not** inspected: the primary session is rebuilding both, so any contents read
there would not be a current fact.

## Changes made by this unit

- `scripts/build_1994_cmo_baseline.py`: the refusal covering this exact slice already
  existed in the working tree (uncommitted); this unit added a four-line comment naming
  the QA record and this audit. No behaviour change.
- `scripts/build_1994_context_features.py`: **unchanged**. It never reads a raw 1994
  vote row (verified above), so no refusal is applicable.
- `scripts/tests/test_1994_cmo_baseline.py`: **rewritten**. Its three tests called
  `load_returns()` against the live slice and had been failing since the guard landed
  (`3 failed, 4 passed` before this change, see below). The module now drives
  `build_weights` / `allocate` / `build_features` with deterministic integer fixtures,
  so it no longer depends on warehouse contents and cannot silently re-test the
  quarantined slice. Coverage note: its former real-source scale assertions
  (104 House / 35 Senate districts, 72 contested races) are no longer executable while
  the slice is refused; they are recorded here as the pre-quarantine module's claims,
  not re-verified by this unit.
- `scripts/tests/test_morgan_1994_quarantine.py`: **new**. Pins (a) the live warehouse
  retains exactly one fractional observation and it is the recorded cell; (b) the QA
  view flags it and the canonical view retains it (no view exclusion); (c) the live
  1994 baseline refuses before any pandas read and leaves the cell unchanged; (d) an
  integer (144 or 0) in the same slot passes, so the quarantine is about the fraction
  and not the row.

Not touched, and reported instead: `build_war_story_page.py` (unguarded aggregate,
consumer #9) and `build_historical_federal_baselines.py` (broader-than-consumed read,
consumer #10).

## Verification

```powershell
& .venv/Scripts/python.exe -m pytest --testmon --testmon-noselect -p no:cacheprovider `
  scripts/tests/test_1994_cmo_baseline.py scripts/tests/test_1994_context_features.py `
  scripts/tests/test_source_vote_quality.py scripts/tests/test_morgan_1994_quarantine.py -q
```

- After this unit: **30 passed**, 0 failed, 0 skipped, 2 warnings, 24.05 s.
- Before this unit, over the two pre-existing 1994 modules: **3 failed, 4 passed** — all
  three failures were `test_1994_cmo_baseline.py` raising
  `ValueError: Unusable reported votes: 1 source observations … {"votes": 144.4, …,
  "issue": "fractional_source_vote"}`.
- No formatter, linter, project-wide suite, or rebuild was run (unit scope).
- Warehouse state: `data/processed/elections/alabama_elections.sqlite`, 5,819,056,128
  bytes, mtime 2026-09-08T15:38:30Z, opened read-only with `PRAGMA query_only=ON`
  throughout. No checksum of the database file was computed; all writes are excluded by
  the connection mode, and no row was modified.

## Disposition proposal (evidence only — the owner decides)

**Option A — retain as reported, refuse at consumption, no correction.** Matches the
existing `WQA-04` decision and the implemented guards. To be *complete* it still needs:
(i) the 12 cell-carrying artifacts listed above marked stale for this reason until they
are regenerated after adjudication — none currently records it; (ii) a decision on
consumer #9 (`build_war_story_page.py`), which reads the cell unguarded into a
display-name aggregate — either guard its slice or record why the page's name lookup is
exempt; (iii) a note in the 1994 baseline/CMO documentation that 1994 cannot be rebuilt
while the cell stands (the guards already make this true in practice).

**Option B — establish a correction.** Requires a named authoritative source (SOS or
Morgan County re-issue/errata giving the precinct 26001 `AG2` count), then a source
change plus dependent rebuilds. No such source is present in the repository or
referenced by the registered archive.

**Option C — declare the cell unknowable at precinct grain and record an explicit
exclusion** for precinct 26001's Attorney General allocation. This changes stored
output, requires an authorized repair, and makes the aggregate equal to neither K52 nor
K53; the evidence does not support it as a first choice, but it is listed because it is
the only option that would let the 1994 pipeline run again.

The K48/K52/K53 conflict cannot be resolved from the archive alone, so this audit does
not select an option.

## Not established

- The intended reading of K48 (144 vs 144.4) and the true precinct-26001 count.
- Whether K52 is an independent reported count or a recomputation from rounded cells.
- The per-district propagation of the 0.4 into the published 1994 WAR backcast: the
  chain is recorded, no rebuild was performed, and no per-artifact delta was quantified.
- Freshness/contents of `data/processed/war/alabama_war_v1/` and
  `data/processed/war/alabama_historical_war_v1/` (excluded: primary-session rebuild).
- Whether any analysis script consuming the embedding artifacts filters cycle 1994 (only
  two were checked).
- Whether the same provider/worksheet defect exists for any other cycle, county, or
  state; this audit covers only the one recorded fractional cell.

## Out-of-scope findings (reported, not changed)

- `build_war_story_page.py` `load_data`: unguarded `SUM(votes)` over
  `authority_rank=1` D/R rows including the cell (see #9). The file was being edited
  concurrently by another session during this audit.
- `build_historical_federal_baselines.py`: `SELECT` covers 1994 all offices while only
  federal offices are consumed (see #10) — broader than needed, though not an exposure.
- `stage_precinct_identity_repair.py` / `apply_precinct_identity_repair.py`: the default
  repair profile contains `year=1994` wholesale, so the precinct-identity repair paths
  are also blocked by this cell. These are not 1994-specific consumers; the block is a
  consequence of the profile granularity.
- `qa_vote_observation_quality` is advisory only: no producer consults it; the only
  enforced refusal is the `require_reported_vote_quality` call pattern.
- `warehouse_build_run` holds two `running` runs with no completion
  (`RUN-38499B743007490291D8841A8A3FF91B`, `RUN-D1633D6ECDE54F9DBD9A75F644C8619B`)
  and several long-lived `running` finance/plan runs; unrelated to this cell, recorded
  because the audit read the table.
