# Alabama baseline and plan certification — `alabama-04`

Audit date: 2026-09-11. Task `ALABAMA-BASELINE-PLAN-CERTIFICATION-20260911`
(`cmo_model`, write scope `project_docs/audits/ALABAMA_BASELINE_PLAN_CERTIFICATION_2026_09_11.*`).
Read-only: no warehouse writes, no builder execution, no `docs/` or published
export changes, no network. Companion JSON carries `generated_at_utc`.

## 0. Certification question

For each of the eight historical cycles (1994, 1998, 2002, 2006, 2010, 2014,
2018, 2022) and each chamber, record for the same-cycle ticket baselines that
feed the historical Alabama WAR:

1. the same-cycle ticket **source election(s)**;
2. the **allocation method** and its **geography vintage**;
3. the **target district plan** the district numbers refer to;
4. the **county-fallback share** distribution;
5. **vote conservation** (allocated D/R across districts vs statewide source);
6. the **prior-presidential source election** and its completeness;

and verify that no later plan or election silently substitutes for the cycle
being modelled.

## 1. Lineage and inputs

| Item | Value |
|---|---|
| HEAD (task registration) | `d93dd8c6` |
| Published historical Alabama run | `AL-HIST-WAR-V1-44F191EB8D939EF062CC` |
| Published Alabama WAR v1 | `AL-WAR-V1-C00FF05BC2BE58E16087` |
| Approved Southern v3 source | `WAR-POST2016-V3-530FBD4238CC483E557C` |
| Southern training warehouse | `RUN-504CE4C4DF904D88A5A40D268F3FCEAB` (declared in the historical manifest) |
| Scoped 2002 repair run | `RUN-DFB1D093D7594AB68A264292050E924D` (task context) |
| Historical export manifest | `data/processed/war/alabama_historical_war_v1/manifest.json` (`generated_at_utc` 2026-09-11T15:52:53Z, `git_commit` 38c30819…) |

Files read (no writes):

- `data/processed/elections/canonical_cmo_features.csv` (1,056 rows)
- `data/processed/elections/canonical_cmo_district_office_baselines.csv` (2,236 rows)
- `data/processed/war/cmo_v5_races.csv` (510 rows)
- `data/processed/war/alabama_historical_war_v1/race_war.csv` (510 rows) and `candidate_cycle_war.csv` (1,020 rows)
- `data/processed/elections/canonical_precinct_district_weights.csv`, `canonical_geography_qa.csv`
- `data/processed/elections/historical_federal_district_baselines.csv`, `historical_federal_contest_components.csv`,
  `validation/historical_federal_baseline_coverage.csv`
- `data/processed/war/district_baseline_office.csv`, `baseline_allocation_qa.csv`, `district_baselines.csv`
- `data/processed/elections/1994_baseline_allocation_qa.csv`, `1994_unmatched_precinct_review.csv`
- `data/processed/presidential/*_district_presidential_features.csv`, `1996_2004_historical_president_precinct.csv`
- `data/processed/elections/alabama_elections.sqlite` — opened
  `sqlite3.connect('file:…?mode=ro', uri=True)` + `PRAGMA query_only=ON`, bounded SQL only.

Producers read: `build_canonical_cmo_features.py`, `build_1994_cmo_baseline.py`,
`build_1994_context_features.py`, `build_1998_2006_context_features.py`,
`build_historical_federal_baselines.py`, `build_presidential_district_features.py`,
`build_canonical_geographic_weights.py`, `build_geographic_crosswalks.py`,
`build_war_database.py`, `rebuild_cmo_methodology_v2.py`,
`rebuild_cmo_candidate_quality_v5.py`, `build_war_story_page.py` (`MAP_FILES`,
`PRIOR_PRESIDENTIAL_NOMINEES`), `build_alabama_historical_war_v1.py`.

## 2. Definitions used

- **In-universe race**: a row of `cmo_v5_races.csv` (510 rows; identical key set
  to `race_war.csv`, 1,020 candidate orientations). 438 rows are
  `core_1998_2022`, 72 are `sensitivity_1994`.
