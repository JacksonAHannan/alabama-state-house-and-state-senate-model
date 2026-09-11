# Central warehouse data-quality audit — 2026-09-05

## Scope and conclusion

Read-only audit of `data/processed/elections/alabama_elections.sqlite`:
5,746,839,552 bytes, 118 tables, 22 views, schema versions 1–25.
Database modification time: `2026-09-04T22:12:44.054212+00:00`.
Queries and source inspections were performed on 2026-09-05 UTC.
Repository HEAD: `88878b973fdac3cee95a8d8648da321e38e0021c`;
the working tree contains uncommitted changes, so HEAD alone does not identify
the inspected implementation. Relevant working-file hashes appear below.

The database is structurally readable, but some normalized data and supposedly
canonical interfaces contain confirmed processing defects. A passing test suite
or a successful import is not sufficient evidence of analytical readiness.
No database, raw source, loader, model, or publication output was changed by
this audit. This report is the only new audit deliverable.

## Priority findings

### WQA-01 — High: Jefferson 2014 county totals are counted as precincts

`vote_observations` contains **105** Alabama SOS rows with
`county_key='JEFFERSON'`, `year=2014`, and
`precinct_key='TOTAL OF REGISTERED VOTERS'`. Every one exactly equals the sum
of the corresponding remaining precinct rows. All 105 also appear in
`canonical_vote_observations`.

Thus, summing this county's records doubles the affected contest-option totals.
Of these rows, 23 are State House records and 9 are State Senate records.
Their repeated legislative counts total 142,053 and 136,449, respectively;
these are sums across contests, not counts of distinct voters.

Source evidence: `2014General-precinctLevel.zip`, member
`Jefferson 2014 General Precinct.xls`, sheet `Jefferson_Crosstab`, column D.
The source header says `Total Of Registered Voters`, but its candidate-specific
values demonstrably restate the precinct sums. Example: the Governor rows
contain 83,147 and 82,865 in both the summary and the remaining precinct sums.
Snapshot rowids for those summary rows are 1319667 and 1319844; rowids are
diagnostic locators, not stable identifiers.

Cause: `sos_precinct._wide_sheet` treats every numeric column after the first
three fields as a precinct. Unlike the OpenElections adapter, this path has no
summary-column exclusion. Canonical source ranking does not validate row grain.

Recommended repair: retain this column as reconciliation evidence, exclude it
from additive precinct facts, then rebuild and reconcile affected consumers.
Do not assume that separately consolidated candidate totals are also doubled:
`build_candidate_identity.reconcile_official_candidate_results` provides a
separate authority path for those records.

### WQA-02 — High: all 4,029 Marshall 2002 rows have shifted metadata

Every Marshall County 2002 row in `vote_observations` has `office='MARSHALL'`.
Candidate values are party codes (`DEM`, `REP`, `LIB`, `WI`, `TBC`) or blank;
the party field contains contest titles. All **4,029** rows survive into the
canonical vote view. Of these, 306 have blank candidate names, and 79 come from
the `TOTAL OF NUMBER VOTES` summary column.

Source evidence: `2002-GeneralElection-PrecinctLevel_0.xls`, sheet `MARSHALL`.
The header has an extra column:

| Excel column | Actual content |
|---|---|
| C | Repeated county label |
| D | Actual contest title |
| E | Party code |
| F | Candidate name |
| G | County total |
| H onward | Precinct results |

Cause: `_legacy_2002` unconditionally takes `row[2:5]` as contest/party/candidate
and starts numeric observations at column G. That layout assumption is wrong
for this sheet. A Governor example has 10,426 in its county-total cell but sums
to 20,852 after the total and precinct detail are both loaded.

Recommended repair: add a fixture for this actual layout, select the proper
header positions, separate county totals, and reparse the affected source.
Deduplication cannot recover the missing names and offices.

### WQA-03 — High: apparent duplicates include lost precinct identities

At the declared normalized key
`source/year/county_key/precinct_key/office/district/candidate_key`, the Alabama
vote table has **25,754 collision groups**, representing **44,820 rows beyond
one per key**. Of those groups, 24,910 contain different vote values.
Across all 14 stored columns, there are also **1,949 identical-row groups**,
with **2,927 repeated rows**; 1,351 of those repeated rows have positive votes.

These counts are not permission to delete those rows. For example, the 1994
Jackson workbook lists distinct precinct numbers under repeated place names:
Bridgeport has identifiers 38249, 38248, 38250, and 44653 in column C.
The parser chooses the name in column B instead of preserving both fields.
Scottsboro consequently has 12 rows per Governor candidate but only one
`precinct_nodes` entry. The same-name pieces are legitimate source observations,
not twelve copies of one polling-place result.

