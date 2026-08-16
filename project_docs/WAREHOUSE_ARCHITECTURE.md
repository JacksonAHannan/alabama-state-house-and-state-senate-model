# Canonical research warehouse

## Decision

The existing `data/processed/elections/alabama_elections.sqlite` database is
the nucleus of the project-wide warehouse. SQLite remains the storage engine.
Raw PDFs, ZIP files, spreadsheets, saved pages, and shapefiles remain immutable
files under `data/raw`; the warehouse stores their provenance and normalized
records, not their binary contents.

The migration is incremental. Existing CSV consumers remain supported until a
database table or view is validated and every upstream consumer is migrated.
Files under `docs/data` are publication outputs and must never be upstream
inputs.

## Layers

1. **Raw files** — immutable provider artifacts plus hashes and licensing.
2. **Source tables** — normalized observations that preserve provider meaning.
3. **Canonical tables/views** — authority-ranked facts, identities, and all
   retained reconciliation evidence.
4. **Marts** — model-specific features and versioned model runs.
5. **Publication exports** — CSV/JSON/HTML generated from canonical views or a
   validated model run.

SQLite lacks named schemas, so layer membership is declared in
`warehouse_table_registry` and `warehouse_asset`, not encoded with opaque table
name prefixes.

## Lifecycle controls implemented

- `warehouse_schema_version` records controlled schema changes.
- `warehouse_build_run` records target, configuration, code commit, timestamps,
  validation status, and validation results.
- `warehouse_source_file` records provider, path, URL, hash, media type,
  licensing, extraction status, and authoritative scope.
- `warehouse_table_registry` declares ownership, keys, authority policy, layer,
  and replacement/append/view lifecycle.
- `warehouse_asset` and `warehouse_asset_lineage` form the machine-readable
  dependency catalog.
- `warehouse_manual_adjudication` provides a stable destination for approved,
  reviewable human decisions; existing decision CSVs remain authoritative until
  their domain migration is implemented.
- Base election database builds occur in a unique temporary SQLite file. The
  working database is replaced atomically only after SQLite integrity checks and
  build validation succeed.

## First canonical domain: candidate/person identity

The candidate identity pipeline owns the underlying evidence tables and now
publishes stable interfaces:

| Interface | Key | Meaning |
|---|---|---|
| `dim_person` | `person_id` | One canonical person with observed election span |
| `fact_candidate_election` | `canonical_candidate_id` | One candidate-party-district-election record |
| `bridge_person_alias` | person/source/year/candidate key | Accepted source aliases and match evidence |

Unique indexes enforce one canonical candidate ID and one major-party candidate
per year/chamber/district/party. Conflicting and proposed matches remain in
their evidence/review tables rather than being overwritten.

## Missing-value and authority policies

- Missing is distinct from zero unless a source contract explicitly defines an
  absent record as zero.
- Source observations coexist. Canonical selection is performed by declared
  authority or approved adjudication.
- Optional analytical inputs must become explicit configuration fields. File
  existence is not an authority policy.
- Every reusable join must state and validate its expected cardinality.
- Human decisions must retain rationale, evidence, status, and supersession.

## Current compatibility boundary

`project_docs/data_catalog.csv` lists initial assets, owners, keys, status, and
planned replacements. Entries marked `compatibility` are still legitimate
outputs, but they are migration targets rather than permanent internal APIs.

## Legislative domain

LegiScan bills, legislators, sponsorships, histories, subjects, amendments,
documents, roll calls, and individual recorded votes are now constrained source
tables. The migration preserves exact row parity with the compatibility CSVs.

| Table/view | Key | Current rows |
|---|---|---:|
| `source_legiscan_bill` | `bill_id` | 28,833 |
| `source_legiscan_roll_call` | `roll_call_id` | 31,257 |
| `source_legiscan_member_vote` | roll call/person | 2,225,079 |
| `source_legiscan_bill_sponsor` | bill/person/order | 102,291 |
| `source_legiscan_bill_history` | bill/history order | 205,574 |
| `source_legiscan_bill_subject` | bill/subject | 28,265 |
| `source_legiscan_amendment` | `amendment_id` | 5,912 |
| `source_legiscan_bill_document` | `doc_id` | 39,853 |
| `canonical_legislator_identity` | LegiScan person/project person | 20 approved links |

All 31 LegiScan archives are registered by hash and linked from their source
rows. General exact-name candidate links are stored as `proposed`; only the
reviewed focal crosswalk is exposed through `canonical_legislator_identity`.
Bill text, journals, and Alabama Acts scans remain external files registered by
hash.

