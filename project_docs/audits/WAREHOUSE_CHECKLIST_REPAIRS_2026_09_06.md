# Warehouse checklist repairs — 2026-09-06

Internal execution evidence under the user's autonomous checklist authorization.
See [task/handoff](../coordination/CHECKLIST-EXECUTION-20260906.md) and the
[pre-repair dependency inventory](WAREHOUSE_REPAIR_DEPENDENCIES_2026_09_06.md).
Neither technical acceptance nor an updated checkbox authorizes publication.

## Accepted: isolated finance compatibility export

The source SQL view was already repaired; the saved CSV still retained amounts
for 110 incomplete rows. Its regression test checked only the null ratio.
The existing loader now offers `--export-finance-only`, reuses a shared export
validation boundary, and reads SQLite without initialization or writes.

Executed:

```powershell
& .venv/Scripts/python.exe scripts/load_southern_war_preparation_warehouse.py --export-finance-only
& .venv/Scripts/python.exe -m pytest --testmon --testmon-noselect scripts/tests/test_southern_war_preparation_warehouse.py -q
```

- Result: 4,582 rows retained; 675 incomplete; incomplete rows with any numeric
  finance feature reduced from 110 to zero. Complete-row finance values and all
  non-finance fields agree with the preserved before-image and the corrected
  source query.
- Exact backup: `data/processed/elections/backups/pre-finance-export-2026-09-06.csv`.
  SHA256 `89cf801469168f47174bb6533a3431ce9ffad79a4e05d89211f4d8f9fef3e595`.
- Corrected CSV SHA256:
  `088bdb4d4c0d271945b7f44f7ad7d1443c1af19083789ed6ee93da6aecce30dc`.
  Its adjacent `southern_war_training_with_finance.manifest.json` records the
  query, view/code/output hashes, source row run IDs and export time
  `2026-09-06T18:16:56.047644+00:00`. It governs only this file, not the old
  bundle manifest's siblings or overall input readiness.
- Central warehouse SHA256 before and after:
  `2dfcdcb81079605b9ac36f5670d30957500f8cec74ddafa1da18b3eccd613377`.
  All six sibling file hashes, including the original bundle manifest, match
  before/after. No public or model outputs changed.
- Verification: new incomplete-amount assertion first failed on the saved
  defective export. Two scoped checks then passed after correcting a test-only
  CSV district dtype mismatch. Final affected module: **9 passed**, no
  deselection, **one pandas future warning** concerning null representation,
  114 seconds. This includes its existing SQLite integrity and foreign-key
  checks; it is not a full repository-suite pass.
- Independent read-only reviewer: **PASS**, reproducing source-query parity,
  non-finance/complete-row preservation, 110-to-zero masking, and
  backup/output/pipeline/view hash agreement. No additional framework or
  dependency was added; the existing producer was extended.

The original CSV can be recovered from the named backup, but doing so would
restore the documented defect. An interrupted CSV/sidecar replacement is
detectable by their hash mismatch; verify both before reuse.

## Accepted: warehouse-07 source-reconciliation gates

`scripts/legiscan_eligibility.py` reuses the canonical SQL views; it does not
duplicate the category-count algorithm. Read-only snapshots protect coherent
reads. The checked standalone boundary compares ordered provider roll-call
metadata, bill association, and actual member-vote contents rather than trusting
timestamps or matching IDs applied to unchecked CSV votes.

| Consumer under `scripts/` | Enforced boundary |
|---|---|
| `build_alabama_legislative_ideology.py` | Canonical votes; full raw roll-call QA retained, eligibility requires reconciliation `passed` |
| `build_unified_legislative_rollcall_warehouse.py` | Canonical source observations instead of cached eligibility/CSV votes; verifies temporary standalone contents before replacement |
| `build_candidate_rollcall_positions.py` | Canonical observations and IDs; human queue approval cannot restore an excluded source roll call |
| `build_legislative_issue_review_queue.py` | Canonical roll-call IDs and member-vote contents intersect the review universe |
| `build_anchor_vote_review_tranche.py` | Canonical source boundary; cached review entries cannot override it |
| `build_comprehensive_rollcall_classifications.py` | Canonical roll-call source and checked standalone snapshot |
| `build_full_candidate_legislative_ideology.py` | Checked standalone connections at direct source-read boundaries |
| `build_legislative_position_evidence_v3.py` | Checked standalone connection |

Intentional exemptions: source importer, warehouse loader, repair QA, SQL QA
views and `audit_legislative_ideology_coverage.py` may inspect unrestricted or
stale data as diagnostic evidence. They do not certify it as accepted analysis.
No classification/scoring rule was changed, and no analytical builder or
persisted evidence/analysis/page rebuild was run.

Verification:

```powershell
& .venv/Scripts/python.exe -m pytest --testmon --testmon-noselect scripts/tests/test_legiscan_eligibility.py scripts/tests/test_legislative_ideology.py scripts/tests/test_warehouse_data_repairs.py scripts/tests/test_legiscan_rollcalls.py scripts/tests/test_comprehensive_rollcall_classifications.py scripts/tests/test_full_candidate_legislative_ideology.py scripts/tests/test_legislative_position_evidence_v3.py -q
```

**45 passed**, no deselection, one existing SOS pandas concatenation future
warning, 15.49 seconds. Fixtures cover category-only conflicts, unknown codes,
stale/manual approvals, missing IDs, duplicate/missing/changed vote contents,
changed bill association, read-only access and later source invalidation.

Independent read-only review: **PASS**. The reviewer also ran the live checked
standalone comparison successfully and observed `query_only=1`. Thus no current
standalone rebuild is required for this source-integrity change. Its historical
journal component and downstream analytical validity were not certified by the
LegiScan provider check. Older evidence/publication dependencies remain open.