Cause: `_legacy_1994` uses `row[1] or row[2]` as the precinct identifier.
`build_election_database._observations` also discards adapter `source_file` and
`party_method`; no source member/sheet/row or value-review status survives in
the table. This makes source-level duplicate adjudication and geographic joins
unnecessarily ambiguous. Marshall's shifted metadata contributes additional
collisions, so this is not one uniform defect.

Recommended repair: restore source-scoped precinct codes and cell/row lineage
before investigating true duplicates or rebuilding affected geographic joins.
Do not apply `DISTINCT` to the existing table as a cleanup shortcut.

### WQA-04 — High: 1994 party corrections exist only downstream

All **3,026** stored 1994 Attorney General observations for `SESSIONS`, across
65 counties, have `party_norm='D'`. The other candidate is also labeled D.
This conflicts with the project's explicit correction in
`build_1994_cmo_baseline.PARTY_CORRECTIONS`, which maps Sessions to R.

The source export code is `AG2`. `_legacy_1994` tests `code.startswith('A')`
before the second-position rule, classifying `AG2` as Democratic. The correction
is applied locally by the historical-baseline loader, not in the shared vote
view. Consumers therefore receive different party classifications depending
on which interface they use. This is a demonstrated project-internal
inconsistency, not a new independent adjudication of historical party evidence.

There is also one **144.4-vote** source observation: Morgan, precinct 26001,
Sessions, Attorney General. It is present in `MORGAN.XLS`, Excel row 48,
column K, inside `94g-prec.zip`; it is not floating-point noise introduced by
allocation. It enters the canonical view without a review label.

Recommended repair: make party evidence/corrections shared and auditable, and
review the fractional source value against independent evidence. Do not round
or replace the immutable source silently. The fractional value is a source
anomaly; accepting it without an explicit quality status is the pipeline issue.

### WQA-05 — Medium: nine invalid geometries belong to a passed layer

All **53,510** stored WKB geometries were decoded and checked. Nine Arkansas
2016 precinct geometries are invalid: five self-intersection/ring defects and
four components with too few points. All nine belong to a layer marked
`passed` and have `accepted` result-to-geometry links.

Affected geography IDs:

```text
GEOUNIT-D2AB495E957DB31AA5FFBE6F
GEOUNIT-4BB7E1079874E93CB66064FB
GEOUNIT-B74B209FF1E3A9C8C2CDB0EC
GEOUNIT-E64696D68BBE2ECAE4D386A8
GEOUNIT-AA174F910D3FDCB7A097396B
GEOUNIT-D1A7A85F058E1A9B2891F5BB
GEOUNIT-14261028F3F8864F59FDC78A
GEOUNIT-876D9FFDB1516453BBCA6D68
GEOUNIT-0EAB80ED2EB925955AD4F0C5
```

The VEST loader checks validity before reprojection to EPSG:4326, then stores
the transformed geometries without another validity gate. That is a concrete
validation gap and a plausible explanation; the exact transformation history
of each defect was not independently replayed.

Recommended repair: validate final stored geometry, repair only normalized
copies with recorded lineage, and recheck affected spatial operations. This
audit does not establish that existing district allocations are numerically
wrong. Geometry hashes, stored bounding boxes, CRS labels, and coordinate
ranges all passed the checks performed.

### WQA-06 — Medium: 24 LegiScan roll calls have unresolved tally conflicts

For **24** of 31,257 roll calls, reported totals and category counts disagree
with stored individual member votes. The corresponding raw JSON members were
inspected for all 24: their member arrays have exactly the same lengths as the
warehouse, with no duplicate person IDs in those arrays. The inconsistency is
already in the provider data, not evidence that ingestion dropped those rows.

Examples: roll call 309294 reports 204 but has 102 member records; 445297
reports 35 but has 12; 1185411 reports 105 but has 35.

The importer writes `legiscan_rollcall_qa.csv`, but no corresponding LegiScan
reconciliation table exists in the warehouse, and the source roll-call/member
interfaces contain no reconciliation-readiness flag. CSV row parity alone
does not resolve these conflicts.

Recommended repair: preserve both representations, warehouse the existing
reconciliation evidence, and gate analytical uses requiring a complete roll
call. Do not manufacture missing votes or silently substitute recounts for
reported totals.

### WQA-07 — Medium: SQL finance inputs do not fully honor masking contract