- **Selected ticket baseline** (`selected_ticket_source`, `selected_ticket_margin`):
  `rebuild_cmo_candidate_quality_v5.prepare()` sets the baseline to
  `federal_index_margin` when `federal_primary` is true, else
  `baseline_state_margin_v2`. Labels are `same_cycle_federal` /
  `same_cycle_state_fallback`.
  - `same_cycle_federal` = mean of the district margins of the **same-cycle**
    contested D-vs-R U.S. House and U.S. Senate contests
    (`build_historical_federal_baselines.build()`); uncontested contests are
    excluded from the margin but retained in `federal_contested_coverage`, and
    `federal_available_v2` requires coverage ≥ 0.5
    (`rebuild_cmo_methodology_v2`).
  - `same_cycle_state_fallback` = same-cycle **Governor + Attorney General**
    vote-weighted margin (`build_source_aware_baseline`,
    `state_ticket_margin_weighted`).
- **Ticket-office baselines** (`canonical_cmo_district_office_baselines.csv`)
  are the Governor and Attorney General allocations used for the state ticket
  and for `core_index_margin`. For 2014/2018/2022 most core rows are replaced by
  `data/processed/war/district_baseline_office.csv` (`baseline_source =
  election_precinct_block_population`).
- **Prior-presidential baseline**: the immediately preceding presidential
  district allocation (`prior_presidential()` in `rebuild_cmo_methodology_v2`,
  `TARGET_SOURCES` / `PRIOR` in the producers).
- **Conservation**: per chamber/office, `sum(allocated D/R over districts)` from
  `canonical_cmo_district_office_baselines.csv` minus the statewide source
  total from `vote_observations` (below). Each chamber independently allocates
  the full statewide vote, so chambers are compared separately, never summed.

### Statewide source totals used (`vote_observations`, `source='alabama_sos'`)

Party normalization applied by the producers is reproduced where the warehouse
labels are incomplete:

- 1994 Attorney General: warehouse already labels `SESSIONS` R / `EVANS` D; the
  producer's `PARTY_CORRECTIONS` is a defensive duplicate of that.
- 2010 Governor and Attorney General: every row carries `party_norm='O'`.
  `build_canonical_cmo_features.PARTY_2010` maps
  `ROBERT BENTLEY`→R (860,272), `RON SPARKS`→D (625,052), `LUTHER STRANGE`→R
  (868,331), `JAMES H ANDERSON`→D (605,650). These mapped values are used as the
  2010 source totals.

| cycle | office | source D | source R |
|---|---|---|---|
| 1994 | Governor | 590,497 | 603,157 |
| 1994 | Attorney General | 498,409 | 660,998 |
| 1998 | Governor | 1,415,398 | 1,218,917 |
| 1998 | Attorney General | 641,185 | 648,298 |
| 2002 | Governor | 749,428 | 755,958 |
| 2002 | Attorney General | 576,003 | 875,388 |
| 2006 | Governor | 426,923 | 600,312 |
| 2006 | Attorney General | 485,835 | 544,520 |
| 2010 | Governor | 625,052 | 860,272 |
| 2010 | Attorney General | 605,650 | 868,331 |
| 2014 | Governor | 521,632 | 938,624 |
| 2014 | Attorney General | 504,345 | 714,638 |
| 2018 | Governor | 694,011 | 1,021,276 |
| 2018 | Attorney General | 702,345 | 1,003,298 |
| 2022 | Governor | 412,961 | 946,932 |
| 2022 | Attorney General | 450,543 | 955,425 |

## 3. Per-cycle certification table

`races` = in-universe rows. `fed/state` = `selected_ticket_source` counts.
`fb p50/p90/max` = `baseline_fallback_share` quantiles over in-universe races.
`prior-pres` = immediately preceding presidential allocation, complete/total
in-universe races.

