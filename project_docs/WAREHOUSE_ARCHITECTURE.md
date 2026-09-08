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
- Base election database builds are bootstrap-only and occur in a unique
  temporary SQLite file. After SQLite integrity checks and build validation,
  publication atomically creates a new output path; it never replaces an
  existing warehouse. Use `--output` with a new path for a separate build.
  Refreshing one domain does not authorize discarding other domains or history.

## First canonical domain: candidate/person identity

> **Migration history, not a live coverage dashboard.** The domain and
> schema-version sections below record successive implementation snapshots.
> Their “current” counts, gaps and next steps belong to that migration, not
> necessarily the present warehouse or published products. Use the registered
> build runs and current product manifests for live state, the source-repair
> audit for invalidated dependencies, and `PROJECT_COMPLETION_CHECKLIST.html`
> for remaining work. Do not infer present coverage from an earlier table.

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

## Official Southern election results

Schema version 10 adds the acquired official Southern result collection without
changing Alabama's authority policy. `source_southern_election_file` extends
the general file registry with state, cycle, stage, geographic-vintage,
licensing, scope, ingest-status, and parser fields.
`source_southern_candidate_election` stores normalized candidate-party-contest
totals, while `bridge_southern_candidate_result_source` preserves the explicit
many-to-many source lineage needed when county files compose a statewide or
district result. `fact_southern_candidate_election` exposes only validated
rows. Reconciliation and 14-state coverage remain first-class QA tables.

The load currently parses machine-readable official formats for Arkansas,
Florida, Kentucky, Louisiana, North Carolina, Oklahoma, South Carolina,
Tennessee, and Virginia. Alabama remains in its existing canonical tables;
Texas remains in its companion repository. Georgia and Missouri acquisition
gaps and Mississippi's PDF-only corpus are recorded as gaps, not silently
filled from lower-authority sources.

## Comprehensive Southern legislative history

Schema version 11 integrates the separate historical/recent outcome layer.
Klarner supplies locally available candidate-contest history from 1968 through
2022; national MEDSL archives supply 2018, 2020, and 2024 precinct returns;
the acquired MEDSL individual-state bundles add four 2022 and five 2024 source
observations; and validated Mississippi and Virginia files close their 2023
scheduled elections. These are provider observations rather than silent
replacements for the schema-version-10 official tables.

The schema-version-12 canonical materialization ranks one whole source
observation set per contest and is exposed through the stable
`fact_southern_legislative_candidate_election` view. The all-observations view
remains the reconciliation interface. Geography stays
`reported-unknown-vintage`, and MEDSL 2024 coverage is explicitly allowed to be
contested-only.

Schema version 13 adds a model-safe final-stage interface. Louisiana selects a
November runoff only for districts that reached it and otherwise retains the
October first-round result. Other states select the regular general stage.
This prevents stage addition or double counting while preserving every source
stage in the canonical history. A separate QA view counts final contests,
observed competitions, and exactly-one-Democrat/one-Republican WAR-eligible
contests.

## Southern finance warehouse

Schema version 14 loads the versioned Southern candidate-cycle finance panel
without replacing explicit unknown and review states. The source layer
registers both acquisition manifests, the canonical input panel, the supplied
incumbency workbook, and the Alabama/Texas upstreams not represented in those
two manifests. `bridge_southern_finance_record_source` retains record-level
lineage.

Finance identities are constrained to the exact state, cycle, chamber, and
district of `fact_southern_legislative_final_candidate_election`. Party also
agrees unless the warehouse source explicitly reports it as unknown;
conservative name evidence then determines accepted versus review status. The
supplied incumbency workbook is positive evidence only and currently contains
Alabama 2026. Historical positive incumbent flags already preserved on source
candidate observations separately support 2016-2024 matching; absence is not
negative evidence.

`fact_southern_candidate_cycle_finance` exposes accepted candidate links while
preserving missing totals. `fact_southern_race_finance` exposes a fundraising
ratio only when both major-party observations and identities are complete.
`qa_southern_finance_coverage` separately reports source data, identity,
linked-observation, and D/R race completeness.

`scripts/validate_southern_finance_release.py` enforces integrity, foreign-key,
cardinality, missing-not-zero, identity-retention, and complete-race gates.
`scripts/export_southern_finance_model_features.py` then publishes a
missingness-aware CSV interface without changing the outcome-only WAR mart.

## Southern WAR preparation and finance overlay

Schema version 15 prepares the non-financial model inputs without implying
that campaign-finance data are complete. `mart_southern_war_outcome` selects
one whole provider observation for each model-valid final-stage contest: one
positive-vote Democrat, one positive-vote Republican, all votes observed, and
no provider exclusion flag. The canonical source remains preferred, but an
otherwise lower-ranked model-valid observation may be used and is labeled as
a fallback. Louisiana uses its final-stage rule: November runoff when present,
otherwise the October first round. The only external fallback is a validated
Texas official companion-panel contest absent from the central regular-stage
key.

