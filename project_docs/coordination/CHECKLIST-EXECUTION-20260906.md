# Checklist execution — 2026-09-06

Owner: primary session / orchestrator. Status: checkpoint — three factual source
units and guarded source registration accepted. Overall checklist open.

Authority: user authorized autonomous progress through the existing checklist.
Preserve source evidence and unrelated work. No public release without its
required review; unresolved factual adjudications stay in review. No separate
checklist or orchestration framework.

## Ordered work

### Warehouse completion request (2026-09-08)

Resumed on the user's "Finish the work" instruction. Live latest warehouse run
still matches RUN-92AB8DE353AC47D6AECE3D7767C29FCD. Full raw 1998/2004 archive
hashes match their registry rows; complete year replays retain 196769/127069
rows but reveal 5430/10987 unmatched substantive records, respectively. No
updates applied. A read-only helper is isolating county/field drift while the
primary stages exact metadata-only matches. Never coerce these mismatches into
equivalence to fill source locators. Existing source and publication WIP persists.

- Owner/accountable role: primary session, warehouse_integrator; status: active.
- Objective: complete the remaining Phase 2 warehouse repairs and safeguards,
  reconciling checklist evidence against the September 8 live state.
- Scope: warehouse-04/05/06/08/09/10/11/12/13; preserve the already accepted
  source repairs, raw artifacts, stable identities and unrelated working changes.
- Non-goals: candidate scoring, model estimation, election predictions, public
  publication, commits or replacement of the populated warehouse.
- Snapshot: latest documented warehouse run RUN-92AB8DE353AC47D6AECE3D7767C29FCD;
  verify the live run before any application. Extensive existing WIP is present.
- Sequence: establish current unresolved source/dependency evidence; implement
  source and stale-input refusal at actual consumers; reconcile supported data
  dependencies; run integrity/replay checks; refresh existing catalog and record
  acceptance or concrete evidence blockers in the internal checklist.
- Acceptance: source preservation, explicit unknown/review states, tested join
  and source-quality refusal, scoped downstream freshness checks, recovery and
  independent review of consequential changes. A blocked source cannot become
  a complete allocation or accepted output through exclusion without its contract.
- Read-only helper /root/collision_review investigates warehouse-05 and legacy
  lineage/run evidence, using query-only connections; no files or databases may
  be written. Primary inspects source-consumer guards and stale-input boundaries.
- Warehouse mode initially read-only. Any live application requires verified
  separate backup and an exact staged transaction; no bulk loaders are scheduled.
- Handoff: primary owns checklist acceptance and execution evidence here.

Checkpoint: three neutral infrastructure units accepted (source-count guards,
declared dependency hash enforcement, legacy parser locators), with independent
read-only code reviews and 109 consolidated plus 14 parser tests passing. Live
full integrity/source-pattern/geometry checks passed on the unchanged latest
warehouse run in 202.61s. Detailed findings and limitations:
`../audits/WAREHOUSE_COMPLETION_REPAIRS_2026_09_08.md`. Internal checklist revision
`2026-09-08T14:47:16Z` remains 23/82; both viewport/browser persistence checks
passed. No additional Phase 2 task accepted in full; overall request incomplete.
No source values, canonical rows, analytical results or public files changed.
No live writer or partially committed transaction to recover. Existing source
repair replay commands retain their historical parser pins and must not be
silently repinned to the new metadata adapter. Next safe work is a registered-
source, full-cohort locator stage for 1998/2004; only unique exact pairs qualify
for a later guarded load. Source-grain adjudication, Morgan quarantine of cached
consumers, historical ingest/terms evidence, allocation replay, complete joins,
other publication routes and catalog reconciliation remain outstanding.

Resumed source-lineage unit, pre-application checkpoint:

- Initial strict proposal `artifacts/warehouse/legacy_source_lineage_20260908/proposal.json`
  (SHA256 `6754528ecc8953ff58391f188c63b4ef71d3ca24f4a52873e9f79691ce5c0725`)
  correctly proposed no updates because all counties had representation drift.
- Independent complete-cohort comparison and original-header inspection support
  only the two office spellings recorded in
  `../audits/LEGACY_SOURCE_OFFICE_EQUIVALENCE_2026_09_08.json`. Matching now records
  these explicit equivalences while retaining the original stored office field;
  all other substantive fields, including party, must match exactly. Forty-seven
  2004 counties remain refused. This is a documented source-evidence refinement,
  not removal of the office field from the matching key.
- An initial reviewed-stage attempt failed on abbreviated county keys in the
  review record. Corrected those to the literal warehouse keys with ` - GEN04`;
  no output or database mutation occurred in that failed attempt.
- Exact reviewed proposal:
  `artifacts/warehouse/legacy_source_lineage_20260908/reviewed-proposal.json`,
  SHA256 `171d2853604e6c8dddad336b8218e1b68c14364784931e2599f4f610d9d3e026`.
  87 fully reconciled cohorts contain 232434 records; 228882 unique metadata
  fills are proposed. Preserve 3552 ambiguous rows (1322 alternative groups)
  and all 91404 rows in refused cohorts. Proposal size: 136393589 bytes.
- New staging and application code use exact source/code/schema/run hashes,
  all substantive before-images, a verified new separate backup, transactional
  metadata-only authorizer, and full expected-after source digest. Original
  schema, source values, labels, ingest IDs and unrelated domains are protected.