## Accepted: warehouse-03 scoped precinct identity

The initial review-only directory `precinct_identity_stage_20260906` also exposed
2008 drift across 67 counties. Earlier parsing corrections are described in
`HISTORICAL_MAP_AND_2008_CONTEXT_AUDIT.md`, but run-bound reconciliation to the
current normalized source remains missing. That directory is not approved for
unrestricted application and is retained as evidence.

The replacement scope in `precinct_identity_stage_20260906_scoped` is explicitly
SOS 1994, Marshall 2002 and Jefferson 2014. Outside-scope nodes/fingerprints stay
unchanged. It stages 45,132 nodes: 42,182 retained IDs, 2,950 new IDs and 2,488
retired IDs. Changed suggestions stay in review; unchanged sibling links retain
acceptance. Transactional application committed as
`RUN-9984BE13204D46EBA6C529F80685B3E2`, completed
`2026-09-06T18:47:57.482165+00:00`. No scores or analytical definitions changed.

```powershell
& .venv/Scripts/python.exe scripts/apply_precinct_identity_repair.py --stage data/processed/elections/precinct_identity_stage_20260906_scoped --stage-manifest-sha256 bdda18f7ba883f3cf1f2c1afab030494c04ea996d3635fa761d49a20d71e1c8a --backup data/processed/elections/backups/pre-precinct-identity-2026-09-06.sqlite
& .venv/Scripts/python.exe -m pytest --testmon --testmon-noselect scripts/tests/test_precinct_identity.py scripts/tests/test_apply_precinct_identity_repair.py -q
& .venv/Scripts/python.exe -m pytest --testmon --testmon-noselect scripts/tests/test_warehouse.py scripts/tests/test_sos_precinct.py -q
```

The new separate backup is 5,768,613,888 bytes. Before writes, its `quick_check`,
source fingerprint and all nine owned table contents matched the write-reserved
snapshot. The adjacent `.application.json` records the accepted stage hash,
executed code hashes, run, before/after geography hashes and review export hashes.
Both previous review CSVs are backed up alongside it. Do not rerun the original
stage after this commit: its before-state guard must now fail. Recovery must
first restore/check the backup at a separate path, never overwrite the populated
central database blindly.

| Generated table | Before rows | After rows |
|---|---:|---:|
| `precinct_nodes` | 44,670 | 45,132 |
| `precinct_vote_fingerprints` | 1,059,512 | 1,076,230 |
| `precinct_match_candidates` | 36,094 | 36,090 |
| `precinct_source_links` | 10,298 | 10,297 |
| `precinct_geography_match_candidates` | 41,043 | 41,038 |
| `precinct_geography_links` | 8,229 | 8,228 |
| `canonical_geography_evidence` | 7,291 | 7,183 |
| `canonical_precinct_geography_links` | 4,432 | 4,336 |
| `precinct_geography_conflicts` | 1,048 | 1,036 |

Retired-reference rows and revoked source-transfer evidence were removed only
from these generated products, with full before-images retained. This did not
delete source observations or adjudicate the unresolved source collisions.
All 10,124 unaffected links remain unchanged; 173 changed links remain unaccepted
review rows. The 173 surviving referenced 2014 identities passed exact metadata
parity before retaining their direct geography evidence.

Fresh targeted verification: **19 identity/application tests passed** in 4.94s
and **19 warehouse/parser tests passed** in 3.79s; no deselections or warnings.
Fixtures exercise rollback, stale/tampered stages, existing-backup refusal,
scope-preserving writes, trigger rejection, metadata mismatch and export failure.
Independent pre-application replay/design review and post-commit review both
returned **PASS for warehouse-03 only**.

Read-only post-commit checks found unchanged schema definitions across the
database and row-count changes only in the nine owned tables plus one build and
one repair-evidence row (119 tables checked). All four identity hashes match the
accepted stage; five geography hashes match the report; the source fingerprint,
foreign keys and both review export hashes pass. All 24 manual-file hashes are
unchanged. Independent review also confirmed no reference orphans and preservation
of all original repair records and 5,355 source-quality QA rows.

The two regenerated CSV hashes are:

- `precinct_link_review.csv` (10,297 rows):
  `2f88affc4fc992e24808675acfeac34282c396c97337e99b589b87d4311eaf3b`.
- `precinct_geography_review.csv` (8,228 rows):
  `ffd23b33b8a63bf02f3008b2db929770d1f074f04dd88d93776f69f68e751fb1`.

Historical weights, conflict-impact exports, baselines and dependent analytical
or public outputs remain stale/unvalidated. The transaction's QA evidence records
exports pending at commit; the completed build validation and application report
record their subsequent successful export. Fresh read-only full
`PRAGMA integrity_check` returned `ok` after commit. No full repository-suite
pass, broader allocation replay or integrated release acceptance is claimed.

## Remaining source-review evidence (warehouse-05/06, not closed)

A fresh read-only group query still finds 5,354 proposed-natural-key collisions:
1994: 83; 1998: 922; 2004: 3,661; 2006: 281; 2008: 326; 2010: 27; 2012: 54.
The 83 groups in 1994 reduce to two repeated provider precinct keys with
different printed place labels. Inspection used the immutable registered archive
`SRC-E64FFC4299ED54CB2D3A` and its original workbook rows, not inferred geography.

| Source county/key | Distinct source records | Collision groups |
|---|---|---:|
| `COVINGTN / 121` | `94g-prec/COVINGTN.XLS`, Covington sheet: Libertyville row 16 and Red Level-1 row 41 | 45 |
| `JACKSON / 37030` | `94g-prec/JACKSON.XLS`, Jackson sheet: Scottsboro row 45 and Hytop row 50 | 38 |

