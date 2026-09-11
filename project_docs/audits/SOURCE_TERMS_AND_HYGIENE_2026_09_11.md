# Source terms and repository hygiene — 2026-09-11

**Task:** `RELEASE-08-SOURCE-TERMS-HYGIENE-20260911` (checklist `release-08`,
"Check source terms and repository hygiene"). **Status:** audit complete; read-only.
**Artifacts:** this file and `SOURCE_TERMS_AND_HYGIENE_2026_09_11.json`.
**Published lineage:** HEAD `d93dd8c6`; forecast build `b76d607f2d81e54697a3`;
Alabama historical `AL-HIST-WAR-V1-44F191EB8D939EF062CC`; Southern v3
`WAR-POST2016-V3-530FBD4238CC483E557C` (published mart run
`RUN-504CE4C4DF904D88A5A40D268F3FCEAB`); latest scoped warehouse repair
`RUN-DFB1D093D7594AB68A264292050E924D`.

Nothing outside these two files was written. The warehouse was opened read-only
(`sqlite3.connect('file:data/processed/elections/alabama_elections.sqlite?mode=ro', uri=True)`
with `PRAGMA query_only=ON`); queries were bounded aggregates.

## Method

1. `warehouse_source_file` (26,694 registrations, 59 distinct `provider` families)
   aggregated by provider for registration count and the share with a non-empty
   `license`, `original_url`, `retrieved_at_utc`, plus the distinct license strings.
2. Families that feed the four published products were traced through (a) the four
   product manifests' declared inputs, (b) `project_docs/data_catalog.csv`
   source-layer entries, and (c) the product lineage tables that carry
   `source_file_id`: `mart_southern_war_outcome` (published run),
   `canonical_southern_legislative_candidate_election`,
   `source_southern_legislative_observation_set`,
   `bridge_alabama_canonical_candidate_certified_result`, the
   `source_historical_*_county_result` tables, `vote_observations`, and the
   `source_southern_*` election/context/assignment/census-block/vest/finance/
   precinct-geometry/presidential-geography/incumbency tables.
3. Registered families not referenced by any product table were cross-checked
   against the scripts and manifests that read them (`git grep`, script inspection).
4. `docs/data` (31 files) and `docs/*.html` were searched for verbatim raw copies
   and for source attributions.

## 1. Source terms by family

Registry totals: **59 families, 26,694 registrations**; **2,153 registrations have no
license string** (unchanged from the count implied by the 2026-09-05 warehouse data
quality audit, 2,154, less the single 2026-09-08 URL+license repair on
`SRC-3F0ED360408C5AD273F6`). Of the 59 families, **48 are referenced by a product
lineage table** and **11 are registered without any product-table reference**
(`alabama_legislature`, `internet_archive_adah`, `shor_mccarty`, `pollster_document`,
`openelections`, `census_acs`, `us_census`, `census_vtd`, `vest_election_precinct`,
`alabama_reapportionment_archive`, `alabama_sos_lublin_archive`); those 11 are still
product-relevant through the scripts/manifests listed in section 7.

### Families traced to each published product

| Product | Declared inputs / lineage evidence | Families feeding it |
|---|---|---|
| 2026 forecast (`b76d607f…`, `docs/index.html`) | `alabama_war_v1/race_war.csv` + `manifest.json`, `post2016_southern_war_v3/manifest.json`, `historical_silver_a_generic_ballot_cycles.csv`, `2026_final_candidate_roster.csv`, `2026_candidate_incumbency.csv`, `2026_poll_adjusted_baseline.csv`, `robust_forecast_v1_error_components.csv` | `alabama_sos`, Klarner, MEDSL, `pollster_document`, Southern incumbency web roster/continuity builder, Southern incumbency research workbook, `us_census`, `census_acs`; plus unregistered Catalist, VoteHub, YouGov/Economist, Silver |
| Historical Alabama WAR (`AL-HIST-WAR-V1-44F191…`, `docs/cmo.html`) | `alabama_historical_war_v1/manifest.json` (Klarner/MEDSL Southern v3, Alabama v1, `candidate_research_aliases.csv`), `source_historical_*_county_result`, certified-canvass bridge, 1994 plan geometry | `alabama_sos`, `alabama_reapportionment_archive`, `census_vtd`, `vest_election_precinct`, `openelections`, Klarner, MEDSL, Project Southern WAR panel v1, Southern incumbency web roster; plus committed Wikipedia HTML |
| Ideology and caucuses (`docs/ideology-performance.html`, `docs/caucuses.html`, `docs/legislators.html`) | `candidate_position_evidence_v3_all_sources.csv` → `source_provider` in {`Alabama Legislature via LegiScan` (51,801 rows), `Vote Smart` (9,184 rows)}; historical journal roll-calls; archive bill ledger | `legiscan`, `alabama_legislature` (journals), `internet_archive_adah` (acts), `shor_mccarty`; plus unregistered Vote Smart |
| Southern WAR 2016–2024 (`WAR-POST2016-V3-530FBD42…`, `docs/southern-war.html`) | `post2016_southern_war_v3/manifest.json`; published `mart_southern_war_outcome` run `RUN-504CE4C4…`; `source_southern_*` context/geography/incumbency tables | `mart_southern_war_outcome` contributors: Klarner, MEDSL, `alabama_sos`, Virginia DoE, NC SBE, Louisiana SoS, Tennessee SoS, Florida Division of Elections, Oklahoma SEB, Arkansas SoS, Redistricting Data Hub/MS via OpenElections, Project Southern WAR panel v1; context/geography: U.S. Census Bureau, VEST, RDH, Daily Kos Elections, The New York Times, Virginia Voting Precincts project, MARIS/Georgia reapportionment via Election Geodata; incumbency: Southern incumbency workbook + continuity builder |