- Focused consolidated tests: 70 passed in 3.92s with testmon deselection disabled.
  Independent exact-proposal review pending; live database remains unchanged.
- Planned sole-writer application uses `repair_sos_cell_lineage.py --apply
  --legacy-proposal <above> --proposal-sha256 <above> --backup
  data/processed/elections/backups/pre-legacy-source-locators-2026-09-08.sqlite`.
  On interruption, check the live build/QA and backup before retrying; never
  overwrite a backup or blindly replay a committed proposal.

Application checkpoint: the exact reviewed proposal failed its final source
digest check and rolled back. Independent full live/backup source, schema,
registry, build and QA digests match; latest run remains unchanged. Cause:
pandas staged integral row/column coordinates as floats, whereas SQLite INTEGER
affinity stores them as integers. Regression reproduced (1 failed, 25 deselected);
stage now emits integer coordinates. Consolidated verification: 71 passed in
4.20s without deselections. Preserve the failed proposal and verified backup.
Fresh `reviewed-integer-proposal.json` is being regenerated from raw sources;
it requires a new exact review and a new backup path before any retry.

Corrected proposal SHA256
`1ff5f7d6d9de09b51588670c97bd7491eda411ee4849435534720ef0ded35ee1`
passed independent delta review: same 228882 targets and evidence; only integer
coordinate representation, generation time and staging-code hash differ. Retry
started with new backup
`data/processed/elections/backups/pre-legacy-source-locators-integer-2026-09-08.sqlite`.
Inspect live build/QA before retrying after interruption. Registry URL/license
recovery code is independently reviewed with 38 passing new/existing tests;
its dry run remains unchanged and live application waits for source transaction
acceptance. Manifest SHA256 and exact source evidence are in the repair audit.

Retry committed successfully: `RUN-91B2A0C3435548A1B6932613B3073995`, QA
`SOSLEGACYCELL-BC8883A71B89FFC0267F04CE`; 228882 metadata fills and 2184861
full-source rows verified against the expected after-image. Do not retry.
Independent post-commit integrity/preservation verification is in progress;
registry application remains held until acceptance. No analytical rerun or
publication acceptance is implied by the source repair.

Source metadata unit accepted after independent full post-commit comparison,
all 120 table counts/schema/prior controls, full SQLite integrity and foreign
keys passed. Registry two-field application started against exact latest run
`RUN-91B2A0C3435548A1B6932613B3073995` with new backup
`data/processed/elections/backups/pre-shor-registry-metadata-2026-09-08.sqlite`.
No other live writer. Inspect build/QA before retrying after any interruption.

Registry committed as `RUN-55E4997B16DA4330BF6E2EE7A1E5FD36`; no active writer
or partial transaction remains. Do not retry either committed repair. Two
literal metadata fields filled; retrieval/scope/source contents unchanged.
Independent bounded postcheck pending. Parent registry verification: 38 tests
passed, no deselections. Checklist browser checks passed in desktop/mobile
contexts; test edits restored and browser closed. Current checklist remains
23/82; nine Phase 2 tasks remain open, with concrete source/dependency limitations
in the existing audit. No analytical or publication acceptance was added.

Final scoped registry postcheck accepted: exactly two intended fields changed,
full source digest unchanged, all prior controls/schema and table counts intact
except the one expected new build and QA row. Application backup quick_check
passed; no repeated full integrity scan required after this registry-only write.
Final checklist revision `2026-09-08T15:39:47Z` passed both browser viewports.
Overall warehouse completion remains unestablished; remaining factual source
adjudications and consumer revalidation are not waived by metadata recovery.

### Southern completion checkpoint (2026-09-08)

The Southern finish line was executed under
`SOUTHERN-WAR-COMPLETION-20260908.md`, which records the Alabama certified-source
authority decision, the accepted code units, the archived exact v3 bundle and the
ordered warehouse steps. After the user switched the session to manual-mode
prompts, the three warehouse writes committed (`RUN-DD7FF8C9ACBE4EAAA026AD1046693CA9`,
`RUN-4C2EF8D12CC442D99A516E0D393DE157`, `RUN-92AB8DE353AC47D6AECE3D7767C29FCD`,
each with a verified separate backup), v3 was retrained as
`WAR-POST2016-V3-4AF79A70EAA8F39EBD49` and independently approved for descriptive
historical use, and the historical run `WAR-SOUTH-HIST-V1-45EC0B380AAEA007C2DF` and
local map artifacts were rebuilt and browser-checked. Checklist: Southern 13/13,
overall 23/82. Publication was not performed. Latest warehouse checkpoint is
`RUN-92AB8DE353AC47D6AECE3D7767C29FCD`; do not rerun any committed apply.

### Fresh certified-source verification (September 7 local)

User requested correction of unresolved lineage and vote discrepancies. Do not
describe these as absent source data: the official local records are available.
Replayed `.venv/Scripts/python.exe scripts/load_alabama_2022_certified_source.py`
without `--apply`: exit 0 in 8.72 seconds, `warehouse_status: unchanged`, latest
run `RUN-3723F54646824B1682D8543BE39C7EC5`. Fresh source parsing, source hashes,
precinct/canvass reconciliation and exact existing-source-cohort comparison pass.
The existing certified cohort contains 140 contests, 211 named candidates and
140 write-in totals: 2,426,083 named-candidate votes and 30,426 write-in votes,
with zero reconciliation review rows. Unknown precinct cells remain unknown.