| cycle | chamber | races | fed/state | fb p50 | fb p90 | fb max | prior-pres | plan | geography vintage |
|---|---|---|---|---|---|---|---|---|---|
| 1994 | house | 54 | 37/17 | 0.0000 | 0.0000 | 0.0000 | 1992: 46/54 | 1992–2000 (`al_lower_1992_2000`) | same-cycle SOS precinct ballot/activity; no county fallback |
| 1994 | senate | 18 | 12/6 | 0.0000 | 0.0000 | 0.0000 | 1992: 17/18 | 1992–2000 (`al_upper_1992_2000`) | same as house |
| 1998 | house | 57 | 57/0 | 0.0000 | 0.0000 | 0.7072 | 1996: 52/57 | 1992–2000 | legislative-activity split; 1990 SF3 tract county-population fallback |
| 1998 | senate | 28 | 28/0 | 0.0000 | 0.0006 | 0.0128 | 1996: 24/28 | 1992–2000 | same as house |
| 2002 | house | 52 | 52/0 | 0.0000 | 0.0164 | 0.0552 | 2000: 45/52 | 2002–2010 (`al_lower_2002_2010`) | legislative-activity split; 2000 SF3 tract county-population fallback |
| 2002 | senate | 23 | 23/0 | 0.0000 | 0.0000 | 0.0000 | 2000: 18/23 | 2002–2010 | same as house |
| 2006 | house | 40 | 22/18 | 0.0000 | 0.0000 | 0.0000 | 2004: 38/40 | 2002–2010 | legislative-activity split; 2000 SF3 tract county-population fallback |
| 2006 | senate | 22 | 13/9 | 0.0000 | 0.0000 | 0.0000 | 2004: 19/22 | 2002–2010 | same as house |
| 2010 | house | 42 | 42/0 | 0.0000 | 0.0000 | 0.0000 | 2008: 42/42 | 2002 plan via 2010 Census SLD boundaries (`tl_2010_01_sldl00`) | canonical precinct→district weights, 2010 Census VTD/blocks |
| 2010 | senate | 21 | 21/0 | 0.0000 | 0.0000 | 0.0000 | 2008: 21/21 | `tl_2010_01_sldu00` | same |
| 2014 | house | 40 | 21/19 | 0.0000 | 0.0000 | 0.0000 | 2012: 40/40 | 2012 enacted (`al_sldl_2012_to_2017`) | canonical weights from **2010** Census blocks; core rows from OpenElections 2014 block/precinct product |
| 2014 | senate | 16 | 9/7 | 0.0000 | 0.0000 | 0.0000 | 2012: 16/16 | `al_sldu_2012_to_2017` | same |
| 2018 | house | 49 | 48/1 | 0.0000 | 0.0000 | 0.0000 | 2016: 49/49 | **2017 remedial** (`al_sldl_2017_to_2021`) | canonical weights from 2020 Census blocks; core rows from OpenElections 2018 |
| 2018 | senate | 15 | 15/0 | 0.0000 | 0.0000 | 0.0000 | 2016: 15/15 | `al_sldu_2017_to_2021` | same |
| 2022 | house | 25 | 25/0 | 0.0000 | 0.0000 | 0.0000 | 2020: 25/25 | 2021 enacted (`al_sldl_2021_to_2023`) | canonical weights from 2020 Census blocks; core rows from 2022 RDH/SOS precinct file |
| 2022 | senate | 8 | 8/0 | 0.0000 | 0.0000 | 0.0000 | 2020: 8/8 | `al_sldu_2021_to_2023` | same |

Plan labels are read from `build_war_story_page.MAP_FILES`,
`build_war_database.MAP_VINTAGE` (`{2014: 2012_enacted, 2018: 2017_remedial,
2022: 2021_enacted}`), the `PLANS`/`PLAN_FILES` dicts in
`build_1998_2006_context_features.py` / `build_1994_cmo_baseline.py`, and
`block_district_assignments()` in `build_geographic_crosswalks.py`.

## 4. Ticket source composition

`selected_ticket_source` counts (fed/state) above. The federal source index is
built from contested same-cycle federal contests; `senate_available` is zero in
cycles with no contested U.S. Senate contest, which is why the state fallback is
used more often then:

| cycle | federal House available | federal Senate available | median contested coverage |
|---|---|---|---|
| 1994 | 82 districts | 0 | 1.000 |
| 1998 | 88 / 105 (house), 32 / 36 (senate) | 105 / 36 | 1.000 |
| 2002 | 66 / 105, 25 / 35 | 105 / 35 | 0.996 / 0.938 |
| 2006 | 51 / 61, 22 / 25 | 0 | 1.000 |
| 2010 | 92 / 105, 35 / 35 | 105 / 35 | 1.000 / 0.989 |
| 2014 | 79 / 79, 27 / 27 | 0 | 0.555 / 0.553 |
| 2018 | 104 / 104, 35 / 35 | 0 | 1.000 |
| 2022 | 88 / 105, 31 / 35 | 105 / 35 | 1.000 |

Source: `data/processed/elections/validation/historical_federal_baseline_coverage.csv`.

## 5. Conservation — state ticket offices

Per chamber/office, difference of allocated sum minus the statewide source
total; percent is relative to the source. (Full table in the JSON companion.)

| cycle | chamber | office | ΔD | ΔR | %D | %R | weighted margin Δ (pp) |
|---|---|---|---|---|---|---|---|
| 1994 | house | Governor | −1,067 | −1,119 | −0.181 | −0.186 | −0.0002 |
| 1994 | house | Attorney General | −931 | −1,195 | −0.187 | −0.181 | |
| 1994 | senate | Governor | −671 | −550 | −0.114 | −0.091 | −0.0118 |
| 1994 | senate | Attorney General | −576 | −599 | −0.116 | −0.091 | |
| 1998 | house | Governor | −3,276 | −3,588 | −0.231 | −0.294 | +0.0323 |
| 1998 | house | Attorney General | −1,445 | −1,903 | −0.225 | −0.294 | |
| 1998 | senate | both | 0 | 0 | 0.000 | 0.000 | 0.0000 |
| 2002 | both | both | 0 | 0 | 0.000 | 0.000 | 0.0000 |
| 2006 | both | both | 0 | 0 | 0.000 | 0.000 | 0.0000 |
| 2010 | both | both | 0 | 0 | 0.000 | 0.000 | 0.0000 |
| 2014 | house | Governor | −77,692 | −161,615 | −14.894 | −17.218 | +0.6288 |
| 2014 | house | Attorney General | −72,906 | −99,674 | −14.455 | −13.948 | |
| 2014 | senate | Governor | −76,708 | −155,611 | −14.705 | −16.579 | +0.6966 |
| 2014 | senate | Attorney General | −92,284 | −136,875 | −18.298 | −19.153 | |
| 2018 | both | both | 0 | 0 | 0.000 | 0.000 | 0.0000 |
| 2022 | both | both | 0 | 0 | 0.000 | 0.000 | 0.0000 |

`weighted margin Δ` is the chamber-aggregate Governor+Attorney-General
vote-weighted margin (the quantity `state_ticket_margin_weighted` uses) minus the
source margin.

**2014 is a source-provenance difference, not an allocation loss.** The 2014
core office rows come from `data/processed/war/district_baseline_office.csv`,
whose own reconciliation against its source (OpenElections
`20141104__al__general__precinct.csv`) is exactly 1.0 for every 2014 office and
chamber (`data/processed/war/baseline_allocation_qa.csv`: Governor house
1,220,949 → 1,220,949; senate 1,227,937 → 1,227,937). The gap above arises
because that source universe is ~232k Governor votes smaller than the canonical
SOS warehouse total (1,460,256). The audit did **not** reconcile that provenance
gap (see §9).

**1994 and 1998 house** shortfalls are genuine allocation losses:

- 1994 has no county fallback (`build_1994_cmo_baseline` records unmatched
  precincts instead of imputing). `1994_baseline_allocation_qa.csv` shows
  coverage 0.9981–0.9991; `1994_unmatched_precinct_review.csv` carries 256
  unmatched rows across 12 counties — nonzero house votes in Covington,
  Lauderdale, Lowndes, Marengo, Morgan and Jackson; nonzero senate votes in
  DeKalb, Hale, Madison and Jackson (Jefferson, Marshall and Shelby appear with
  zero votes).
- 1998 house: the precincts with no same-cycle State House activity
  (`left_only`) are in Franklin (14,844 D / 11,038 R), Crenshaw (8,181 / 5,693)
  and Dale (2,928 / 3,376); the county-population fallback recovers most but not
  all of them. The residual −3,276 D / −3,588 R is not fully attributed
  (Dale's totals are the nearest match; see §9).

## 6. Conservation — prior-presidential allocation (secondary)

Allocated district presidential sums (`*_district_presidential_features.csv`)
vs the source precinct files:

| cycle | source year | chamber | ΔD | ΔR | %D | %R |
|---|---|---|---|---|---|---|
| 1994 | 1992 | both | 0 | 0 | 0.000 | 0.000 |
| 1998 | 1996 | house | −6,656 | −6,431 | −1.062 | −0.886 |
| 1998 | 1996 | senate | 0 | 0 | 0.000 | 0.000 |
| 2002 | 2000 | house & senate | −10,381 | −17,084 | −1.933 | −2.301 |
| 2006 | 2004 | house & senate | −98,664 | −251,174 | −15.871 | −19.516 |
| 2010 | 2008 | both | 0 | 0 | 0.000 | 0.000 |
| 2014 | 2012 | both | 0 | 0 | 0.000 | 0.000 |
| 2018 | 2016 | both | 0 | 0 | 0.000 | 0.000 |
| 2022 | 2020 | both | 0 | 0 | 0.000 | 0.000 |

The 2006 loss is **fully attributed**: the warehouse's 2006 State House and
State Senate observations cover only ~48 of 67 counties. The 18 counties with no
2006 legislative observations (Barbour, Bibb, Blount, Chambers, Choctaw,
Colbert, Crenshaw, DeKalb, Escambia, Franklin, Houston, Lamar, Lauderdale,
Limestone, Lowndes, Perry, St. Clair, Washington) hold exactly 349,838 votes in
the 2004 presidential source file = the observed loss. The prior-presidential
fallback tiers (`allocate_to_districts` → `county_activity_fallback`) join
`county_shares` built from the same-cycle legislative activity, so a county with
no legislative returns drops out entirely. The **state**-ticket path instead
used `county_population_district_weights` and conserved those counties (§5), so
this is specific to the prior-presidential allocation for 1998–2006.

## 7. Flags

### 7.1 Conservation beyond rounding

| flag | cycle/chamber | evidence |
|---|---|---|
| Allocated sums below source | 1994 house/senate; 1998 house | §5; −0.09% to −0.29% |
| Allocated sums ~15–18% below canonical source | 2014 house/senate | §5; different source universe (OpenElections vs SOS) |
| Prior-pres allocation below source | 1998 house (−1.1%/−0.9%); 2002 (−1.9%/−2.3%); 2006 (−15.9%/−19.5%) | §6; 2006 fully attributed to 18 counties with no 2006 legislative returns |

Largest conservation difference overall: **2014 senate Attorney General D
−18.298% (−92,284 votes)**; largest absolute vote gap: **2014 house Governor R
−161,615**. Largest difference among cycles whose allocation shares the
canonical warehouse source: **1998 house Governor R −0.294% (−3,588 votes)**.

### 7.2 Fallback share > 10%

In-universe races with `baseline_fallback_share` > 0.10: **1**.

| cycle | chamber | district | Governor fb | AG fb | method |
|---|---|---|---|---|---|
| 1998 | house | 18 | 0.7072 | 0.7057 | `county_population_fallback` |

Out-of-universe baseline rows with office-level fallback > 0.10 (present in
`canonical_cmo_district_office_baselines.csv`, no matching in-universe race):

| cycle | chamber | district | fb | note |
|---|---|---|---|---|
| 1998 | house | 90 | 0.389 | no in-universe race |
| 2006 | house | 86 | 1.000 | no 2006 legislative returns for HD86; no in-universe race |

Prior-presidential allocation fallback > 0.10 is common in 1998–2006
(1998 house 50, 1998 senate 28, 2002 house 40, 2002 senate 21, 2006 house 17,
2006 senate 11 in-universe races) and is a property of the prior-presidential
context, not the selected ticket baseline.

### 7.3 District-number / plan-conformance anomalies

- **1998 State Senate district 90.** The 1998 source labels 19 Crenshaw County
  precincts as `State Senate` district `90` (candidate `NEWTON`, `party_norm='O'`,
  3,242 votes). The activity weights treat it as a district, producing an office
  baseline row `(1998, senate, 90)` with 1,432 D / 546 R (AG) and 2,115 D /
  1,851 R (Governor) — outside the 1–35 senate plan. It is not in the race
  universe (`cmo_v5_races` has no 1998 SD90) but it is in the office-baseline
  export and consumes ~0.15% of the senate allocation away from Crenshaw's true
  district. Observed source label; not repaired here.
- **1994 House district 92** is absent from the 1994 source legislative returns
  and therefore from both the race universe and the office baselines (104 house
  districts).
- **2006 coverage.** Source State House returns cover 98 districts
  (missing 1, 2, 3, 5, 18, 24, 86) and 48 counties; State Senate returns cover
  34 districts (missing 1) and 48 counties. Office baselines cover 103 house
  districts (missing 1, 24) and 35 senate districts. This is the direct cause of
  the §6 2006 loss.
- **2014 mixed-provenance core rows.** 277 / 280 core office rows for 2014 come
  from `district_baseline_office.csv`; three house Attorney General rows
  (HD13 county fallback, HD24, HD40) fall back to canonical SOS allocations.

## 7a. Resolution of the 2014 state-ticket flag (owner decision, 2026-09-11)

The owner accepted the recommended repair. `scripts/build_canonical_cmo_features.py`
now applies the legacy spatial override (`district_baseline_office.csv`,
`baseline_source = election_precinct_block_population`) only to 2018 and 2022,
where it conserves the certified totals; 2014 keeps the SOS-canonical allocation
computed in the same builder. After the rebuild the 2014 allocated state ticket
equals the SOS statewide totals exactly for both chambers (Governor D 521,632 /
R 938,624; Attorney General D 504,345 / R 714,638; all 280 cycle-office rows
`alabama_sos_canonical`). No other cycle changed (max |Δ office margin| = 0 for
1994–2010, 2018, 2022). District core-index margins moved for 140 of 140 2014
districts (median 1.1 pp, max 27.2 pp in HD82, where the legacy source lacked
whole counties). In the historical WAR export only the 26 races on the 2014
state-ticket fallback changed (|Δ baseline| ≤ 2.62 pp, |Δ WAR| ≤ 2.22 pp, eight
races > 0.5 pp); the 30 same-cycle-federal 2014 races, every other cycle, the
modern `alabama_war_v1` export, the forecast scenarios and the v3 training-frame
digest (`cc9204796781b99a…`) are unchanged. Historical run
`AL-HIST-WAR-V1-0E018273EBEDEEEFAD75` supersedes `AL-HIST-WAR-V1-44F191EB8D939EF062CC`.
Before-images: `artifacts/war/baseline_2014_fix_20260911/`.

## 8. Substitution checks

| check | result | evidence |
|---|---|---|
| Ticket election year equals the cycle | **PASS** | State ticket: `observations[observations.year.eq(cycle)]`; federal: `allocate_cycle` filters `source[source.year.eq(cycle)]`. `selected_ticket_source` only distinguishes same-cycle federal vs same-cycle state. |
| Prior presidential is the immediately preceding election | **PASS** | 1992→1994, 1996→1998, 2000→2002, 2004→2006, 2008→2010, 2012→2014, 2016→2018, 2020→2022 (`PRIOR`, `TARGET_SOURCES`, `prior_presidential()`, `build_war_story_page.PRIOR_PRESIDENTIAL_NOMINEES`). |
| District plan matches the election's plan | **PASS with one label conflict** | 1994/1998 → 1992–2000; 2002/2006 → 2002–2010; 2010 → 2002 plan via 2010 Census SLD; 2014 → 2012 enacted; 2022 → 2021 enacted. **2018** uses the 2017 remedial plan (`MAP_VINTAGE[2018]='2017_remedial'`, display `al_sldl_2017_to_2021`), which agrees with the 2018 election's plan but contradicts the task's stated expectation of "2012 plan for 2014/2018". No allocation/display substitution is evident for 2018; the conflict is in the stated expectation. Flagged for owner confirmation. |

## 9. Not established

1. Whether the 2018 allocation's official block-assignment file
   (`BlockAssign_ST01_AL.zip`, 2020-vintage) encodes the 2017 remedial plan. The
   audit did not decode the block assignment; the 2017 vintage is inferred from
   `MAP_VINTAGE` and the display filename.
2. Exact county/row attribution of the 1998 house state-ticket residual
   (−3,276 D / −3,588 R) and of the 2002 prior-presidential residual
   (−10,381 D / −17,084 R). Candidate counties identified (1998: Franklin,
   Crenshaw, Dale; 2002 raw-string comparison: St. Clair), but the dropped rows
   were not reconstructed.
3. Reconciliation of the ~232k-vote 2014 Governor provenance gap between the
   OpenElections-derived allocation source and the canonical SOS warehouse
   totals.
4. Whether the 2014 U.S. Senate contest was omitted because it was uncontested
   (Sessions) — consistent with the producer's contested-only rule — was not
   verified from the raw 2014 ballot rows.
5. The published race-universe count. `CANONICAL_PIPELINES.md` release matrix and
   the task context state 509 races / 1,018 orientations; the current export
   (`race_war.csv`, `candidate_cycle_war.csv`) and `cmo_v5_races.csv` carry
   510 races / 1,020 orientations. Deferred to `alabama-02/03`.
6. 2002 HD26/HD27 and 2014 party-label dispositions (`warehouse-05`) are outside
   this audit.

## 10. Out-of-scope findings

- **2006 legislative returns cover only ~48 of 67 counties** in the canonical
  warehouse (18 counties entirely absent, 349,838 source votes). This is a
  warehouse source-coverage gap that affects every 2006 legislative-activity
  weighting and caused the 2006 prior-presidential allocation loss.
- **1998 Senate district 90** phantom allocation row (§7.3).
- **509 vs 510** published race-universe documentation mismatch (§9.5).
- **2014 OpenElections vs SOS** statewide executive totals differ by ~16% for
  Governor; the allocation product is internally reconciled at ratio 1.0.

## 11. Reproduced commands (selected)

All warehouse access read-only (`mode=ro`, `PRAGMA query_only=ON`), bounded SQL.

```sql
-- statewide source totals per cycle/office
select year, office, party_norm, sum(votes), count(*)
from vote_observations
where source='alabama_sos' and office in ('Governor','Attorney General')
  and year in (1994,1998,2002,2006,2010,2014,2018,2022)
group by year, office, party_norm;

-- 2010 party labels recovered from candidate_key (PARTY_2010)
select candidate_key, party_norm, sum(votes) from vote_observations
where source='alabama_sos' and year=2010 and office in ('Governor','Attorney General')
group by candidate_key, party_norm;

-- legislative district coverage per cycle
select year, office, count(distinct county_key), count(distinct district)
from vote_observations
where source='alabama_sos' and office in ('State House','State Senate')
  and district is not null and year in (1994,1998,2002,2006,2010,2014,2018,2022)
group by year, office;
```

Python (repository `.venv`) computed the allocated sums, fallback quantiles,
prior-presidential conservation and substitution checks from the CSVs listed in
§1. No builder, formatter or test suite was run.