The finance overlay (`DIME`, `Alabama Secretary of State FCPA`, the state campaign-finance agencies) is displayed but is **not** a headline WAR input, so its families are listed in the table but excluded from the "headline feeding families" count. Counting the roles above, **59 registered families** are described here; the finance-overlay-only payees are `Alabama Secretary of State FCPA`, the Arkansas/Georgia/Kentucky/Louisiana/Missouri/Oklahoma/South Carolina/Tennessee/Texas finance agencies, `FollowTheMoney.org`, `DIME`, `Reviewed Southern campaign-finance identity adjudications` and `Southern candidate-cycle finance canonical builder`.

| Family (warehouse_source_file.provider) | Role | Regs | License | URL | Retrieved | License strings |
|---|---|---:|---:|---:|---:|---|
| Virginia Department of Elections | election_results | 10366 | 10366 (100%) | 10366 (100%) | 10366 (100%) | official public record; reuse terms not recorded in acquisition manifest; review required; official public record; reuse terms not recorded; review required; official public records; reuse terms not stated |
| Kentucky State Board of Elections | election_results | 2053 | 2053 (100%) | 2053 (100%) | 2053 (100%) | official public record; reuse terms not recorded in acquisition manifest; review required |
| Louisiana Secretary of State | election_results | 931 | 931 (100%) | 931 (100%) | 931 (100%) | official public record; reuse terms not recorded in acquisition manifest; review required |
| Arkansas Secretary of State | election_results | 618 | 618 (100%) | 618 (100%) | 618 (100%) | official public record; reuse terms not recorded in acquisition manifest; review required; official public records; reuse terms not stated; official public records; reuse terms not stated on download page |
| Mississippi Secretary of State | election_results | 511 | 511 (100%) | 511 (100%) | 511 (100%) | official public record; reuse terms not recorded in acquisition manifest; review required; official public records; reuse terms not stated |
| Tennessee Secretary of State | election_results | 346 | 346 (100%) | 346 (100%) | 346 (100%) | official public record; reuse terms not recorded in acquisition manifest; review required |
| South Carolina Election Commission | election_results | 255 | 255 (100%) | 255 (100%) | 255 (100%) | official public record; reuse terms not recorded in acquisition manifest; review required |
| North Carolina State Board of Elections | election_results | 184 | 184 (100%) | 184 (100%) | 184 (100%) | Official NCSBE public download; reuse terms not separately stated; official public election-result download; official public record; reuse terms not recorded in acquisition manifest; review required; official public records; reuse terms not stated; official public records; reuse terms not stated on download page |
| Florida Division of Elections | election_results | 21 | 21 (100%) | 21 (100%) | 21 (100%) | official public record; reuse terms not recorded in acquisition manifest; review required; official public records; reuse terms not stated |
| Oklahoma State Election Board | election_results | 17 | 17 (100%) | 17 (100%) | 17 (100%) | official public record; reuse terms not recorded in acquisition manifest; review required |
| MIT Election Data and Science Lab | election_results | 12 | 12 (100%) | 12 (100%) | 12 (100%) | reuse terms not retained with local artifact; review required |
| Missouri Secretary of State | election_results | 11 | 11 (100%) | 11 (100%) | 11 (100%) | official public record; reuse terms not recorded in acquisition manifest; review required |
| OpenElections | election_results | 2 | 2 (100%) | 2 (100%) | 2 (100%) | OpenElections public repository; converted Mississippi county results; OpenElections public repository; underlying Georgia SOS/Clarity results |
| alabama_sos_lublin_archive | election_results | 1 | 0 (0%) | 0 (0%) | 1 (100%) | **(none)** |
| Redistricting Data Hub; Mississippi SOS via OpenElections | election_results | 1 | 1 (100%) | 1 (100%) | 1 (100%) | reuse terms not retained with local artifact; review required |
| OpenElections conversion of Mississippi Secretary of State | election_results | 1 | 1 (100%) | 1 (100%) | 1 (100%) | OpenElections public repository; converted official Mississippi county results |
| Carl Klarner, State Legislative Election Returns, 1967-2022 | election_results | 1 | 1 (100%) | 1 (100%) | 1 (100%) | reuse terms not retained with local artifact; review required |
| alabama_sos | election_administration | 24 | 2 (8%) | 13 (54%) | 24 (100%) | review: public official election record; explicit redistribution license not established |
| openelections | election_identity | 5 | 0 (0%) | 0 (0%) | 5 (100%) | **(none)** |
| Florida Department of State Division of Elections | context_geography | 1485 | 1485 (100%) | 1485 (100%) | 1485 (100%) | official public precinct-level election-result download; official public records; reuse terms not stated on download page |
| Voting and Election Science Team | context_geography | 15 | 15 (100%) | 15 (100%) | 15 (100%) | CC BY 4.0; preserve VEST citation and state validation report; CC BY 4.0; preserve VEST citation and validation report |
| vest_election_precinct | context_geography | 3 | 0 (0%) | 0 (0%) | 3 (100%) | **(none)** |
| Redistricting Data Hub | context_geography | 3 | 3 (100%) | 3 (100%) | 3 (100%) | Redistricting Data Hub public download; preserve README and attribution |
| alabama_reapportionment_archive | context_geography | 2 | 0 (0%) | 0 (0%) | 2 (100%) | **(none)** |
| The New York Times | context_geography | 2 | 2 (100%) | 2 (100%) | 2 (100%) | New York Times 2024 precinct-data license; attribution and license review required |
| Virginia Voting Precincts project | context_geography | 1 | 1 (100%) | 1 (100%) | 1 (100%) | GPL-3.0; compiled from Virginia official and local GIS evidence |
| Virginia Department of Elections historical database | context_geography | 1 | 1 (100%) | 1 (100%) | 1 (100%) | official public historical election-result export |
| Redistricting Data Hub redistribution of VEST | context_geography | 1 | 1 (100%) | 1 (100%) | 1 (100%) | CC BY 4.0; preserve VEST and RDH attribution and embedded README |
| Mississippi Automated Resource Information System via Election Geodata | context_geography | 1 | 1 (100%) | 1 (100%) | 1 (100%) | MARIS metadata states no access/use limitations; Election Geodata credit requested |
| Georgia Legislative and Congressional Reapportionment Office via Election Geodata | context_geography | 1 | 1 (100%) | 1 (100%) | 1 (100%) | Election Geodata permits reuse without permission; credit requested |
| Daily Kos Elections | context_geography | 1 | 1 (100%) | 1 (100%) | 1 (100%) | publicly accessible Daily Kos Elections research page; attribution required |
| U.S. Census Bureau | census_geography | 110 | 110 (100%) | 110 (100%) | 110 (100%) | U.S. Census Bureau public data; TIGER/Line attribution required; U.S. Census Bureau public data; no copyright restriction |
| census_vtd | census_geography | 1 | 0 (0%) | 0 (0%) | 1 (100%) | **(none)** |
| us_census | census_demographics | 12 | 0 (0%) | 8 (67%) | 4 (33%) | **(none)** |
| census_acs | census_demographics | 8 | 0 (0%) | 8 (100%) | 8 (100%) | **(none)** |
| pollster_document | polling | 8 | 0 (0%) | 8 (100%) | 8 (100%) | **(none)** |
| Southern state legislative incumbency research workbook | incumbency | 1 | 1 (100%) | 0 (0%) | 1 (100%) | project-derived or supplied research input; upstream terms retained separately |
| Southern incumbency web roster and reviewed continuity builder | incumbency | 1 | 1 (100%) | 0 (0%) | 1 (100%) | project-derived or supplied research input; upstream terms retained separately |
| Tennessee Registry of Election Finance | finance | 5834 | 5834 (100%) | 5834 (100%) | 5834 (100%) | official public records; reuse terms not stated; official public records; reuse terms not stated on download page |
| Georgia Government Transparency and Campaign Finance Commission | finance | 1445 | 1445 (100%) | 1445 (100%) | 1445 (100%) | official public records; reuse terms not stated; official public records; reuse terms not stated on download page |
| Arkansas Secretary of State predecessor filing archive | finance | 129 | 129 (100%) | 129 (100%) | 129 (100%) | official public records; reuse terms not stated |
| South Carolina State Ethics Commission | finance | 38 | 38 (100%) | 38 (100%) | 38 (100%) | official public records; reuse terms not stated; official public records; reuse terms not stated on download page |
| Alabama Secretary of State FCPA | finance | 36 | 36 (100%) | 36 (100%) | 36 (100%) | official public records; reuse terms not stated; official public records; reuse terms not stated on download page |
| Oklahoma Ethics Commission Guardian | finance | 18 | 18 (100%) | 18 (100%) | 18 (100%) | official public records; reuse terms not stated on download page |
| FollowTheMoney.org | finance | 16 | 16 (100%) | 16 (100%) | 16 (100%) | Institute data attribution required; public research table |
| Kentucky Registry of Election Finance | finance | 15 | 15 (100%) | 15 (100%) | 15 (100%) | official public records; reuse terms not stated |
| Louisiana Board of Ethics | finance | 9 | 9 (100%) | 9 (100%) | 9 (100%) | official public records; reuse terms not stated on download page |
| Missouri Ethics Commission | finance | 7 | 7 (100%) | 7 (100%) | 7 (100%) | official public records; reuse terms not stated |
| Arkansas Secretary of State Financial Disclosure | finance | 2 | 2 (100%) | 2 (100%) | 2 (100%) | official public records; reuse terms not stated |
| Texas Ethics Commission | finance | 1 | 1 (100%) | 1 (100%) | 1 (100%) | official public records; reuse terms not stated on download page |
| Southern candidate-cycle finance canonical builder | finance | 1 | 1 (100%) | 0 (0%) | 1 (100%) | project-derived or supplied research input; upstream terms retained separately |
| Reviewed Southern campaign-finance identity adjudications | finance | 1 | 1 (100%) | 0 (0%) | 1 (100%) | project-derived or supplied research input; upstream terms retained separately |
| DIME | finance | 1 | 1 (100%) | 1 (100%) | 0 (0%) | ODC-BY 1.0 |
| alabama_legislature | ideology_legislation | 1157 | 0 (0%) | 1157 (100%) | 1157 (100%) | **(none)** |
| internet_archive_adah | ideology_legislation | 170 | 0 (0%) | 170 (100%) | 170 (100%) | **(none)** |
| legiscan | ideology_legislation | 31 | 31 (100%) | 31 (100%) | 31 (100%) | CC BY 4.0 |
| shor_mccarty | ideology_scale | 1 | 1 (100%) | 1 (100%) | 1 (100%) | CC0 1.0 |
| usdoj_crt_section5 | precinct_history | 764 | 0 (0%) | 764 (100%) | 764 (100%) | **(none)** |
| Project Southern WAR panel v1 | derived_research | 1 | 1 (100%) | 0 (0%) | 1 (100%) | internal derived research artifact |