This verifies the certified source tables, not downstream analytical copies.
The previously reported HD32/68/92 differences must not be described as defects
in this already-correct certified cohort. No database mutation, analytical
refresh, publication or checklist completion is recorded by this verification.

Independent read-only source trace (`/root/al2022_dependencies`) resolved all 66
ballot codes in the 33-contest subset using the existing README decoder at
`scripts/build_incumbency_features.py:107`; normalized decoded names match the
certified names. It also found 10 count discrepancies among 173 major-party
`canonical_candidates` records, six in that subset. Thus source-name evidence is
recoverable, and discrepancies extend beyond the three previously named races.
These are downstream adoption issues, not missing or incorrect certified source
observations. No identity or numerical correction has yet been applied there.

### Current request: finish Southern legislative WAR (September 7)

Next assignment authorized by user: independent review of exact upstream
`WAR-POST2016-V3-8BB52074EC806C5BF6BF`. Read-only specification review delegated
to a fresh reviewer context; primary reviews standards, provenance/status and
integration evidence. Scope is current artifact bundle and implementation at
HEAD `88878b973fdac3cee95a8d8648da321e38e0021c` plus existing WIP, pinned by
manifest SHA256 `0ea558730b9e953d95853d552960886c855b8bb3f9fb9cb2ee0a3c44a47c7638`.
No source/model repairs, retraining, manifest promotion or publication authorized
by the review assignment itself. Record findings in the independent-review audit;
do not mark southern-07 complete merely because a review was performed.

Review assignment recorded in `audits/SOUTHERN_V3_INDEPENDENT_REVIEW_2026_09_07.md`:
NOT APPROVED. Fresh reviewer completed technical/spec provenance inspection;
independent scientific acceptance remains incomplete. Main ran four artifact
checks successfully; reviewer ran the remaining manifest test, which failed at
the intentionally revised contract hash. All13output/3code hashes match. No
manifest/model/source/output edits. Missing-context sensitivity and uncertainty
acceptance, source lineage and downstream approval enforcement remain open.
The next unit is a reviewed run-era/current contract disposition, followed by
the outstanding source and scientific review; not a blind model rebuild.

Goal: complete the existing 2016-2024 Southern v3-plus-backcast product against
southern-04/05/06/07/09/12/13, preserving the accepted schedule and map contract.
Non-goals: v4 promotion, optional finance expansion, unrelated product rebuilds,
or publication without separate approval. Existing prior checkpoints below remain
historical evidence rather than new authorization.

1. Reconcile exact upstream approval and source snapshots. Immediate non-database
   inputs of the historical manifest match, but the v3 source run
   `WAR-POST2016-V3-8BB52074EC806C5BF6BF` and its validation report explicitly remain
   pending independent validation. The downstream validated label does not resolve
   this conflict. Approval evidence has been requested; manifests remain untouched.
2. Produce reproducible, source-preserving exclusion and empty-slice accounting
   from the current warehouse. Do not turn eligibility flags into new adjudications.
3. Document Mississippi exact-history as retained deferred-v4 evidence, not a
   prerequisite for the current route; retain current v3 provenance requirements.
4. Only after source and approval reconciliation, verify the final regional bundle
   and browser/download behavior. An old passing build is not final acceptance.

Acceptance remains source/plan lineage, all scheduled slices accounted for,
reason-coded exclusions, current validated dependencies, regional regression
evidence and independent release review. No whole phase is closed by this plan.

Southern checkpoint (2026-09-08 00:07 UTC / September 7 local): no warehouse or
publication writes. `audits/SOUTHERN_RELEASE_READINESS_2026_09_07.json` records
all 4,582 existing outcome keys across 116 slices: 4,280 recorded-strict and 302
research-only. Outcome and context runs both remain
`RUN-85A4692E481448B6BB1380D76E07742B`; latest warehouse repair run is separately
recorded. The audit captures deployed SQLite definition hashes and code hashes.
Eleven isolated fixtures passed after independent review identified and prompted
a fix for omitted context-run provenance; final independent software rereview PASS
against code SHA256 `715a1b7deb7ffeb153b6c90776a3225a69cb636221a8653224397f9eacf45773`.

The 302 exclusions split into 151 experimental prior-winner incumbency rows and
151 cross-election precinct-membership baseline rows (VA lower 2017:60;2021:91).
97 source-file IDs remain missing. This is source metadata accounting, not
source certification, scored-result validation or reviewed public exclusions.
The recovered original 2018 context file matches all five consumed fields and
140keys exactly; its unconsumed changes remain unapproved. No manifest rewritten.
southern-09 accepted by independent documentation review as deferred-v4 evidence,
not resolution; Southern now7/13, overall17/82. Exact upstream approval remains
requested and unresolved. Source adoption/lineage and final regional/browser
checks remain open; do not run a publication builder against this checkpoint.

Southern checkpoint (2026-09-08 01:52 UTC): `southern-05` accepted, bringing the
Southern phase to 8/13 and the overall checklist to 18/82. Exact query-only
accounting confirms that the two empty Virginia lower-chamber slices contain all
151 baseline exclusions: 60 in 2017 and 91 in 2021. Their same-year governor
returns use 2019-plan cross-election precinct membership plus locality fallback;
the model note now states the precise contemporaneous-plan and allocation evidence
needed for recovery. No score was fabricated and source repair remains open.