`mart_southern_war_context_feature` preserves the versioned baseline and
incumbency fields from Southern WAR panel v1. The 1:0..1 join to outcomes is
exposed as `mart_southern_war_training_no_finance`, where strict, research,
missing-context, and missing-baseline states remain explicit. Its
`finance_status` is always `excluded_not_ready`; the mart contains no finance
amount or ratio columns.

Schema version 16 adds `mart_southern_war_training_with_finance` and its QA
coverage view. The join is exact state/cycle/chamber/district and retains all
outcomes; incomplete finance stays null and is labeled separately from WAR
context readiness. Virginia cycles without a same-year ticket use the
election-day national generic-ballot polling average instead of a prior-cycle
ticket result.

`mart_alabama_2026_incumbency_roster` materializes the 140 populated Alabama
rows in the supplied workbook. Workbook entries mapped only in its source tabs
are not treated as incumbency evidence. Disagreements with the earlier 2026
roster enter a review queue rather than being silently approved.

## Central Southern presidential context and geography

Schema version 17 moves the shared presidential-result and legislative-
boundary inputs out of model-specific side paths. The central warehouse now
contains provider-grain presidential totals in
`source_southern_presidential_geography_result`, validated rows in
`fact_southern_presidential_geography_result`, boundary-layer metadata in
`dim_southern_geography_layer`, and normalized WGS84 features in
`dim_southern_geography_unit`.

The loader deliberately distinguishes raw registration, normalization, and a
model-ready geographic join. `bridge_southern_result_geography` remains empty
until precinct/block membership or spatial allocation is built and validated.
This prevents an available 2012 precinct file plus an available legislative
district outline from being misrepresented as an exact 2012-on-plan baseline.
The 2024 New York Times result CSV is normalized separately from its registered
national TopoJSON geometry, and the latter remains an explicit unparsed asset
until the resource-heavy precinct geometry stage is implemented.

## Central block assignment and district-result allocation

Schema version 18 registers the Redistricting Data Hub national 2022 and 2024
state-legislative block-assignment archives and stores their Southern subset in
`bridge_southern_block_district_assignment`. This is an explicit membership
bridge, not a spatial guess: each 2020 Census block is assigned to its reported
lower- and upper-chamber district on the named election-year plan.

`mart_southern_presidential_district_result` aggregates the validated national
2020 block result through each assignment source. The corresponding fact view
exposes only state/chamber allocations that pass vote conservation. Geometry is
optional at this stage and may link only to the exact state, plan cycle,
chamber, and district feature. The current validated run contains 6,324,382
Southern assignment rows and 4,532 district aggregates across the two plans;
all 56 state-plan-chamber audits pass.

This schema-version-18 stage supplies 2020 margins on the 2022 plan for the V4
WAR research pipeline. It does not manufacture other presidential years;
schema version 20 separately supplies validated VEST 2016-on-2022-plan margins.

## VEST 2016 precinct context

Schema version 19 adds one CC BY 4.0 Harvard Dataverse/VEST archive for every
Southern model state. The loader normalizes both the 2016 presidential result
and its matching precinct polygon, then records an explicit one-to-one source-
precinct link. The validated run contains 45,990 precincts from 46,065 source
features; 75 repeated zero-vote geometry fragments are dissolved after their
vote fields agree, and 15 invalid source polygons are repaired in canonical
storage without modifying the raw archives.

These precinct links establish which polygon owns each VEST result. They do not
claim that a precinct lies wholly within one 2022 legislative district.

## VEST 2016 allocation to the 2022 plan

Schema version 20 registers official TIGER2020 Census block polygons in
`source_southern_census_block_file` and creates population-weighted
precinct/district rows in `bridge_southern_vest_precinct_district_weight`.
Blocks join to the validated 2022 BAF by exact GEOID and to VEST precincts by a
representative point, with greatest intersection area resolving boundary
ambiguities. Split precinct weights use RDH modified VAP. A separately labeled
geometry-area fallback is permitted only where a vote-bearing precinct has no
positive-VAP block match.

The validated run contains 96,114 weight rows and 2,266 2016 district results.
All 28 state/chamber audits in
`qa_southern_vest_precinct_plan_allocation` pass, as do the separate vote-
conservation audits. These results share the existing presidential district
mart and fact view with the 2020 allocations while retaining election year,
plan year, source IDs, method, and build run.

## Historical presidential allocation and district readiness

Schemas 21--23 extend the shared mart to election-vintage presidential
context on the exact intradecade legislative plans. The validated historical
run loads exact 2012/2016/2020 contexts already available at a compatible
geography. A separate 2012 precinct allocator covers Florida, Georgia, North
Carolina, and Virginia across 14 plan/chamber cells and 1,272 district rows;
all cells pass source-vote, weight-sum, unmatched-VAP, and fallback-vote gates.
Alabama 2012 uses the official Secretary of State archive as county and
statewide authority, retaining four explicitly county-only rows where the
source says precinct results are unavailable.