### Families without terms

**11 families have zero license strings, covering 2,131 registrations.**

| Family | Regs | License | URL | Retrieved |
|---|---:|---:|---:|---:|
| alabama_legislature | 1157 | 0 (0%) | 1157 (100%) | 1157 (100%) |
| usdoj_crt_section5 | 764 | 0 (0%) | 764 (100%) | 764 (100%) |
| internet_archive_adah | 170 | 0 (0%) | 170 (100%) | 170 (100%) |
| us_census | 12 | 0 (0%) | 8 (67%) | 4 (33%) |
| pollster_document | 8 | 0 (0%) | 8 (100%) | 8 (100%) |
| census_acs | 8 | 0 (0%) | 8 (100%) | 8 (100%) |
| openelections | 5 | 0 (0%) | 0 (0%) | 5 (100%) |
| vest_election_precinct | 3 | 0 (0%) | 0 (0%) | 3 (100%) |
| alabama_reapportionment_archive | 2 | 0 (0%) | 0 (0%) | 2 (100%) |
| census_vtd | 1 | 0 (0%) | 0 (0%) | 1 (100%) |
| alabama_sos_lublin_archive | 1 | 0 (0%) | 0 (0%) | 1 (100%) |

**One family is partially licensed:** `alabama_sos` — 2 of 24 registrations record a
license (the 2018 and 2022 certified canvass PDFs: *"review: public official election
record; explicit redistribution license not established"*); the other 22 (precinct zips,
county/statewide workbooks, the Lublin archive) record none, and only 13 of 24 record a URL.
2,131 + 22 = **2,153 missing terms**, matching the 09-08 expectation.