The official Alabama 2018 certified canvass was acquired and hash-manifested at
the previously absent raw path, with a tracked acquisition audit. Exact source
tracing also shows the existing bridge repair can recover 0/97 Alabama scalar
links and that the staged certified 2022 cohort conflicts with the canonical
route in ten candidate totals across seven House contests.
`SOUTHERN_V3_RELEASE_DECISION.json` therefore records
`blocked_insufficient_evidence`. Both downstream builders now check that exact
decision before reading model rows. Fifteen focused guard tests passed; no model,
warehouse or public builder ran.

Alabama 2018 source checkpoint (2026-09-08 02:12 UTC): the official certified
canvass adapter is accepted after four focused tests, including exact audit
replay. It covers all 105 House
and 35 Senate districts, 352 candidate/write-in totals and all 67 precinct
workbooks. Physical-cell parsing retains 24,912 blank cells as unknown. Exact
contest/party/category reconciliation yields 322 matched totals and 30 review
rows. Four current strict Southern races intersect six major-party review rows,
with 12 votes of aggregate absolute difference. The canvass is still not
registered or bridged to the affected outcomes. The source is ready for a
reviewed staging proposal; no warehouse, model or publication output changed.

September 7 continuation: proceed through unblocked source-data units, not just
one checkpoint. Current sequence is certified 2022 all-candidate reconciliation,
then remaining source-key provenance/quarantine evidence. No political ratings,
candidate-performance models, election probabilities or publication are in scope.

1. Correct the isolated stale finance compatibility export identified by
   `WAREHOUSE_REPAIR_DEPENDENCIES_2026_09_06.md`. Acceptance: source-view parity,
   no numeric finance for incomplete rows, no non-finance changes, provenance,
   isolated regression checks, warehouse/sibling files unchanged.
2. `warehouse-03`: stage corrected precinct identities and links, preserving
   stable existing IDs and adjudication evidence; review before warehouse writes.
   Application scope: four identity tables plus retired-reference pruning in
   the five generated geography linkage/evidence tables. Withdraw source-transfer
   evidence only where its accepted source link was revoked; recompute affected
   canonical/conflict records from remaining evidence. Retain surviving direct
   2014 geometry only after relevant metadata parity checks. Preserve geography
   nodes/fingerprints, all manual files and unrelated source domains. Before-image,
   snapshot guard, transaction rollback and post-commit export evidence required.
3. `warehouse-07`: audit all roll-call readers and enforce equivalent canonical
   source-reconciliation gates where needed, without recalculating analyses.
4. Continue unblocked warehouse/checklist outcomes after accepted evidence.

Primary is the sole live warehouse and checklist writer. Bounded helper agents
have explicit disjoint code/test scopes in the ledger; reviewers remain read-only.
No helper may execute a live builder or write the populated SQLite warehouse.
Expand narrow write claims before adding implementation scopes and check collisions.

## Handoff

### September 7 completion continuation

New committed metadata checkpoint: `RUN-3723F54646824B1682D8543BE39C7EC5`.
4,083 NULL-only source locators/source IDs filled; six ambiguous observations
retained. Before/after evidence is in QA issue `SOSCELL-3171F6960B9DE8E7B24000D4`.
Backup: `pre-sos-cell-lineage-2026-09-07.sqlite` (5,780,967,424 bytes).
Audit: `../audits/SOS_CELL_LINEAGE_REPAIR_2026_09_07.json`. Full source hash after:
`4445e6f9137a9bebc4d2fee74f7089edbe9604d393a3851109b6be8fda822feb`.
Application exited 0, with verified backup, full source expected-after parity,
foreign keys and prior controls preserved. No substantive source changes or
analytical runs. Independent post-commit review PASS: all 4,083 before/after rows,
six unresolved rows, ingest IDs and non-locator fields match; all 119 table counts
preserved except QA +1/builds +1; schema unchanged and foreign keys clean.
Do not retry application.

Raw-quality implementation: 50 worker fixtures passed across quality, identity,
stage and application tests; four additional input-refusal fixtures passed for
the remaining direct readers. A live read-only scoped guard refuses the known
fractional source with physical provenance. Existing three live baseline tests
remain unchanged and unrun because their source dependency is unresolved.
Independent software review PASS for helper, eight integrations and two fixture
files: scoped pre-aggregation refusal and helper-hash replay checks verified.
The name-only renderer query still uses a vote sum
as a tie-breaker; removing that unnecessary numerical dependency remains open.

Active continuation at 21:57 UTC: the primary remains sole live warehouse writer.
Two disjoint fixture-only implementations are underway: unique SOS source-cell
lineage (4,083 proposed fills; six ambiguous rows retained) and raw fractional
reported-vote refusal at three aggregation entry points. Neither is accepted or
applied yet. Raw values, original ingest run IDs and analytical outputs must stay
unchanged. Ledger claims identify exact worker paths; independent review precedes
any warehouse application.

Dispatcher safety implementation removes only the superseded `build cmo`
shortcut and requires `--publish` for remaining publication targets. It does not
add a model route or certify release approval. Five mocked-subprocess regressions
failed before the change and passed afterward (0.33s); scoped diff whitespace and
CLI help checks passed. README, pipeline index and historical audit status agree.
Independent read-only standards/spec review passed against dispatcher SHA256
`49c354d9b92858ebffa5ebee03be9bdd3f72f9df7cbe372faf1482f40d09f393`.
No builders executed. Scope-03/release-01 remain open:
this limited cleanup is not complete four-product reproducibility or dead-code
certification.