These are distinct printed source rows, not proof of duplicate ingestion.
The archive alone does not adjudicate the reused provider codes or certify the
reported totals. Keep both source observations and their cell lineage; do not
silently deduplicate, invent a corrected precinct number, or transfer geography.
Source-row physical identity and real-world precinct identity remain different
questions. This finding does not close all collision groups.

The fractional Morgan observation remains 144.4 at row 48, column 11 of
`94g-prec/MORGAN.XLS`, sheet Morgan, provider key `26001`. The earlier source
audit records conflicting K52/K53 totals. Its original value and QA review are
preserved; neither rounding nor an approved precinct-level correction has been
established. Merely recording that review is not completion of downstream
quarantine/reconciliation.

## Initial investigation: recoverable source-file lineage (warehouse-08 open)

Read-only investigation distinguishes a scalar-interface omission from missing
source evidence. Of 469 strict rows with missing scalar `source_file_id`, 372
official-state rows already have a unique registered file through
`bridge_southern_candidate_result_source`; another five research-only rows share
that recoverable condition. For each of these 377 rows, both constituent result
IDs have exactly one bridge file and agree on that file. All 46 supporting local
artifact hashes matched their registered SHA256 values. Eligibility must not
change during any metadata repair.

The omission is explicit `NULL AS source_file_id` in
`scripts/warehouse_southern_legislative_history_schema.sql`; the preparation
loader copies that scalar. The bridge's composite key allows multiple source
files per candidate record. A future metadata-only correction must require
cardinality one for each constituent and agreement between them, not choose an
arbitrary minimum from a multi-file set. Preserve the original bridge and all
non-provenance fields. Neither general loader is a safe scoped repair: both
rebuild wider tables. No lineage changes were applied during this initial
investigation; the subsequent scoped application is recorded below.

The remaining 97 strict Alabama rows originate from
`official_consolidated_candidate_results`, consuming the intermediate
`data/processed/war/race_candidate_results.csv` through
`scripts/build_candidate_identity.py`. Its `build_war_database.py` producer uses
the 2018 OpenElections precinct CSV and 2022 RDH source components, not the
year-matching SOS archives. The registered OpenElections scope is currently
identity enrichment; the intermediate lacks a run-bound manifest and matching
2022 component registrations were not found. Recover source contracts and
transformation lineage before attributing these rows. Do not attach an unrelated
archive merely because the year agrees. Unknown acquisition dates, terms and
legacy build states remain unresolved; warehouse-08 is not complete.

## Prior internal handoff verification

The internal checklist is 9/82, revision `2026-09-06T18:53:01Z`; stable IDs and
prior history were retained. Existing browser checks passed at 1258px and 390px
for check/uncheck, persistence, counters/history/chart, filters, export round-trip,
evidence escaping and overflow. Browser test edits were restored. Workflow
collision validation and scoped whitespace checks passed; only existing Git
line-ending conversion warnings were emitted. No public-site integration was
added. The full repository suite and analytical builders were not run.

## Accepted partial warehouse-08 repair (2026-09-07 UTC)

Metadata-only run `RUN-C5CB7CFA8EB0454A9C65904A251D6CD2` committed 377
previously null source-file links. It leaves all other outcome fields unchanged.
The original investigation above checked the major-party pair; application and
independent review additionally checked **all 955 contributing records**, including
201 third-party records. Every contributor has one registered bridge file, all
contributors to an outcome agree, and all 46 registered local file hashes match.

The existing preparation producer now uses this full-group consensus instead of
copying the first row's scalar. Missing, unregistered, multiple or disagreeing
sources remain unknown. Source tables and their many-to-many bridge are unchanged;
the shared history SQL has not been migrated. The owning data contract documents
this scalar meaning and its limits.

Applied command (exit 0):

```powershell
& .venv/Scripts/python.exe scripts/repair_southern_source_lineage.py --backup data/processed/elections/backups/pre-source-lineage-2026-09-06.sqlite
```

Recovery evidence is the separate verified 5,769,785,344-byte SQLite backup at
that path and its adjacent `.application.json`. The transaction updates only
owned null source-file fields, inserts one build and one repair-QA record, and
guards source evidence, readiness, schema changes and other writes. The report
records the complete mapping, before/after hashes and stale consumers. The code
hashes guarded before application were:

- `scripts/repair_southern_source_lineage.py`:
  `85d3a4f6cc9863f235ada7de0e8c8a6b250aa8b668fa44c0a3585b60fcee59e7`.
- `scripts/load_southern_war_preparation_warehouse.py`:
  `8e52a0e1fd027485c3bca0a13b40f224645c1744348ed415cc0f194a379bca1d`.

The prior loader was recovered by reversing only these producer edits and
verifying its exact preexisting manifest hash. It is retained as
`data/processed/elections/backups/pre-source-lineage-2026-09-06.preparation-loader.py`,
SHA256 `c71145d45139794d50ab62446ae303ddcb3cae02ce0bfa3e12656874614bf580`.
This is a verified recovered version, not a newly asserted acquisition date.
A read-only old/new producer comparison returned 4,582 identical rows except for
exactly the 377 supported source-file changes; it wrote no outputs or database.

Verification already accepted:

- `pytest --testmon --testmon-noselect scripts/tests/test_southern_source_lineage.py -q`:
  21 passed in 10.16s, no warnings, skips or deselections. Fixtures cover source
  ambiguity, third-party evidence, scope mismatch, non-provenance preservation,
  replay no-op, rollback, backup/hash refusal, trigger/authorizer guards,
  readiness rollback and report failure after commit.