## 2. What is published from each flagged family

All four products publish **derived aggregates, scores and manifests**; no product
publishes a verbatim raw source file. `docs/data` holds 31 files: race- and
candidate-cycle-level WAR exports, forecast seat/scenario outputs, coverage and
manifest files, the Census geography manifest and the poll source manifest.

### alabama_legislature

Registrations 1157; license recorded 0; URL 1157; retrieval time 1157.

Derived only. Journal PDFs feed extract_historical_house/senate_journal_rollcalls.py -> historical_*_journal_rollcalls.csv -> frontier roll-call ontology -> published ideology summaries (docs/ideology-performance.html, docs/legislators.html). No journal page image or text is published; no Alabama Legislature attribution appears in docs/.

### usdoj_crt_section5

Registrations 764; license recorded 0; URL 764; retrieval time 764.

Derived/context only. Section 5 notices feed source_doj_section5_notice / precinct_change_event and precinct-history evidence for Alabama allocation decisions. No DOJ row is published in docs/data or docs/*.html.

### internet_archive_adah

Registrations 170; license recorded 0; URL 170; retrieval time 170.

Derived only. Acts scanned by ADAH via archive.org feed build_frontier_archive_bill_ledger.py -> archive bill ledger -> ideology ontology/evidence. No act text is published; no ADAH attribution appears in docs/.

### us_census

Registrations 12; license recorded 0; URL 8; retrieval time 4.

Derived only. 1990 SF3 Alabama extracts feed district context/demographic features consumed by WAR baselines. Census data is a U.S. Government work; no raw census table is published, but no license string is registered for these 12 files.

### pollster_document

Registrations 8; license recorded 0; URL 8; retrieval time 8.

Manifest + derived only. The 8 poll documents (Fox/Beacon, Echelon, Cygnal, Quinnipiac, CNBC-Hart) feed the forecast national environment. docs/data/poll_source_manifest.csv republishes filename, pollster, source URL, retrieved_utc, bytes and sha256 (no poll content); docs/data/polling_environment.csv publishes derived environment shares. Terms are not recorded.

### census_acs

Registrations 8; license recorded 0; URL 8; retrieval time 8.

Derived only. ACS 2022 block-group tables feed demographic features. docs/data/2026_sld_demographics.csv publishes derived district demographic aggregates (31,552 B). ACS is public-domain U.S. Government data but these 8 files carry no license string.

### openelections

Registrations 5; license recorded 0; URL 0; retrieval time 5.

Committed raw + derived. All 5 registered files are tracked in Git under data/raw/openelections/ (19.2 MB) and feed precinct identity enrichment and historical allocation. No license or URL is registered for them; no OpenElections attribution appears in docs/.

### vest_election_precinct

Registrations 3; license recorded 0; URL 0; retrieval time 3.

Derived only. VEST precinct packages (2016/2018 AL) feed precinct_snapshot geometry and allocation. Derived allocations appear in historical WAR exports; no raw VEST package is published. Sibling VEST registrations carry CC BY 4.0, but these 3 carry no license string.

### alabama_reapportionment_archive

Registrations 2; license recorded 0; URL 0; retrieval time 2.

Derived only. 1992-2000 House/Senate plan shapefiles supply the 1994 plan geometry used by historical Alabama WAR allocation. Only derived residuals/maps are published; no terms or URL recorded.

### census_vtd

Registrations 1; license recorded 0; URL 0; retrieval time 1.

Derived only. tl_2012_01_vtd10.zip supplies an observed precinct geometry snapshot used by precinct allocation. Only derived map output is published; no terms or URL recorded.

### alabama_sos_lublin_archive

Registrations 1; license recorded 0; URL 0; retrieval time 1.

Derived/context only. Registered single archive artifact used for Alabama historical context; no terms, retrieval of URL, or independent published copy; only derived series appear in docs/data.

### alabama_sos

Registrations 24; license recorded 2; URL 13; retrieval time 24.

Derived only. Official SOS precinct and county returns plus the two certified canvass PDFs feed historical Alabama WAR and the certified-canvass bridge. docs/data publishes race-level/candidate-cycle derived aggregates and coverage; the southern historical export labels rows source_provider=Official state election authority. Raw precinct zips/PDFs are not published. Only the 2 certified canvass PDFs record a review-required license string.

### Terms that restrict or require review before redistribution

- **Attribution required (compatible with derived publication only if credited):**
  `legiscan` CC BY 4.0 (31 files) — its rows are attributed inside the evidence table
  as `Alabama Legislature via LegiScan`, but **no LegiScan attribution appears in
  `docs/`**; `DIME` ODC-BY 1.0 (1); `FollowTheMoney.org` (16); `Voting and Election
  Science Team` CC BY 4.0 (15); `Redistricting Data Hub` (3); `Daily Kos Elections`;
  `U.S. Census Bureau` TIGER/Line attribution (20 of 110).
- **Explicit review required:** `The New York Times` (*"attribution and license review
  required"*, 2 precinct files feeding derived baselines); the Alabama SOS certified
  canvass (*"explicit redistribution license not established"*, 2); and roughly 4,013
  election-file rows plus the state finance files recorded as
  *"official public record; reuse terms not recorded … review required"*. Fourteen
  rows are recorded as *"reuse terms not retained with local artifact; review
  required"* (MIT Election Data and Science Lab 12, Klarner 1, RDH/MS 1).
- **Unregistered families with no recorded terms:** the **Catalist** "What Happened
  2024" workbook (its demographic-transfer selection is a **published forecast branch**,
  `status=catalist_yougov_demographic_transfer_selected`), **VoteHub** (CC BY 4.0 exists
  only as an in-code constant in `scripts/download_votehub_generic_ballot.py`),
  **Vote Smart** (9,184 rows in the ideology evidence table, no registry row), the
  eight committed Wikipedia HTML pages (CC BY-SA implied, not recorded) and the
  committed Split Ticket source page.
- **The ideology evidence layer is largely unregistered.** The published payload's
  source table `data/processed/ideology/candidate_position_evidence_v3_all_sources.csv`
  (63,881 rows) carries **193 distinct `source_provider` strings**, of which only
  `LegiScan` exactly matches a registered `warehouse_source_file.provider`. The largest
  are `Alabama Legislature via LegiScan` (51,801 rows), `Vote Smart` (9,184) and the
  interest-group/news channels (NRA-PVF 628, NFIB-Alabama 684, Alabama AFL-CIO,
  Alabama Political Reporter, AL.com, BirminghamWatch, and roughly 180 more). None of
  these evidence channels records a license or terms; only their derived ideology
  scores reach `docs/`.
- **Finding (not an adjudication):** no registered family records terms that flatly
  prohibit the derived aggregates currently published. The two cases that cannot be
  shown compliant on the present evidence are (i) the unregistered Catalist workbook,
  whose derived branch is published without any terms record, and (ii) the missing
  LegiScan/Vote Smart attribution on the published ideology pages. The New York Times
  and Alabama SOS certified-canvass strings say review is required before
  redistribution, and the 11 zero-license families give no redistribution basis at all.

## 3. Committed raw material

`git ls-files data/raw` returns **15 tracked files, 27,528,289 bytes (27.5 MB)**:

| Path | Bytes | Family |
|---|---:|---|
| `data/raw/README.md` | 1,093 | readme |
| `data/raw/openelections/20121106__al__general__precinct.csv` | 1,007,747 | openelections |
| `data/raw/openelections/20141104__al__general__precinct.csv` | 4,730,350 | openelections |
| `data/raw/openelections/20161108__al__general__precinct.csv` | 2,262,986 | openelections |
| `data/raw/openelections/20181106__al__general__precinct.csv` | 7,806,381 | openelections |
| `data/raw/openelections/20201103__al__general__precinct.csv` | 2,827,690 | openelections |
| `data/raw/reference_pages/split_ticket_2024_war/source.html` | 462,282 | split_ticket_2024_war |
| `data/raw/wikipedia/2010_house.html` | 981,507 | wikipedia |
| `data/raw/wikipedia/2010_senate.html` | 624,600 | wikipedia |
| `data/raw/wikipedia/2014_house.html` | 1,015,147 | wikipedia |
| `data/raw/wikipedia/2014_senate.html` | 505,988 | wikipedia |
| `data/raw/wikipedia/2018_house.html` | 963,823 | wikipedia |
| `data/raw/wikipedia/2018_senate.html` | 718,368 | wikipedia |
| `data/raw/wikipedia/2022_house.html` | 2,390,730 | wikipedia |
| `data/raw/wikipedia/2022_senate.html` | 1,229,597 | wikipedia |

- Family totals: `openelections` 5 files / 18,635,154 B; `wikipedia` 8 files /
  8,429,760 B; `split_ticket_2024_war` 1 file / 462,282 B; `data/raw/README.md` 1,093 B.
- `.gitignore` coverage: `/data/raw/**` with `!/data/raw/README.md` (`.gitignore:18-19`).
  `git check-ignore --no-index` confirms the pattern **matches** the 14 raw files; they
  remain committed because the ignore rule does not un-track already tracked paths.
  So `.gitignore` protects *new* raw material but the 14 files stay in the tree.
- Registry coverage of committed raw: only the 5 `openelections` CSVs have a
  `warehouse_source_file` row, and those rows have **no license and no URL**.
  The 8 Wikipedia pages and the Split Ticket page have **no registry row at all**.
- `*.sqlite` is ignored and **no SQLite file is tracked**; the 5.8 GB warehouse is local only.

## 4. Oversized tracked files

Checked all **36,567 tracked files** with `os.path.getsize`
(the `git ls-files -z | xargs -0 stat` equivalent).

- **Files > 50 MB: 0.**
- Largest tracked file: `data/processed/legislative/comprehensive_rollcall_direction_review_queue.csv` at
  40.24 MB — under the threshold.
- The large analytical CSVs (roll-call ledgers, ideology evidence, finance reports)
  are ignored/generated rather than committed blobs; no oversized binary raw source
  is tracked.

## 5. Credential scan

Bounded regex scan over **36,446 tracked text files < 5 MB**
(extensions `.py .md .txt .csv .json .yaml .yml .toml .ini .cfg .html .js .ts .css
.sql .sh .ps1 .bat .xml .env .rst .ipynb`, plus `LICENSE`/`Makefile`/`Dockerfile`),
reading each file line by line; 63 text-extension tracked files above 5 MB (largest
40.2 MB) were skipped, and the 58 tracked files with non-text extensions were out of scope.

| Pattern | Matches |
|---|---:|
| `AKIA[0-9A-Z]{16}` (AWS access key) | 0 |
| `-----BEGIN … PRIVATE KEY-----` | 0 |
| `ghp_…` / `github_pat_…` | 0 |
| `sk-…` (OpenAI-style) | 0 |
| `xox[baprs]-…` (Slack) | 0 |
| `AIza…` (Google API) | 0 |
| JWT (`eyJ….*….*…`) | 0 |
| assigned `api_key`/`secret`/`token`/`password` string literals | 0 |
| assigned `API_KEY`/`SECRET_KEY`/`ACCESS_TOKEN`/`PASSWORD` constants | 0 |

- **No credential match was found.**
- **`.env` is ignored** (`.gitignore:2`); `token.env` and `.env` are listed in the same
  block. `.env` exists on disk (238 B) but is not tracked; **0 tracked `.env`-like files**.
- No tracked `*.pem`, `*.key`, `id_rsa*`, `*.p12` or `*.pfx` file exists.
- This scan is pattern-based; it cannot prove the absence of every possible secret, and
  it did not inspect files ≥ 5 MB or binary blobs.

## 6. Repository hygiene script output (verbatim)

Command (dispatcher `audit` target):

```
.venv/Scripts/python.exe scripts/audit_repository_hygiene.py
```

Exit code: **0**. Output, recorded verbatim:

```
Repository hygiene audit passed: canonical publication boundary is clean.
```

The script is read-only (no writes, no side effects) and checks: no legacy
`docs/data/cmo_v2_|cmo_v3_|preliminary_cmo_` export; no code under `scripts/` or
`dashboard/` reading `docs/data`; `build_war_story_page.py` not consuming legacy CMO
exports; `data_catalog.csv` not advertising a legacy public CMO export. Nothing was fixed.

## 7. Proposed terms-completion list

No repair is applied here. The list below names the registered/derived locations that
already carry terms evidence for each missing-license group, so a later authorized
pass could backfill `warehouse_source_file.license` without new network access.

1. **11 families with zero license registrations (2,131)**
   - data/processed/source_audits/southern_legislative_geography_manifest.csv (license_or_terms, 116 rows, Census)
   - data/processed/source_audits/southern_2020_census_block_manifest.csv (license_or_terms, 14 rows, Census)
   - data/processed/source_audits/southern_war_v4_acs_manifest.csv (license_or_terms, 70 rows, ACS)
   - data/processed/source_audits/southern_2016_vest_manifest.csv (license_or_terms, 14 rows, VEST)
   - scripts/acquire_southern_sld_acs_v4.py in-code Census constant
   - the 15 Voting and Election Science Team registrations already carrying CC BY 4.0 strings

2. **alabama_sos 22 missing licenses**
   - data/raw/alabama_elections_and_geography/2018_general_certified_canvass.manifest.json and 2022_...manifest.json (license_or_terms present)
   - data/processed/source_audits/southern_sos_download_manifest.csv (3630 rows; no license column -> would need extension)
   - scripts/load_alabama_2018_certified_source.py / load_alabama_2022_certified_source.py (read license_or_terms from the certified manifest)
   - the 09-08 repair record SRC-3F0ED360408C5AD273F6 (qa_warehouse_source_repair) shows URL+license backfill precedent

3. **legiscan attribution (31 files already CC BY 4.0)**
   - data/processed/source_audits/southern_legislative_history_source_manifest.csv (15 rows, license_or_terms)
   - docs/ideology-performance.html (needs a LegiScan attribution line; no license field exists)

4. **pollster_document 8 missing licenses**
   - project_docs/audits/FORECAST_POLLING_SNAPSHOT_POLICY_2026_09_11.md (documents per-poll terms status, mostly unknown)
   - docs/data/poll_source_manifest.csv (published; has source_url/retrieved/bytes/sha256 but no license column)

5. **finance overlay payees (DIME, FollowTheMoney, state ethics agencies)**
   - data/processed/source_audits/southern_campaign_finance_manifest.csv (license_or_terms, 2727 rows)
   - data/processed/source_audits/southern_finance_summary_manifest.csv (license_or_terms, 17356 rows)
   - data/processed/source_audits/southern_campaign_finance_coverage.csv (17 rows, provider coverage; no license column)

6. **Alabama journals / ADAH acts / DOJ / reapportionment archive / Lublin archive (no manifest carries terms)**
   - scripts/download_adah_house_journals.py and scripts/download_alabama_historical_acts.py (acquisition scripts; may embed source-page evidence)
   - Internet Archive item metadata for the ADAH acts (network; out of scope)
   - Federal public-record convention for usdoj_crt_section5 (17 U.S.C. sec.105)
   - no manifest found for alabama_reapportionment_archive or alabama_sos_lublin_archive

## 8. What this audit does NOT establish

- Reuse terms for 11 families (2,131 registrations) and 22 Alabama SOS registrations are not recorded anywhere in the warehouse registry; this audit does not establish that those sources may be redistributed.
- The published forecast demographic branch (status=catalist_yougov_demographic_transfer_selected) is Catalist-derived; the Catalist workbook is not registered in warehouse_source_file and no terms are recorded, so its compatibility with publication is not established here.
- Vote Smart is a source_provider in the ideology evidence table (9,184 rows) but is not registered in warehouse_source_file; its terms are not recorded.
- VoteHub supplies the live 2026 environment; its CC BY 4.0 string exists only as an in-code constant in download_votehub_generic_ballot.py and no attribution appears in docs/.
- Attribution presence/absence in docs/ was checked by text search only; this audit does not certify that the published pages meet every attribution requirement of CC BY 4.0, ODC-BY 1.0 or CC0.
- The 8 Wikipedia HTML files and 1 Split Ticket HTML file are tracked raw material with no warehouse registration and no recorded license; their presence in the repository is not adjudicated here.
- This audit does not re-verify the 2026-09-11 warehouse/index state beyond the read-only queries and commands recorded; it does not re-run any product build.

## 9. Out-of-scope observations

- No Catalist, Vote Smart or VoteHub provider is registered in warehouse_source_file; their raw files live under data/raw/polling and data/raw/ideology outside the registry.
- The committed Wikipedia HTML (8 files) and Split Ticket source.html (1 file) are not registered; only 5 of the 14 committed raw files (openelections) have a registry row.
- The warehouse-level source manifests that already carry license_or_terms (southern_legislative_geography_manifest.csv, southern_2016_vest_manifest.csv, southern_2020_census_block_manifest.csv, southern_war_v4_acs_manifest.csv, southern_legislative_history_source_manifest.csv, southern_campaign_finance_manifest.csv, southern_finance_summary_manifest.csv, *certified_canvass.manifest.json) are candidate inputs for a terms-completion pass, not corrections applied here.
- The 30 superseded docs/data downloads removed on 2026-09-11 (checkpoint 4) are out of scope; the audit covers the current 31 files.