Latest checkpoint: `RUN-986CDF1CB3CE44468E5C8218E7DB555D`, validated scoped
identity repair; checklist 16/82. The dated in-progress notes below are retained
as history, not instructions to retry. Both review exports completed. Do not
rerun the accepted stage against the new snapshot or reuse its backup path.
Evidence: `../audits/SOS_OFFICE_IDENTITY_REPAIR_2026_09_07.json` and the backup's
`.sqlite.application.json`. All 119 table counts, schema, foreign keys, entire
2,184,861-row source hash, eight protected tables and prior control rows passed.
Independent code, stage and post-commit reviews passed; 32 profile/default tests
passed. No full-suite/browser/model/publication acceptance is claimed.

Overall project is not complete. Candidate/party ratings and ideological-score
generation were not undertaken. The assistant communicated that it can support
factual data, software, documentation and validation infrastructure but cannot
create those political ratings/scores. Their checklist items remain open; this
is not a scope waiver or a scientific disposition. Remaining factual source
collisions, fractional-cell handling, allocation dependencies, source adoption,
reproducible release builds and public acceptance also remain open.

User requested completion of the whole checklist. Current scope retains the
existing four products; v4 migration/expansion and optional finance expansion
are deferred under the established contracts, not silently made prerequisites.
The current Democratic 1998–2022 public scope is explicit. Four independent
scope dispositions accepted; checklist is 12/82. No release certification.

Corrected the forecast template's structural-zero contradiction without model
or public-output changes. Focused test command:
`python -m pytest --testmon --testmon-noselect scripts/tests/test_forecast_dashboard.py -k template_distinguishes -q`
passed 1, deselected 21. Source inventory cards now distinguish the full
both-party research file from displayed eligible evidence; mocked-payload test
`python -m pytest --testmon --testmon-noselect scripts/tests/test_ideology_performance_page.py -k inventory_cards -q`
passed 1, deselected 11. Independent reviews PASS. No browser/full-suite or
analytical rebuild claimed; published copies remain pending validated rendering.

Active warehouse-03 unit: preserve the 72 existing Geneva 2010/Morgan 2012
precinct IDs while replacing source-office-dependent fingerprints and reviewing
source-link proposals. Existing CLIs have an old hard-coded scope, so do not run
them unchanged. Extend an explicit profile and review geography preservation
before any write. Five accepted Geneva direct links require name/code-only
matcher parity; all 43 affected source links are currently unaccepted. No
automatic source-transfer promotion or allocation/model rebuild. Starting run
remains `RUN-38DC9E26D9E24097A415038621E293EE`.

Further scope definitions accepted: adaptation contract checked against the
primary Split Ticket article and actual code; retrospective/predictive and
missingness/review acceptance boundaries explicit. Independent reviews PASS;
checklist 15/82. Old caucus PASS labeled historical, not recertification.

Office-dependent identity stage is ready for final independent stage review:
`data/processed/elections/precinct_identity_stage_sos_offices_20260907/`.
Manifest SHA256 `e08a156ba3afd00dabd8d7664b54956dc17da775d0a3abe093e189c6d8c0ba3b`.
32 isolated profile/default/rollback tests passed in 9.17s without warnings or
deselections; preapply code review PASS. Parent exact stage replay and geography
proof passed: 72 changed fingerprint IDs, all 45,132 IDs/metadata retained,
1,076,230 to 1,076,275 fingerprints; 36,090 source candidates and 10,297 links
retain their counts. 43 affected source suggestions remain review. All five
geography table hashes unchanged; 25 referenced Geneva nodes prove name/code
parity and retain five accepted direct links. No transfers revoked. No live
application yet. Apply only accepted hash/current run with a new backup; retain
manual files and inspect post-commit export state before any retry.

Independent actual-stage review PASS: all eight CSV hashes/counts, every node
record and outside-scope fingerprint/source-link rows match; 43 changed
suggestions remain unaccepted. Guarded apply started using the accepted stage
hash and expected run above, with new backup
`data/processed/elections/backups/pre-sos-office-identity-2026-09-07.sqlite`.
Application status is pending until its `.sqlite.application.json` and latest
warehouse build are inspected. Backup existence is not commit evidence.

### Accepted source-label correction; derived dependencies pending

Committed `RUN-38DC9E26D9E24097A415038621E293EE`; independent post-review PASS.
292 office/district corrections only; every vote, rowid and other field retained.
All 22 ambiguous records unchanged. Backup quick_check and expected full-table
digest passed; all 119 table counts compared, schema unchanged, foreign keys
passed. Only build/repair QA counts increased by one. Read-only replay reports
zero pending corrections. Full evidence: `../audits/SOS_OFFICE_REPAIR_2026_09_07.json`.
The following intake/application notes are historical, not pending commands.
Do not rerun the old apply. Checklist now 8/82: warehouse-03 reopened because
office-dependent fingerprints/linkage evidence require separate revalidation.
Next safe unit is bounded factual source-lineage/dependency reconciliation,
preserving ambiguities; no analytical scores, forecasts or publication.