- Independent pre-application and post-commit reviews: PASS, zero blocking
  findings. Post-commit review matched every mapping, unchanged unsupported
  Alabama rows, the complete SQLite schema, original build/QA records, and
  hashes of candidate sources, bridge records and the file registry to backup.
- All eight existing finance-free bundle files retain their pre-application
  SHA256 hashes. No analytical rebuild or public-site file was produced.
- Parent post-commit comparison checked all 119 table counts: only
  `warehouse_build_run` (112 to 113) and `qa_warehouse_source_repair` (44 to 45)
  increased. All non-provenance outcome fields and both readiness interfaces
  match the backup; the complete changed-field mapping matches the report and
  foreign-key checks pass. Exactly 97 unresolved scalar fields remain.
- `pytest --testmon --testmon-noselect scripts/tests/test_southern_war_preparation_warehouse.py -q`:
  9 passed in 541.48s, no skips/deselections. This includes full live SQLite
  `integrity_check` and foreign-key checks. One preexisting pandas FutureWarning
  concerns null-like `nan`/`None` comparison in the isolated finance export test.
  The full repository suite was not run.

Warehouse-08 remains open. The 97 Alabama records still require evidenced
transformation provenance; the local 2022 RDH README's provider retrieval date
does not establish this project's acquisition date. The registry inventory also
found one unknown retrieval time, 2,154 missing terms and 1,351 missing scopes
among 26,692 registrations. Thirteen older running build records have no proven
completion disposition; age alone does not authorize changing their statuses.
These gaps were not filled by inference.

Existing downstream provenance exports remain stale: the finance-free bundle,
Southern historical race/candidate CSV source-file fields, map provenance fields,
and dependent manifests. Unchanged numerical values are not refreshed provenance
or publication approval. The checklist stays 9/82, with warehouse-08 unchecked.

Final internal-page checks passed at 1258px and 390px using the existing
`scripts/tests/internal_checklist_browser_checks.js`: 82 stable task IDs,
check/uncheck, counter/chart/history, local persistence, filters, portable export,
evidence escaping and overflow. Test edits were restored and the dedicated
browser session closed. Revision `2026-09-07T02:42:38Z` records partial progress
without checking the broader task. Workflow collision validation and scoped
whitespace checks passed; Git emitted existing LF/CRLF conversion warnings.

## Follow-up: Census check-time provenance (warehouse-08 open)

The live latest run was rechecked as
`RUN-C5CB7CFA8EB0454A9C65904A251D6CD2` before this unit. The eight Census
crosswalk registrations match every manifest path, provider, SHA256 and
`checked_utc` value in `data/raw/census/source_manifest.csv` (manifest SHA256
`2e4eff90ca53f1104300750a019f9dcf502a69f6bfab9bf006cd211dccdfc5e1`).
All eight actual artifact hashes also match. The implicated files are
`BlockAssign2010_ST01_AL.zip`, `BlockAssign_ST01_AL.zip`, `al2010.pl.zip`,
`al2020.pl.zip`, `sldl_2022.zip`, `sldu_2022.zip`, `sldu_post2010.zip` and
`sldl_post2010.zip` under `data/raw/census/`.

`download_census_crosswalk_sources.py` writes `checked_utc` after inspecting
each file whether or not it downloaded it. The registry sync incorrectly maps
that verification field into acquisition time. Its actual sync-path fixture
reproduced the defect before the fix: one test failed because the check timestamp
became `retrieved_at_utc` instead of remaining unknown. These are not eight
recovered acquisition dates; the supported correction is to withdraw the
unsupported timestamps while preserving the original checks in the raw manifest.

Independent preapplication review passed, and scoped run
`RUN-FB3931B5261247C094477492E72AC7DB` committed all eight timestamp corrections.
No general source registry sync or historical builder ran. The separate backup
`data/processed/elections/backups/pre-census-check-times-2026-09-07.sqlite`
passed full SQLite `quick_check` and exact registry/control snapshot verification
before the updates. Its adjacent `.application.json` records the former values,
source/manifest hashes and the validated repair run; the CLI returned exit 0.
Application code SHA256:
`8dfbb96f24fa33d12d082c9d8715ced47f345cddec923e18cc9b3aa8d166ee5b`.

The existing sync now leaves Census acquisition time unknown when only a check
time is supplied. Eighteen focused regression/safety fixtures passed in 2.45s
with testmon deselection disabled, no warnings/skips/deselections. A separate
parent run of `scripts/tests/test_warehouse.py` and
`scripts/tests/test_warehouse_data_repairs.py` passed 19 tests in 18.27s using
`--testmon --testmon-noselect`, with one existing pandas concatenation warning.
The full repository suite was not run; the preceding unit's full live integrity
test is not claimed as a new test of this commit. The 13 older running builds
retain their existing statuses.

Post-commit acceptance passed independently and in the parent comparison:
all 26,692 registry rows match backup except the eight intended timestamps;
all prior build/QA records are identical; one validated run and one QA row were
added. Schema definitions across 119 tables are identical, and counts changed
only from 113 to 114 builds and 45 to 46 repair-QA rows. All outcome rows are
unchanged (SHA256 `16efbb0cc6432f8b18ae7d10fb12fa4aa9792b59a057a8c64ccf49977e70cecb`),
foreign keys pass, and all source/manifest/application hashes match. No matching
copied Census check times remain. Unknown acquisition timestamps increased from
one to nine: this corrects false precision, rather than claiming recovered dates.
The verified backup is 5,769,793,536 bytes.