There are **3,020** incomplete rows in `mart_southern_race_finance` with at
least one numeric candidate amount. More importantly, **110** rows in the
model-facing `mart_southern_war_training_with_finance` have
`finance_complete=0` but retain numeric fundraising amounts, contrary to the
documented rule that incomplete model inputs have null amounts and ratio.

No incomplete race has a numeric log ratio, and no unknown source-finance
observation was found with a numeric total. The observed one-sided amounts
are not fabricated. The standalone CSV exporter correctly masks all three
numeric features, so SQL and CSV consumers currently receive different
missingness behavior.

Recommended repair: retain observed source amounts, but enforce the stated
mask at the model-facing SQL interface or explicitly revise the contract and
every consumer. Do not erase legitimate source observations.

### WQA-08 — Medium: incomplete provenance and misleading metadata

- All 26,692 registered file paths exist. However, 36 registrations have no URL,
  2,154 no terms/license value, and 1,351 no authoritative scope. Some URL-less
  entries are legitimate local derived inputs; these counts are completeness
  indicators, not 36 failed downloads.
- All 1,564 Alabama records in the regional canonical candidate table use
  `build_run_id='legacy-alabama-canonical'`, which does not exist in the run
  registry, and have null direct source IDs. This is an explicit legacy bridge,
  but it prevents a normal row-to-registered-build provenance join. In contrast,
  null direct source IDs on the 13,729 official-state records have a documented
  many-to-many source bridge and should not automatically be treated as lost
  provenance.
- DIME's registration claims retrieval at `2026-09-04T22:08:47.061483+00:00`,
  while its build manifest explicitly says original retrieval is unknown.
  `warehouse.register_source_file` fills retrieval with registration time.
  Retrieval and registration are different events and should not be conflated.
- Thirteen older build records remain marked `running`. No process-liveness
  conclusion was drawn from this status, and none was relabeled by this audit.
- Historical registry grains are wrong: the office baseline omits `office`,
  precinct weights omit county/precinct, and the historical presidential
  precinct source is described as `cycle/chamber/district` despite having no
  chamber or district columns. Two historical tables each show 139 collisions
  if consumers use those advertised keys; their actual richer grains are not
  thereby duplicates.

## Checks that passed and intentional limitations

- SQLite `quick_check`: `ok`; `foreign_key_check`: zero violations. A full
  `integrity_check` was not run in this audit. All 22 views compile.
- Declared primary-key null scan found only the two intentional AL/TX
  state-level coverage placeholders with null cycle; these are not candidate
  data errors. All registered table names exist.
- No duplicate Alabama canonical candidate IDs, duplicate regional canonical
  candidate natural keys, mixed-provider contest sets in regional canonical
  selection, or duplicate regional finance source natural keys were found.
- No negative Alabama source votes; the fractional exception is WQA-04.
  Regional canonical results have no negative votes, out-of-range shares,
  observed-null votes, unknown-numeric votes, or date/cycle-year disagreement.
- All 3,270,010 presidential geography rows and 13,800 district allocations
  passed the checked nonnegative/component-total arithmetic. Tested geometry
  joins agree on state, cycle/plan, chamber, and district where applicable.
  All four checked precinct/allocation-weight tables and the source-geometry
  bridge have unit-sum weights at their declared allocation grain.
- All 26,692 registered paths were checked for existence. A bounded,
  path-ordered hash pass verified 3,444 files at most 10 MB each with zero
  mismatches; 275 larger files and 22,973 files beyond the time budget were not
  hashed in that pass. Five non-raw registered inputs and the 1994/2002 Alabama
  source artifacts were checked separately and matched. This is not a complete
  content-integrity certification of the source collection.
- The 26,692 registrations represent 24,878 distinct hashes. Repeated empty
  finance responses, preserved error responses, and repeated acquisition paths
  explain prominent duplicate-content groups. Their existence does not prove
  duplicate canonical transactions or authorize deletion of raw evidence.
- The five Alabama OpenElections CSVs contain no nonnumeric vote cells. Their
  loader's generic `fillna(0)` is a latent contract risk, but this audit found
  no affected current rows and does not count it as a confirmed data defect.
- Virginia's 2,723 reviewed 2012 presidential rows and Mississippi's 106
  reviewed 2012-on-2019-plan district rows remain explicit review data, not
  fabrication. Unverified legislative-plan vintages, inferred election dates,
  missing finance, and empty chronology/adjudication tables are readiness
  limitations, not automatic cleanup targets.