Review and correct only source-supported office/district fields in the 292
uniquely paired Geneva 2010/Morgan 2012 observations identified by the retained
source staging audit. Keep all vote values, rowids, identities and 22 ambiguous
rows unchanged. Preserve physical source title/cell evidence and before-images
in repair QA. No broad source refresh, deduplication, allocation or model rebuild.
Require current registered hashes, exact full-cohort pairing, source-title
review, backup, transaction, narrow update authorization, rollback/replay tests
and independent review before live application. Start at run F135A5EC; do not
repeat the completed Alabama 2022 source append.

Pre-application independent review PASS; 24 isolated repair tests passed.
The read-only production dry run reproduced 292 corrections / 22 unchanged
ambiguous rows at the expected F135 run. Guarded application started with
`scripts/repair_sos_contest_offices.py --apply --expected-run
RUN-F135A5EC686C410CAF58BC5639804FA7 --backup
data/processed/elections/backups/pre-sos-office-repair-2026-09-07.sqlite`.
If interrupted, inspect the latest warehouse run and repair QA before retrying:
backup existence alone does not establish commit. Application code SHA256:
`0de89a5e56243b154987da4c82273cb318892ed8df1fe1905ad0a96d59cdacfb`.

### Accepted step 1: scoped certified Alabama 2022 source loading

Completed under `RUN-F135A5EC686C410CAF58BC5639804FA7`. Appended 140 source
sets, 351 literal certified candidate/category records, one reconciliation QA,
one repair QA and one build. Independent pre/post review PASS. All 119 table
counts checked; only declared five tables grew. Schema, source registry,
canonical identities/aliases/finance bindings, stored outcomes and AL2022 resolved
selection match the backup. Foreign keys passed. Backup quick_check and exact
before-image preservation passed before commit. Recovery and evidence:
`data/processed/elections/backups/pre-al2022-source-load-2026-09-07.sqlite`,
adjacent `.application.json`, and
`project_docs/audits/ALABAMA_2022_SOURCE_LOAD_2026_09_07.json`.

27 new isolated tests passed; 17 existing warehouse/history tests passed and
six affected history tests passed again on final code. No full-suite or browser
check claimed. Source sets remain review pending canonical adoption; shares,
winner and incumbent fields remain null. Physical source evidence and 22,018
unknown precinct cells retained. Shared history refresh now preserves separately
owned source sets/QA, including handling its own zero-output QA safely.

At that checkpoint, the next unit was review of 292 historical normalization
differences and 22 ambiguous records; the accepted correction above supersedes
that pending status. The source-load checkpoint was 9/82. Do not
rerun the committed apply with its old expected run or reuse its backup path.
Read-only verification: `python scripts/load_alabama_2022_certified_source.py`.

User specifically authorized step 1. Append the 140 certified contest sets and
351 candidate/category observations to existing source tables, retaining physical
lineage, write-in denominators and unknown precinct counts. No canonical identity,
result materialization, model, allocation or publication changes. Preserve the
new source through the shared history loader's refresh. Acceptance requires
focused rollback/replay/retention tests, independent review, a verified separate
backup, guarded transaction and exact source reconciliation. Starting warehouse
snapshot: `RUN-DA2442D0AD664F5681DE08E573D79A15`. Primary owns live application,
contracts and tracking; implementation is limited to the claimed loader/tests.

### Latest accepted continuation: certified source and original-label preservation

- Latest warehouse run is now `RUN-DA2442D0AD664F5681DE08E573D79A15`, validated.
  It added only certified-canvass registry source `SRC-DD940F20743C33261CC2`
  and one build/QA pair. Independent pre/post review PASS; all prior control
  rows preserved. Counts: 26,693 sources, 115 builds, 47 repair QA rows, 119
  tables. No vote or analytical output changed. The preceding FB393 run is
  historical, not the latest checkpoint.
- Complete source comparison: all 211 named candidates and 140 write-ins match
  the certified 2022 totals exactly, preserving 22,018 unknown precinct cells.
  Evidence: `project_docs/audits/ALABAMA_2022_CERTIFIED_SOURCE_RECONCILIATION.json`.
  Certified-total matching is no longer the blocker; canonical source selection,
  complete write-in denominators and existing consumer reconciliation remain open.
- Existing contest-sheet parser and source normalization retain exact printed
  labels and numeric cell coordinates. Pure parser replay preserves all prior
  values for 1,551 Geneva 2010 and 2,538 Morgan 2012 rows.
- Live comparison: 4,067 unique source-identity/value matches, 22 ambiguous
  records and 292 office/district normalization differences. Review packet:
  `project_docs/audits/SOS_CONTEST_CELL_LINEAGE_2026_09_07.json`. No live source
  refresh was applied; do not treat adapter parity as warehouse parity.
- Verification: 48 certified-adapter fixtures, nine contest-parser fixtures,
  21 source-interface/warehouse tests, five registration safeguards passed.
  Known warnings: fitz/SWIG deprecations and existing pandas concatenation warning.
  No full-suite or public-site browser/release validation was run.
- Final internal checklist checks passed JSON validity, stable IDs, 9/82 count,
  history/revision consistency and audit/code hashes. Workflow validation and
  scoped whitespace checks passed. Browser persistence recheck was unavailable:
  no local Playwright runtime and the browser connection reported no available
  browser. Checklist JavaScript and UI behavior were not changed.
- Recovery: `data/processed/elections/backups/pre-canvass-registration-2026-09-07.sqlite`
  is a verified separate before-image. Adjacent `.application.py` and
  `.application.json` preserve the exact operation; never rerun a committed
  append blindly. Source registration does not close historical lineage gaps.