`build_alabama_legislative_ideology.py` is the first downstream consumer moved
from the large source CSVs to warehouse queries. Its CSV results remain model
and compatibility exports.

## Finance domain

DIME recipient-cycle records are normalized into `source_dime_recipient` and
linked to canonical election candidates with district-, party-, and
name-constrained evidence. The authority-selected `mart_candidate_resources`
uses DIME total receipts through 2010, FollowTheMoney fundraising summaries for
2014â€“2022, and Alabama FCPA monetary contributions for 2026. Missing source
records remain unknown rather than becoming zero. `mart_race_resource_features`
only publishes a D/R log resource ratio when both candidates are observed.

The DIME import closes most of the pre-electronic reporting gap but does not
provide useful Alabama state-candidate expenditure totals. Candidate resources
are therefore defined as fundraising receipts, not spending, across sources.

## Historical CMO extension

Official Alabama SOS legislative county totals for 1986 and 1990 and the 1990
governor county returns are normalized in dedicated historical source tables.
The 1990 workbook covers all 105 House and 35 Senate districts. The 1986 file
supports positive incumbency identification but omits many uncontested seats,
so a missing prior result is retained as unknown.

`mart_cmo_cycle_input_coverage` defines 1994 as the first eligible CMO cycle.
Official 1986 and 1990 results remain warehoused as archival and incumbency
evidence, but 1990 is excluded from model construction because an authoritative
1983 Alabama House plan geometry could not be recovered. The available Senate
election SVG is a 2025 self-published reconstruction and is not a substitute for
official geometry. The model must never substitute the 1992â€“2000 district plan
for the map used in 1990 or treat absent finance as zero.

The 1994 baseline has a separate auditable build. The warehouse stores ballot-
derived precinct/district weights in
`mart_historical_precinct_district_weight`, office results in
`mart_historical_district_office_baseline`, raw race features in
`mart_historical_cmo_race_feature`, and source-to-allocation reconciliation in
`qa_historical_baseline_allocation`. Single-district precinct assignments and
provisional split-precinct activity weights are distinct methods; neither is
misrepresented as a Census geographic crosswalk.

Warehouse schema version 6 adds the remaining 1994 context as separately
auditable objects: `mart_historical_district_demographic_feature`,
`source_historical_presidential_precinct`,
`mart_historical_district_presidential_feature`,
`mart_historical_candidate_incumbency`,
`mart_historical_candidate_finance_coverage`, and
`mart_historical_cmo_context_feature`. The combined mart preserves Census
tract-interpolation methodology, presidential fallback share and source
completeness, positive-only incumbency evidence, and unknown-not-zero finance
semantics.

Schema version 7 adds `mart_historical_cmo_context_feature_v2` for the 1998,
2002, and 2006 experimental extensions. It uses generic prior-presidential
columns rather than year-specific names, joins Shor-McCarty pre-election
rosters as positive incumbency evidence, and retains DIME missingness as
unknown rather than zero. The 1998 demographics use 1990 SF3 tract-area
interpolation; 2002 and 2006 use official Census 2000 SF3 sequences 1, 3,
and 13 joined to the geographic header and allocated from tract geometry.
These cycles remain experimental pending historical-baseline validation.

The 2010 canonical CMO feature mart now uses direct 2006-2010 ACS five-year
state-legislative-district estimates parsed from the official Alabama summary
file. The source sequence files remain immutable under `data/raw/census/`; the
compact district export records the ACS vintage and direct-SLD method.

Schema version 8 adds `mart_historical_federal_district_baseline`. It preserves
the separately allocated U.S. House and Senate components, excludes uncontested
contests from calculated margins, and records contested-vote coverage rather
than silently interpreting missing opposition as a 100-point margin.

The next finance work is full Alabama FCPA committee discovery and
transaction-level election-window reconciliation, followed by moving the
remaining legislative consumers off compatibility CSVs.

## Commands

```powershell
python scripts/build_election_database.py
python scripts/build_precinct_identity.py
python scripts/build_candidate_identity.py
python scripts/build_data_catalog.py
python scripts/sync_warehouse_source_registry.py
python scripts/load_legislative_warehouse.py
python scripts/build_dime_finance_features.py
python scripts/load_historical_cmo_warehouse.py
```

The first command is atomic. The later identity/geography stages are still
separate writers and are the next lifecycle migration target before a single
top-level warehouse build command can safely publish the full database.
