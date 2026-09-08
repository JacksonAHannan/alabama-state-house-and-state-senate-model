# Southern release readiness — September 7 local-date continuation

> Superseded on 2026-09-08 by `SOUTHERN_RELEASE_READINESS_2026_09_08.md` after the
> Alabama certified-canvass integration resolved the 97 missing source-file IDs.
> This record is retained as history of the pre-repair inventory.

Status: incomplete; no release approval or model execution. Current warehouse
checkpoint: `RUN-3723F54646824B1682D8543BE39C7EC5`.

## Existing scope

Retain the current Southern v3 source plus labeled 2016 backcasts. Research-v4
promotion and optional finance expansion remain deferred. The independent
documentation review accepts southern-09 as documented deferral, not resolution:
retain the documented 134 unresolved Mississippi source rows and 31 null/review
v4 records and all current v3 source/plan requirements. No source substitutions,
filled values or artifact recertification follow from this disposition.

## Blocking approval contradiction

Historical run `WAR-SOUTH-HIST-V1-D3EC2AC2CC508300EA1C` declares
`validated_descriptive_historical_release`. Its exact upstream v3 manifest and
`POST2016_SOUTHERN_WAR_V3_VALIDATION.md` instead describe
`WAR-POST2016-V3-8BB52074EC806C5BF6BF` as
`research_candidate_pending_independent_validation`.

The earlier task handoff `CMO-SOUTHERN-WAR-RESIDUAL-042.md` requests review for a
different older run; it does not supply approval for this one. The incumbency
repair report records regression checks but does not supersede the current
validation report's pending decision. Approval evidence has been requested.
Do not rewrite statuses or hashes to manufacture agreement.

## Narrow context-file drift reconciliation

All ten non-database direct inputs of the historical manifest match their
registered hashes. This does not establish transitive freshness.

The v3 input `data/processed/presidential/2018_district_presidential_features.csv`
has recorded SHA256
`53ac22998689c1a1a69d93cb9e6388ab4d4b1bb01895c70859cff6a6c43b2694`;
current bytes hash to
`064c89b51842a26fa108da0b1ad7278f464b9a1c5faaa01aa44e8fffb5dc2d90`.
Independent read-only tracing recovered the exact recorded bytes from the Git
snapshot at `4d90a5d1bb1b405dc67e1e7eda1b009c811dd969`, using its recorded
CRLF serialization. All 140 keys and all five fields consumed by
`v2.load_alabama_context` match exactly: cycle, chamber, district,
pres_2016_dem_margin, pres_2016_source_complete.

Their sorted consumed-column LF CSV SHA256 is identically
`22aa76d9be642f94312edd56b94c14985b564e200c4df620403f0bc98cc04e18`.
Differences are confined to seven unconsumed 2012/swing fields. This resolves
this particular consumed-field drift; it does not approve those changed fields,
reconcile the entire warehouse, or validate the analytical run. No manifest was
modified and no old source file was restored over user work.

## Eligibility accounting

`scripts/audit_southern_release_readiness.py` reads a consistent query-only
warehouse snapshot. It inventories existing outcome rows, not every election
contest. It selects no scores, margins or vote totals and never changes the
recorded eligibility decisions. Exact IDs and keys reconcile from the base
outcome table to its eligibility view. All 116 declared slices remain visible.

Initial inventory: 4,582 rows = 4,280 recorded-strict + 302 excluded; 97 source-file
IDs are missing. VA 2017 lower has 60 existing outcomes and VA 2021 lower has 91;
both have zero recorded-strict rows. The JSON companion contains stable IDs,
source metadata and overlapping reason flags for excluded rows, plus per-slice
accounting. These are recorded flags, not independently adjudicated exclusions.

All 302 excluded rows retain recorded research status. Of these, 151 have
`experimental_exact_prior_winner` incumbency quality; the other 151 have
`research_only_cross_election_precinct_membership` baseline quality and are the
two Virginia slices above. This explains the current software eligibility
decision without declaring those underlying sources defective or approving a
replacement baseline. In particular, availability of a later precinct plan does
not certify contemporaneous district membership. The audit does not promote
experimental identity evidence or substitute a different comparator to fill a map.