- Remaining source-review boundaries: 5,271 collision groups lack physical
  locators; the 1994 fractional Morgan value lacks a justified correction or
  enforced slice-level quarantine. Preserve originals and unknowns. Shared
  history main performs broad replacement, so it is not a scoped loader for
  this new source. No political ratings, candidate-performance modeling,
  election probabilities or publication were undertaken.

### Prior checkpoint: Alabama 2022 official contest totals

- Latest accepted warehouse run: `RUN-FB3931B5261247C094477492E72AC7DB`.
  No prior repair is rerun.
- Goal: separate complete official contest totals from RDH split allocation
  inputs; retain source cells, write-ins and over/under categories separately.
- New evidence expands the recurrence fix from three contested races to all
  2022 major-party producer inputs: all 173 keys match SOS, with ten differing
  candidate totals across HD16/32/56/68/73/75/92. Do not hide these as per-race
  numeric overrides. Geometry/weights/baselines must remain unchanged.
- First acceptance unit: strict source adapter with physical cell lineage and
  a source-backed producer join preserving existing candidate codes and schema;
  fixtures must retain blank values as unknown and fail on malformed nonempty
  values, all-null candidate groups or ambiguous identities.
  Compare the full 173-row producer output, and prove allocation/weight parity.
- Subsequent warehouse application must reconcile canonical candidates, alias
  vote-match fields, stored Southern history and outcomes, with a reviewed
  write-in/denominator contract. Preserve IDs and original observations; no
  scalar-only patch that fabricates complete source coverage. Stage before
  transactional application and list every stale downstream consumer.
- Primary owns contracts, integration and checklist. Read-only dependency agent
  has no write claims. No analytical retraining or public-site publication.
- Review checkpoint: the proposed producer switch discarded subtotal/missingness
  metadata. It is not accepted: retain the factual source adapter, but defer
  producer integration until completeness is reconciled. The certified SOS
  canvass corroborates the ten disputed values; all 173 D/R keys have not been
  independently reconciled. No live numerical repair has occurred.
- Next action: reconcile the full source universe with certified contest totals,
  preserve write-ins and denominator evidence, then review source-only staging.
  Do not recalculate political ratings, candidate scores or election probabilities.
- Accepted evidence: independent review PASS after removing producer integration;
  final adapter-only tests 27 passed (1.04s), compilation passed. Final replay
  retains 10,477 unknown cells across 173 major-party diagnostic matches. The
  producer has no remaining diff. Checklist remains 9/82; no live data changed.

### Accepted prior unit: warehouse-08 Census check-time correction

- Goal: stop treating a file verification timestamp as an acquisition timestamp.
  The eight `us_census` manifest-backed rows exactly copy `checked_utc`; the
  downloader writes that field for both newly downloaded and cached files.
- Starting snapshot: latest warehouse run
  `RUN-C5CB7CFA8EB0454A9C65904A251D6CD2` is validated; prior repair is not rerun.
- Scope: existing registry sync and focused fixtures; metadata-only application
  may null only an existing Census retrieval field equal to its exact manifest
  check time after path/provider/hash verification. Preserve independent times,
  raw manifests, every other registry field, data domains and previous runs.
- Acceptance: reproduce current timestamp promotion; fix recurrence; new verified
  separate backup; guarded transactional writes and appended build/QA evidence;
  rollback/refusal fixtures; independent review and post-application comparison.
  No analytical rebuild, source acquisition, licensing adjudication or publication.
- Independent read-only task traces the remaining 97 Alabama records. The main
  agent owns integration, contracts, audit and checklist. No helper live writes.
- Status: independent preapplication review PASS; 18 focused fixtures passed
  (2.45s, no warnings/deselections) and 19 warehouse/source-repair tests passed
  (18.27s, one existing pandas warning). Reviewed application SHA256:
  `8dfbb96f24fa33d12d082c9d8715ced47f345cddec923e18cc9b3aa8d166ee5b`.
- Application committed as `RUN-FB3931B5261247C094477492E72AC7DB` with
  `data/processed/elections/backups/pre-census-check-times-2026-09-07.sqlite`.
  The adjacent `.application.json` was written successfully. Do not rerun the
  applied repair. Independent post-commit review PASS: all 26,692 registry rows
  preserve every field except the eight intended timestamps; prior build/QA
  history and source/code hashes match. Parent verified identical schema across
  119 tables, counts changed only for one build/QA addition, all outcomes
  unchanged and foreign keys valid. Nine acquisition dates are now explicitly
  unknown. Starting counts were 119 tables, 113 builds and 45 repair-QA rows.
  The 13 old running builds remain unchanged without completion
  evidence; missing terms/scope are not filled by provider-name inference.
- Checklist revision `2026-09-07T05:01:38Z` remains 9/82. Existing desktop/mobile
  browser checks passed at 1258px and 390px, restored their test edits and closed
  the dedicated session. Workflow and scoped whitespace checks passed (existing
  Git LF/CRLF warnings only). No full repository suite, analytical rebuild or
  publication. The full separate backup is 5,769,793,536 bytes.
- Next source outcome: the existing audit now pins the exact reproduction and
  source evidence for all 97 Alabama lineage cases. A direct official SOS scan
  confirms six major-party total discrepancies in HD32/68/92 in 2022, with
  write-ins and over/under categories kept separate. Stage a distinct source-data
  repair with a revised source contract, original cell locators, conflicting RDH
  observations retained, producer recurrence prevention and downstream impact
  review. No numerical field was changed by this timestamp unit.