Internal checklist revision `2026-09-07T05:01:38Z` retains 9/82 and all prior
history. Existing browser checks passed at 1258px and 390px for stable IDs,
check/uncheck, counters/chart/history, persistence, filters, safe portable export
and overflow. Test edits were restored and the dedicated session closed.
Workflow collision validation and scoped whitespace checks passed, with existing
Git LF/CRLF warnings. Nothing was copied to the public site.

## Alabama lineage replay and source disagreement (97 rows remain unapproved)

A bounded read-only trace separated current reproducibility from historical
provenance. The null-lineage scope is 64 outcomes in 2018 (49 lower, 15 upper)
and 33 in 2022 (25 lower, 8 upper), with 194 canonical candidate contributors.
All are labeled `official_consolidated_candidate_results`. The actual route is
OpenElections 2018 and RDH 2022 through `build_war_database.py`, then
`race_candidate_results.csv`, `build_candidate_identity.py`, canonical candidates
and the history view's hard-coded null source/`legacy-alabama-canonical` token.

The reader imported `load_oe`, `oe_cycle`, `rdh_2022_cycle`,
`consolidate_cross_party_candidate_aliases` and `race_tables`, but never called
the builder entry point or wrote outputs. Its replay matched all 377 saved
2018/2022 intermediate candidate rows and all 194 scoped canonical contributors
one-to-one on year/chamber/district/party, with zero vote or candidate-label
differences and zero cross-party transfers. This establishes a current replay,
not the original execution environment or acquisition dates.

There is also a substantive source disagreement. The RDH source README at
`data/raw/alabama_elections_and_geography/al_gen_22_prec/README.txt:505`
describes removal of 160 votes from the lower-house split geometry file and
directs complete-election analysis to its `no_splits` variant. Three of the
33 scoped 2022 outcomes have the following differences, independently reproduced
by the primary agent using read-only file sums and warehouse queries:

| District | Raw field | Warehouse = split | No-splits | Difference |
|---|---|---:|---:|---:|
| 32 | GSL032DBOY | 5,519 | 5,522 | 3 |
| 32 | GSL032RJAC | 4,389 | 4,390 | 1 |
| 68 | GSL068DJAC | 9,517 | 9,537 | 20 |
| 68 | GSL068RKEL | 8,948 | 8,981 | 33 |
| 92 | GSL092DHUB | 1,789 | 1,795 | 6 |
| 92 | GSL092RHAM | 11,778 | 11,812 | 34 |

The outcome IDs respectively are `WAROUT-B0957A5FA19595DBAC4B`,
`WAROUT-A0BA73AB003DCFAF2A89` and `WAROUT-C449CD9D19E0366785FF`.
The difference is 97 votes across six candidate records, coincidentally the
same number as the broader 97-outcome lineage scope. Other scoped 2022 candidate
totals match no-splits. README line 501 also documents original removals of
3 and 22 votes in two other contests: no-splits is not independently certified
against the official canvass by this comparison. No numerical correction or
scalar attribution was applied.

Reproduction of the source comparison uses `gpd.read_file(...,
ignore_geometry=True)` for `al_gen_22_sldl_prec.shp` and
`al_gen_22_no_splits_prec.shp`, then `pd.to_numeric(frame[field],
errors="raise").sum()` for each field in the table. Existing
`mart_southern_war_outcome` values match the split sums exactly.

Only the actual 2018 OE file is registered (`SRC-579280E800F6BF76A405`), with
`identity_enrichment` scope; the legacy election manifest marks it
`authoritative_votes=0`. Its license and URL are missing, and its recorded
retrieval timestamp was not independently authenticated. Neither the RDH ZIP,
its components nor the consolidated intermediate has a general source-file
registration. The warehouse has no explicit RDH candidate source-observation
set for these years; the split cells survive in immutable DBFs/archive, but
the derived totals entered canonical candidates without that provider distinction.
The latest candidate-identity run `RUN-872E84CE49F34E46A3B71A275F9C8890`
records years, not input hashes, so it cannot replace the legacy token merely
because row counts agree.

Pinned evidence SHA256 values:

- 2018 OE CSV: `de7efe5e395dd8d16d3b646785f3efc9975af1b59ddca9c06840438b7982eefd`.
- Intermediate `data/processed/war/race_candidate_results.csv`:
  `67703a6ec4329d377c2f76527a26e807d734f9ff009300eb75d177cdf887278c`.
- `scripts/build_war_database.py`:
  `d28ccbd58d7a1fbb6ddd1f3f70417ea761ea675c2e7175b153ccdd7031404926`.
- RDH `al_gen_22_prec.zip`:
  `a6ee8032feebfafbaf8d9f0ed5dedd7620c609f0954a5436b1706046dd8f797f`.
- RDH split lower DBF:
  `08cc0388627bc8770d1b81f38f0808ceb1ab412cfe83b190bf56e2720f71158f`.
- RDH no-splits DBF:
  `2b1977abb3594860c59936ce3d75e3d8a2f959fb830b50c5543c0dd8ef21810b`.
- Extracted README:
  `0b14fc47913f37087f25206656dc4630643f6ac4d76720e251259cc41e7510e7`.

The independent trace verified all 25 extracted shapefile components byte-match
their archive members. README line endings differ but decoded lines agree;
the archive README hash is
`462b17364666ef2cfc3e43fe226dc896b25697c8385e88ad5cc205a41d28bf87`.
Preserve both byte identities. A later source repair must reconcile the official
canvass, retain split/no-splits observations and establish source authority and
transformation lineage before changing canonical totals or dependent products.

### Official-source reconciliation for the three affected races