Schema 24 preserves the immutable Mississippi 2012 conversion while recording
the Harrison County Democratic/Republican column correction against an
independently registered county-level result source. Schema 25 then adds
`qa_southern_presidential_precinct_match` and
`qa_southern_presidential_district_readiness`. Mississippi's statewide 2012
allocation remains review because 134 result names are unresolved. District
rows pass only when every unresolved result that could touch the district
either has all plausible donor geometry in that one district or has no
plausible exposure to it. This produces 68 passed and 106 review districts on
the exact 2019 plan; the fact view exposes only the 68 passed rows.

The Mississippi matcher uses the 2012 MARIS precinct geometry as the donor
universe. Its later-name alias inputs are separately hash-registered and
warehouse-registered. In particular, the RDH/VEST 2019 archive is evidence for
precinct names and VTD codes only, never a replacement result source. This
district-level gate is deliberately more conservative than imputing the
unresolved precincts or declaring the whole state complete.

## Source-quality repairs (schema 26)

The source-backed 2026-09-05 repair retains the populated warehouse and a
verified pre-repair backup. Reparsed SOS rows preserve source-cell lineage;
`qa_vote_observation_quality` exposes remaining collisions and fractional
source values. `qa_warehouse_source_repair` records correction evidence,
registered runs, and unresolved/stale dependency scopes. LegiScan gains
category/total reconciliation and complete-roll-call interfaces without
overwriting contradictory provider observations. Existing legacy source
consumers are not automatically migrated or certified.

See `audits/WAREHOUSE_SOURCE_REPAIRS_2026_09_05.md` for scope, source hashes,
recovery path, fresh verification, and unreconstructed dependencies. The
repair command never rebuilds models or published scores.

## Alabama certified canvass bridge (schema 27)

Schema version 27 adds `bridge_alabama_canonical_candidate_certified_result`,
one approved row per Alabama 2018/2022 legislative canonical candidate bridged to
exactly one certified canvass cell in `source_southern_legislative_candidate_result`.
`scripts/repair_alabama_canonical_certified_totals.py` stages the bridge read-only,
then under a verified separate backup corrects only `canonical_candidates.canonical_votes`
and the materialized `canonical_southern_legislative_candidate_election` votes/shares
for contests whose canonical total disagreed with the certified canvass, recording
before-images and stale dependencies in `qa_warehouse_source_repair`. The bridge
table is append-only evidence; `load_southern_war_preparation_warehouse.py` reads it
to supply the scalar source file and certified third-party totals for Alabama
outcomes and refuses to build on disagreement. See the data contract section
"Alabama certified canvass authority and canonical bridge".

## Domain command reference — not a rebuild recipe

The following is a catalog of separate writers and research stages, not a
sequence to run wholesale. Inspect the selected command's scope and prerequisites
and consult `CANONICAL_PIPELINES.md` before execution. Research retraining is not
authorized by a source refresh, and successful domain loading does not validate
dependent products. Do not run the bootstrap against an existing warehouse.

```powershell
python scripts/build_election_database.py
python scripts/build_precinct_identity.py
python scripts/build_candidate_identity.py
python scripts/build_data_catalog.py
python scripts/sync_warehouse_source_registry.py
python scripts/load_legislative_warehouse.py
python scripts/build_dime_finance_features.py
python scripts/load_historical_cmo_warehouse.py
python scripts/load_southern_election_warehouse.py
python scripts/load_southern_legislative_history_warehouse.py
python scripts/load_southern_finance_warehouse.py
python scripts/load_southern_war_preparation_warehouse.py
python scripts/load_southern_context_warehouse.py
python scripts/acquire_southern_context_assignments.py
python scripts/build_southern_context_allocations.py
python scripts/acquire_southern_2016_precinct_geography.py --offline
python scripts/load_southern_2016_vest_warehouse.py
python scripts/acquire_southern_2020_census_blocks.py --offline
python scripts/build_southern_2016_vest_plan_allocation.py
python scripts/build_southern_historical_plan_allocations.py
python scripts/build_southern_2012_plan_allocations.py
python scripts/register_mississippi_2019_precinct_alias_source.py
python scripts/audit_mississippi_2012_precinct_plan_readiness.py
python scripts/build_mississippi_2012_partial_plan_allocations.py
python scripts/retrain_post2016_southern_war_v4.py
```

The first command bootstraps an absent database. If the warehouse already
exists, use `python scripts/build_election_database.py --output <new-path>`;
the resulting election-only database is not a replacement for the populated
central warehouse. Publication uses a same-directory hard link after closing
and validating the temporary database, so a target created during the build
also causes failure without overwrite. Filesystems without hard-link support
fail safely; there is no destructive fallback.

Lifecycle fixtures in `scripts/tests/test_warehouse.py` cover new-file
publication, rejection of an existing warehouse before source loading,
publication-time target collisions, failed-build preservation, and source-hash
parity. `scripts/tests/test_data_catalog.py` checks unique lineage declarations
and repeatable CSV/database catalog contents. These are infrastructure checks,
not validation of every source or downstream model.

The later identity/geography stages are still
separate writers and are the next lifecycle migration target before a single
top-level warehouse build command can safely publish the full database.