An exact-key follow-up accounts for the two exclusion classes without overlap.
The 151 Virginia lower-chamber rows are 60 records in 2017 and 91 in 2021. They
use same-year governor returns with 2019-plan cross-election precinct membership
and locality fallback; strict recovery therefore needs contemporaneous plan and
allocation evidence, not a relabeling of the recorded baseline. The other 151
rows span ten states and all use `experimental_exact_prior_winner`. Every one
matches the newer roster as `review` with missing incumbency evidence, and none
has a same-key row in `source_southern_incumbency_evidence`. A prior-winner
non-match cannot establish that a seat was open. These reason-coded records are
complete accounting, but remain review dispositions rather than accepted inputs.

## Alabama source-lineage follow-up

All 97 missing scalar source-file IDs are Alabama canonical outcomes: 49 lower
and 15 upper in 2018, then 25 lower and 8 upper in 2022. Their 194 contributing
canonical candidate rows expose no candidate-to-source-file bridge. The existing
repair staging function consequently recovers 0 of 97 through its required
complete registered-source consensus. Assigning a nearby SOS or OpenElections
file would invent lineage.

The official Alabama 2018 certified canvass was acquired from the Secretary of
State election page at the previously absent local path
`data/raw/alabama_elections_and_geography/2018_general_certified_canvass.pdf`.
Its SHA256 is
`a83be9be26ac195989bf94ad5097e4269f516674f645373526a9d6621f310044`;
the 192-page PDF opened successfully, with Senate tables beginning on PDF page
23 and House tables on PDF page 43. Full provenance and the redistribution-
license review state are recorded in
`ALABAMA_2018_CERTIFIED_CANVASS_ACQUISITION.json`. This closes acquisition only.
The missingness-preserving source adapter now parses all 105 House and 35 Senate
districts and compares 352 certified candidate/write-in totals with 38,699
physical precinct cells. It finds 322 exact totals and retains 30 review rows;
24,912 blank precinct cells remain unknown. Four current strict Southern races
intersect six major-party subtotal discrepancies with 12 votes of aggregate
absolute difference. `ALABAMA_2018_CERTIFIED_SOURCE_RECONCILIATION.json` records
the exact hashes and counts. Warehouse registration, source-set staging,
canonical authority adjudication and exact candidate bridges remain separate.

For 2022, the staged certified cohort is complete and internally reconciled,
but the current Alabama canonical route differs in ten candidate totals across
seven House contests, totaling 185 votes across the signed candidate deltas.
That conflict prevents both numerical certification and scalar attribution until
the canonical authority decision and downstream dependency trace are reviewed.

## Enforced downstream gate

`SOUTHERN_V3_RELEASE_DECISION.json` now binds the exact v3 manifest and review
record and records `blocked_insufficient_evidence`. Both the historical builder
and map builder verify that decision before reading model rows. This prevents a
new downstream build from treating the historical manifest's stale validated
label as approval. The guard changes no existing model value or public artifact.

## Remaining acceptance

- Obtain or complete independent approval for the exact consumed v3 run.
- Resolve the 97 missing source links and inherited source/plan dependencies;
  registered certified source records do not automatically change canonical use.
- Review the exclusion evidence before treating it as final public disposition.
- Only after reconciliation, run final regional and browser/download checks and
  prepare the accepted state-level release limitations. Publication remains a
  separate authorized action.

The inventory's fixture checks do not constitute regional/model validation.
No whole Southern phase or source-parity gate is accepted by this report.

Verification: 11 isolated testmon fixtures passed; independent software review
passed after adding context-run provenance and deployed SQL definition hashes.
The regenerated JSON records both consumed run families and exact snapshot.
Checklist IDs/history and JSON accounting checks passed. Fifteen focused release-
gate/historical/map tests passed after the exact decision update. A direct
`build_southern_historical_war_v1.py` preflight exited 1 at the blocked decision;
SHA256 checks confirmed that its manifest and four data outputs were unchanged.
Four Alabama 2018 adapter/audit-replay tests passed. No regional analytical suite,
full repository suite, rating fit, browser check or publication ran this continuation.