A subsequent independent read-only scan of all 67 workbooks in the registered
`2022 General Precinct Level Results.zip` supports all six no-splits major-party
totals in the table above. Source `SRC-389A837246D397F4E074` has archive SHA256
`4ea186b9e9eefa7786b3708b8ffd2da5755a9ba5c018b4ff9d47a2ceec46983a`
and registered `official_vote_counts` scope. Its URL/terms are missing and its
recorded retrieval timestamp was not authenticated in this investigation.
This was a local-source comparison, not a new acquisition or full canvass audit.

The raw scan and the existing normalized SOS rows agree on all six totals.
The normalized check filters `year=2022`, `source='alabama_sos'`,
`office='State House'` and `district IN (32,68,92)` before grouping by district
and party; office filtering excludes the different SD32 contest.
Direct workbook inspection uses the `Precinct Results` sheet, exact contest and
party headers, and numeric precinct columns starting at column 4. It retains
absentee/provisional columns, excludes summary-total headers, and found no
duplicate member/sheet/row/column cells or nonempty unparsed cells in scope.
The original write-in and over/under categories were retained separately:

| District | Precinct cells per major-party row group | Write-ins | Over/under votes |
|---|---:|---:|---:|
| 32 | 33 | 9 | 91 |
| 68 | 88 | 10 | 236 |
| 92 | 44 | 7 | 118 |

No additional named-party candidates occur in these source rows. Write-ins
cannot silently become missing or zero; over/under ballots are not candidate
votes. The stored normalized rows lack cell-level lineage, so this scan recovers
locators from the immutable archive rather than claiming the database has them.

One-based rows in `2022-General-<County>.xls`, sheet `Precinct Results`:

| District | County member | DEM row | REP row |
|---|---|---:|---:|
| 32 | Calhoun | 101 | 102 |
| 32 | Talladega | 92 | 93 |
| 68 | Clarke | 97 | 98 |
| 68 | Conecuh | 84 | 85 |
| 68 | Marengo | 83 | 84 |
| 68 | Monroe | 83 | 84 |
| 68 | Perry | 96 | 97 |
| 68 | Wilcox | 92 | 93 |
| 92 | Coffee | 98 | 99 |
| 92 | Covington | 86 | 87 |
| 92 | Escambia | 95 | 96 |

The write-in row follows REP; over/under rows are separate. RDH's documented
absentee redistribution means its removed amounts are not necessarily literal
original precinct cells: Calhoun column 36 has 3 D/1 R, Clarke column 10 has
18 D/32 R, and Escambia column 20 has 6 D/33 R. Therefore the 97-vote RDH
split/no-splits difference is supported by **race-wide** official totals, not
an asserted sum of those six original source cells.

Next implementation gate: distinguish official contest totals from allocated
RDH observations in the source contract; preserve cell-level evidence, the split
variant and write-in/over-under categories; prevent the producer from recreating
split totals; then stage a reviewed transactional canonical/outcome repair with
stable IDs, before-images and downstream invalidation. These three races are
source-supported for reconciliation, but their numerical repair has not occurred.
The other README omissions and the other Alabama lineage cases are not certified
by this narrow comparison.

### September 7 follow-up: factual source adapter and completeness gate