### Accepted prior unit: warehouse-08 singleton source-file linkage

- Goal: recover only source-file scalar omissions supported by complete existing
  bridge evidence; prevent their recurrence in the existing preparation producer.
- Non-goals: no shared history schema migration, source acquisitions, numerical
  changes, eligibility changes, analytical rebuilds or publication.
- Verified starting run: `RUN-9984BE13204D46EBA6C529F80685B3E2`.
  Fresh read-only consensus query covers 377 official-state outcomes and all 955
  contributing records. The remaining 97 strict Alabama rows lack adequate
  transformation provenance and stay unresolved.
- Acceptance: singleton registered source for every contributor, all agree;
  source hashes verified; correct observation IDs/scope; only null official-state
  `source_file_id` fields updated; every other outcome field and readiness state
  preserved; separate verified backup; transactional rollback; fixture tests,
  independent review and post-commit source/provenance checks.
- Parent owns contracts, ledger, checklist and sole live database integration.
  Bounded implementer owns producer helper, scoped repair command and fixtures.
  No further delegation or live writes by the implementer.
- Status: committed as `RUN-C5CB7CFA8EB0454A9C65904A251D6CD2`; independent
  post-commit review PASS. All 377 supported scalar links restored, including
  evidence for all 955 contributors (201 third-party records). The 97 unsupported
  Alabama rows remain unchanged. 21 fixtures passed (parent run 10.16s, no
  warnings/deselections). Verified backup:
  `data/processed/elections/backups/pre-source-lineage-2026-09-06.sqlite`.
  Its adjacent `.application.json` records the committed mapping and safeguards;
  do not retry the live repair. Current checklist remains 9/82; warehouse-08 is
  broader than these recoverable scalar fields. Final integration passed:
  119 table counts checked; only one new build/QA record; all other outcome
  fields and readiness unchanged. Nine preparation tests passed in 541.48s,
  including full SQLite integrity and foreign keys (one existing pandas
  FutureWarning, no deselections). Browser checks passed at 1258px and 390px;
  test edits restored and session closed. Workflow and scoped whitespace checks
  passed. Checklist revision `2026-09-07T02:42:38Z`; see the repair audit for
  commands, recovery evidence and unresolved downstream provenance.
- Prior loader recovered by reversing only this unit's three producer edits,
  then verifying the exact preexisting manifest hash, not inventing a version:
  `backups/pre-source-lineage-2026-09-06.preparation-loader.py` under
  `data/processed/elections/`, SHA256
  `c71145d45139794d50ab62446ae303ddcb3cae02ce0bfa3e12656874614bf580`.

Accepted tranche. Isolated finance export: 9 targeted tests passed (one
pandas future warning), independent read-only review PASS, 110 unmasked
incomplete rows corrected to zero. Warehouse and six sibling hashes unchanged.
See `project_docs/audits/WAREHOUSE_CHECKLIST_REPAIRS_2026_09_06.md` for command,
before-image and exact output/snapshot hashes. Source snapshot remains the
September 6 inventory; recheck before writes. Precinct staging and source-only
roll-call gates are assigned disjoint code/test scopes in the existing ledger.
Roll-call source gates accepted: 45 targeted tests passed (one existing warning),
independent review and live standalone parity PASS. `warehouse-07` complete;
checklist 9/82 after warehouse-03 acceptance. Scoped identity stage passed independent read-only replay/review;
19 identity/application fixture tests passed with testmon deselection disabled.
Application committed as `RUN-9984BE13204D46EBA6C529F80685B3E2` with accepted manifest SHA256
`bdda18f7ba883f3cf1f2c1afab030494c04ea996d3635fa761d49a20d71e1c8a`
and new backup `data/processed/elections/backups/pre-precinct-identity-2026-09-06.sqlite`.
On interruption, inspect its `.application.json` and warehouse run before any retry;
the original stage is not replayable after a successful commit. Both review
exports completed. Full post-commit SQLite integrity, foreign keys, source/stage
and export hashes, schema/count scope and all 24 manual-file hashes passed;
independent post-commit review accepted warehouse-03 only. An additional 19
warehouse/parser tests passed. Internal checklist browser checks passed at
1258px and 390px: check/uncheck, counter/chart/history, persistence, filters,
portable export and evidence escaping. Test edits were restored and no public
site files were changed. Workflow collision validation and scoped whitespace
checks passed; Git emitted existing line-ending conversion warnings.
No scientific or publication acceptance is implied; the export correction did
not itself close a whole remaining checklist task.

Next safe technical outcome: investigate the remaining warehouse-08 acquisition
and transformation provenance. The 377 supported scalar omissions are repaired;
all 46 supporting registered artifacts matched their hashes. Do not rerun the
general history or preparation loaders for this correction. The remaining 97 Alabama rows
require actual transformation provenance; year-matching archives are not enough.
Source collision adjudication, Morgan quarantine, unrelated 2008 reconciliation,
allocation replay and catalog/publication gates remain open. No candidate scores,
election probabilities, analytical rebuilds or publication were produced here.
The current unit is limited to source-file provenance. Later analytical and
forecast checklist work follows the project-specific source, validation and
release gates; the source-repair acceptance above does not waive those gates.