This was an internal consistency and selected raw-source audit, not an
independent recertification of every election total, every spatial allocation,
source reuse terms, or every downstream temporal-leakage path. No claim is made
that all tables or all model outputs are now validated.

## Reproduction queries

Open SQLite with `mode=ro` and `PRAGMA query_only=ON`. The following SQL is
read-only. Source inspections above name exact archive members/sheets.

```sql
-- WQA-01: each summary must be compared with the remaining precincts.
SELECT office, district, candidate,
  SUM(CASE WHEN precinct_key='TOTAL OF REGISTERED VOTERS'
           THEN votes ELSE 0 END) AS summary_votes,
  SUM(CASE WHEN precinct_key<>'TOTAL OF REGISTERED VOTERS'
           THEN votes ELSE 0 END) AS precinct_votes
FROM vote_observations
WHERE source='alabama_sos' AND year=2014 AND county_key='JEFFERSON'
GROUP BY office, district, candidate;

-- WQA-02: wrong column mappings are visible without interpreting results.
SELECT office, candidate, party, COUNT(*) AS rows, SUM(votes) AS votes
FROM vote_observations
WHERE year=2002 AND county_key='MARSHALL'
GROUP BY office, candidate, party;

-- WQA-03: collisions, not an instruction to delete observations.
SELECT COUNT(*) AS collision_groups, SUM(n-1) AS excess_rows
FROM (
  SELECT source, year, county_key, precinct_key, office, district,
         candidate_key, COUNT(*) AS n
  FROM vote_observations
  GROUP BY source, year, county_key, precinct_key, office, district, candidate_key
  HAVING COUNT(*)>1
);

-- WQA-04: party inconsistency and source fractional count.
SELECT candidate_key, party_norm, COUNT(*) AS rows
FROM vote_observations
WHERE year=1994 AND office='Attorney General'
GROUP BY candidate_key, party_norm;
SELECT * FROM vote_observations WHERE votes<>CAST(votes AS INTEGER);

-- WQA-06: provider/member reconciliation failures.
SELECT r.roll_call_id, r.total, COUNT(v.people_id) AS actual_members
FROM source_legiscan_roll_call r
LEFT JOIN source_legiscan_member_vote v USING (roll_call_id)
GROUP BY r.roll_call_id HAVING r.total<>COUNT(v.people_id);

-- WQA-07: SQL model inputs retain amounts despite incompleteness.
SELECT state_code, cycle, chamber, district,
       democratic_fundraising, republican_fundraising, finance_complete
FROM mart_southern_war_training_with_finance
WHERE finance_complete=0
  AND (democratic_fundraising IS NOT NULL OR republican_fundraising IS NOT NULL);

-- WQA-08: missing registered run lineage, including explicit legacy tokens.
SELECT d.build_run_id, COUNT(*) AS rows
FROM canonical_southern_legislative_candidate_election d
LEFT JOIN warehouse_build_run r USING (build_run_id)
WHERE r.build_run_id IS NULL GROUP BY d.build_run_id;
```

Geometry reproduction, using the already-installed Shapely library:

```python
import sqlite3
from pathlib import Path
from shapely import from_wkb, is_valid_reason

db = Path('data/processed/elections/alabama_elections.sqlite').resolve()
connection = sqlite3.connect(db.as_uri() + '?mode=ro', uri=True)
try:
    for identifier, wkb in connection.execute(
        'SELECT geography_unit_id, geometry_wkb FROM dim_southern_geography_unit'
    ):
        shape = from_wkb(wkb)
        if not shape.is_valid:
            print(identifier, is_valid_reason(shape))
finally:
    connection.close()
```

## Inspected working-code hashes

```text
scripts/sos_precinct.py
  fb8590158e79e95e536a651fd82fd4bd1ba7b0724f2525317ef329f64b2aed07
scripts/build_election_database.py
  355e2f7cff24571103f7f9f8dfd8c6f1fd912bd61d038dde357e50e1668cacc1
scripts/load_southern_2016_vest_warehouse.py
  4a144fad63dfcac59e853a692ffbcbf804bf97d58e28b28f1e824f32f72dacf9
scripts/warehouse_southern_war_preparation_schema.sql
  63c03a52f6d5d8cd14e685dee2efd7b1a9f6f604d1aeb320b09fa2da09e5e404
```

Repair order: fix the two demonstrated county parsing/double-counting defects;
restore precinct identity and shared correction evidence; then close geometry,
roll-call, model-interface, and provenance validation gaps. Each repair needs
source fixtures and affected-consumer reconciliation before publication.