Full source comparison expands the discrepancy to ten candidate totals across
HD16/32/56/68/73/75/92 (185 votes in aggregate). The independent
[SOS final canvass](https://www.sos.alabama.gov/sites/default/files/election-data/2022-11/Final%20Canvass%20of%20Results%20%28canvassed%20by%20state%20canvassing%20board%2011-28-2022%29.pdf),
certified November 28, 2022, corroborates those disputed totals on printed pages
89, 105, 131, 145, 151, 153 and 169. This is not full 173-key canvass reconciliation.

The new read-only source adapter preserves archive/member hashes and physical
cell locators, original labels, named candidates, write-ins, overvotes,
undervotes and source summaries. Replay found 60,344 legislative cells:
21,566 observed and 38,778 explicitly unknown. Blank cells are not zeros;
211 named-candidate groups and 173 exact major-party README identity joins
do not by themselves establish complete certified totals.

Independent review rejected the initial producer integration because it dropped
the subtotal/missingness status before assigning ordinary vote totals. That
integration is deferred; the adapter is source preparation only. No live
warehouse numerical repair, generated output refresh, political scoring,
forecasting or publication occurred in this unit. Next gate is full certified
canvass reconciliation and reviewed write-in/denominator evidence.

Remedy review: independent Standards PASS and Spec PASS for source-adapter-only
scope. `build_war_database.py` has no remaining diff; the diagnostic identity
join returns a DataFrame retaining all aggregation/missingness metadata.
Focused verification: 27 tests passed with testmon deselection disabled (1.19s).
Workflow validation, checklist JSON/count/history consistency and scoped
documentation diff checks passed. No full suite or browser behavior check was
run; checklist changes only update embedded evidence/history, not behavior.

### Extended September 7 source-grain review

Read-only census still finds 5,354 proposed-key groups, 20,389 involved rows
and 15,035 excess rows. All 83 located 1994 groups have distinct physical source
cells; none is a demonstrated same-cell ingestion repeat. The other 5,271 groups
(20,223 rows) lack all five physical locator fields, so their duplication status
is unknown. Equal vote values in 633 groups are not evidence for deletion.

Geneva 2010 sheet `29` prints two YES headers (C2/E2), with separate numeric
Total Votes columns D/F. Morgan 2012 contains separate rows labeled
`DECATUR FIRE & RESCUE` and the same text with trailing whitespace (for example,
rows 5/22 on contest sheets `2` and `3`). These explain why normalized keys
collide, not whether the provider mislabeled or duplicated a reporting unit.
The source adapter must retain exact printed labels and physical coordinates;
no NO relabeling, geographic inference or deduplication is authorized by this evidence.

The fractional Morgan 1994 K48 value remains 144.4 in the source and canonical
authority view. K52 reports 21,571 and K53 calculates 21,571.4. Existing QA is
advisory, not enforced quarantine: direct raw-table consumers also exist.
Dropping that one cell or nulling it before ordinary SUM would falsely suggest
a complete aggregate. `warehouse-06` remains open pending a fail-closed,
slice-aware input contract; no original or canonical vote was changed.

### Accepted September 7 source adapter and staging units

- Certified 2022 reconciliation is now reproducible in
  `scripts/alabama_2022_official_results.py`: 211 named candidates and 140 write-in
  totals match exactly, across all 105 House and 35 Senate contests. Named votes
  total 2,426,083 and write-ins 30,426; all 22,018 unknown precinct cells in those
  categories remain unknown. The 351-row internal evidence packet is
  [ALABAMA_2022_CERTIFIED_SOURCE_RECONCILIATION.json](ALABAMA_2022_CERTIFIED_SOURCE_RECONCILIATION.json).
  The explicit LIB/L mapping uses printed party evidence, never generic O=L.
  Independent source review PASS; 48 focused fixtures passed with fitz/SWIG
  deprecation warnings. No producer or model integration was restored.
- The existing 2010/2012 contest-sheet parser now preserves physical cells and
  untrimmed labels. `_observations` carries those labels into source normalization.
  Original parser columns match exactly for all 1,551 Geneva 2010 and 2,538 Morgan
  2012 rows. Nine parser fixtures passed; 21 source-interface/warehouse fixtures
  passed with one existing pandas warning. Both parser and interface regressions
  failed on missing provenance before their respective fixes.
- A separate comparison with the live legacy rows is not a full refresh PASS.
  Vote/identity multisets agree, but 292 uniquely matched rows change office or
  district normalization: 108 Geneva federal-office rows, plus 184 Morgan
  federal-office/PSC rows. There are also 22 indistinguishable stored rows (18
  Geneva, four Morgan) that cannot receive unique physical source identities
  automatically. The exact review evidence is
  [SOS_CONTEST_CELL_LINEAGE_2026_09_07.json](SOS_CONTEST_CELL_LINEAGE_2026_09_07.json).
  No stored source result was refreshed or deduplicated.

These accepted source-only units do not close `warehouse-05`, `warehouse-06`,
or `warehouse-08`. The remaining ambiguous identities, historical source-field
normalization and downstream eligibility require their own reconciliation.

### Applied: certified canvass source registration

`RUN-DA2442D0AD664F5681DE08E573D79A15` appended source
`SRC-DD940F20743C33261CC2`, one build row and one QA row. The independently
reviewed application is retained at
`data/processed/elections/backups/pre-canvass-registration-2026-09-07.application.py`
(SHA256 `b5163ca095885faa817e5b008af8afdd2fa0384d9988faf50914c44f7634362b`).
Its adjacent `.application.json` records the committed result and exact input,
helper-code and prior-control hashes. Do not blindly rerun it.

The new separate backup `pre-canvass-registration-2026-09-07.sqlite` preserves
the pre-registration warehouse (5,769,793,536 bytes). Backup quick-check and
snapshot parity passed before the append; foreign-key checks passed before
commit. Five registration fixtures passed, covering append-only behavior,
rollback, unrelated-write denial, stale snapshots and backup refusal. An
intermediate test run failed because the isolated fixture lacked newly hashed
helper files; the fixture was corrected and the final five passed in 1.24s.

Independent post-commit review PASS: every prior registry/build/QA record and
the schema are unchanged. Registry count is 26,693, build count 115 and repair
QA count 47. Parent verified counts for all 119 tables; only those three counts
changed. Existing outcome rows hash identically to the backup. No source vote,
canonical result, candidate rating, forecast, generated page or model was changed.

The acquisition manifest and source reconciliation JSON are dated pre-registration
snapshots; their pending-registration statements are historical, not current status.
This applied-run record controls present registry status. Explicit redistribution
terms remain review. Registration and certified totals do not reconstruct old
Alabama transformation lineage or automatically repair canonical results.

Do not feed the new source into an unscoped history refresh: the existing
`load_southern_legislative_history_warehouse.py` main routine deletes and rebuilds
the shared source observation sets and canonical history. Source-only registration
does not authorize that wider replacement or certify its affected consumers.

### Step 1 preflight: scoped certified-source ingestion

The September 7 follow-up authorizes source ingestion only. The latest run was
rechecked as `RUN-DA2442D0AD664F5681DE08E573D79A15`; the registered certified
PDF still matches its immutable manifest. Before ingestion: 52,231 observation
sets, 82,361 candidate observations, 50 source reconciliation rows, 115 builds,
47 repair QA rows and 119 tables. No warehouse triggers were present.

The source sets will retain exact source reconciliation while remaining
`validation_status=review` for pending canonical adoption. This is a promotion
boundary, not a claim that the verified certified votes are defective. Existing
resolved-history and positive-incumbency readers exclude review sets. No source
candidate ID is a replacement for a canonical person/candidate ID. The new
all-candidate denominator includes the separately retained write-in category.

Existing warehouse/history fixtures passed: 17 tests via repository Python,
`pytest --testmon --testmon-noselect scripts/tests/test_southern_legislative_history_warehouse.py scripts/tests/test_warehouse.py -q`.
This is preflight verification, not a claim that the pending application passed.

### Applied and verified: scoped Alabama 2022 certified source load

`RUN-F135A5EC686C410CAF58BC5639804FA7` appended 140 source sets and 351
literal source records (211 named candidates and 140 write-in categories),
one reconciliation row, one repair QA and one build. The immutable certified
canvass is linked from the [official SOS 2022 election page](https://www.sos.alabama.gov/alabama-votes/voter/election-information/2022).
Source votes reconcile exactly; source metadata preserves 22,018 unknown
precinct cells. Vote shares, incumbent and winner fields remain null. All sets
remain review for pending canonical adoption; no source observation replaces
an existing person or candidate ID.

The source loader defaults to read-only inspection. Application requires an
explicit expected run and a new separate backup. It checks registered source,
audit, manifest and code hashes; holds a transaction; denies unowned writes;
verifies the backup and exact old-row preservation; and refuses conflicting
replays. A matching existing cohort is a no-op. The history refresh now clears
only its owned source families/parser QA, retaining this separate source.
The empty-MEDSL QA regression found in review was fixed and tested before apply.

Recovery: `data/processed/elections/backups/pre-al2022-source-load-2026-09-07.sqlite`
(5,769,797,632 bytes), with committed `.application.json`. Never overwrite this
backup or blindly rerun the old application. Loader SHA256:
`87da270cacc572a3a3143978423d8bd6b5fa4aceb757400d3ec4464ed8f73442`.
History-loader SHA256:
`37372b2bce5332c9c97b5ee2b5f2445718e79126cb0992da246c0d25e3530c4f`.

Verification: 27 new tests passed (isolated testmon cache), 17 existing
warehouse/history tests passed, six affected history tests rechecked on final
code. Independent pre/post review PASS. Parent verified counts of all 119
tables against backup, unchanged schema, exact protected identity/alias/finance
binding and outcome rows, unchanged AL2022 resolved selection, and zero foreign
key violations. Before append, backup quick_check returned only `ok` and old
source/control snapshots matched. See `ALABAMA_2022_SOURCE_LOAD_2026_09_07.json`
for machine-readable evidence. No full suite, live general-history rebuild,
model calculation, publication or browser verification ran. Broader source
adoption, historical repairs, source terms and consumer validation remain open.

### Historical office correction: independently reviewed source mappings

The 292 proposed corrections are supported by exact printed contest titles:
Geneva 2010 sheet 4 is United States Senator (54 rows); sheet 5 is United States
Representative, 2nd Congressional District (54). Morgan 2012 sheet 3 is United
States Representative, 5th Congressional District (92); sheet 15 is President,
Public Service Commission (92). Thus the latter is not the presidential contest.
Both archive/member hashes match the existing `SOS_CONTEST_CELL_LINEAGE_2026_09_07.json`.
All physical vote locators are unique and retain the original values.

None of the 22 ambiguous snapshot matches overlaps the changed sheets. All 22
remain untouched in this unit. Independent review found that retaining unchanged
office/district in a later matching key resolves 16 cross-contest referendum
ambiguities; six row-to-cell attachments remain unresolved. Equal values and
row order are not identity evidence. Do not silently broaden this correction
into that separate lineage assignment.

Dependency review: `build_precinct_identity.py` reads office to derive vote
fingerprints, which feed matching/link evidence and geography consumers. Those
affected county/year products require revalidation after a label correction.
`build_historical_federal_baselines.py` already normalizes the old federal
titles, so label changes alone do not establish numerical baseline differences.
The inspected candidate-identity, legislative-weight and Governor/Attorney
General readers filter other offices and their direct inputs are unchanged.
No model or allocation builder was run by this source review.

Application accepted as `RUN-38DC9E26D9E24097A415038621E293EE` with QA
`SOSOFFICE-668570F62509C603C27FD2F7`. 24 focused tests passed in 4.40 seconds,
no warnings/deselections. Independent pre/post review PASS. Verified separate
backup is `data/processed/elections/backups/pre-sos-office-repair-2026-09-07.sqlite`
(5,780,525,056 bytes). Backup quick_check and full source before/expected-after
digests passed. All 119 table counts compared: only build and repair QA added
one row each; schema unchanged and foreign keys passed. The original 92-row
misclassification reproduction now returns zero. Read-only repair replay reports
no pending differences. Full evidence and code hashes are in
`SOS_OFFICE_REPAIR_2026_09_07.json`; physical locators and all before/after rows
are in the retained warehouse repair QA. No full suite or browser check ran.
Checklist warehouse-03 is reopened (8/82), preserving prior history, because
new source labels invalidate affected derived fingerprint/linkage evidence.

### Office-dependent identity repair accepted

The reopened dependency is now repaired by
`RUN-986CDF1CB3CE44468E5C8218E7DB555D`. The new explicit `sos-office-labels`
profile preserves the prior default scope and requires the expected source run.
All 45,132 node records/IDs remain unchanged; fingerprints for 72 existing
Geneva/Morgan precincts were rebuilt, with 43 review suggestions unaccepted.
Old/new name/code matcher parity preserves all five geography tables and five
accepted direct links. No source transfers were revoked or promoted.

32 focused profile/default/rollback tests passed in 9.17s without warnings or
deselections. Verified separate backup quick_check, stage replay, independent
code/stage/post reviews and both review exports passed. Parent post-checks
verified all 119 table counts, unchanged schema, foreign keys, full source-row
hash, eight protected-table hashes and prior control-row preservation. The
source table remains exactly 2,184,861 rows; only fingerprint count (+45) and
build/QA counts (+1 each) changed. See `SOS_OFFICE_IDENTITY_REPAIR_2026_09_07.json`
for accepted hashes, recovery paths and unresolved consumers. No full suite,
browser or analytical/publication rebuild ran. warehouse-03 is reaccepted;
other scope dispositions bring the internal checklist to 16/82, not completion.
