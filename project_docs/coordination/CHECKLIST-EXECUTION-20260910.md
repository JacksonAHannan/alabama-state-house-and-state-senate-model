# Checklist execution — 2026-09-10

Owner: primary session / orchestrator. Status: active. Supersedes the closed
Southern umbrella in `CHECKLIST-EXECUTION-20260906.md`; that record and its
checkpoints remain historical evidence.

Authority: user instruction "Proceed with next steps" against the internal
checklist at revision `2026-09-08T15:39:47Z` (23/82). Standing constraints: no
commit, no `docs/` publication, no central-warehouse write, no retraining of the
approved Southern v3 residual source, preserve unrelated working-tree changes.

## Starting evidence

- HEAD `720c350`; worktree carries 161 modified, 2 deleted and 1,874 untracked
  files from accepted-but-uncommitted 2026-09-06..08 work.
- Approved Southern residual source: `WAR-POST2016-V3-4AF79A70EAA8F39EBD49`
  (`audits/SOUTHERN_V3_RELEASE_DECISION.json`, 2026-09-08). Latest analytical
  warehouse target `RUN-92AB8DE353AC47D6AECE3D7767C29FCD`; two later
  metadata-only runs (`RUN-91B2A0C3…`, `RUN-55E4997B…`) changed no source values.
- Stale consumers found: `data/processed/war/alabama_war_v1/manifest.json`
  (`AL-WAR-V1-688D1D476170C330841D`) and
  `data/processed/war/alabama_historical_war_v1/manifest.json`
  (`AL-HIST-WAR-V1-EA0E2C252439D4584227`) both record
  `source_southern_war_run_id = WAR-POST2016-V3-8BB52074EC806C5BF6BF` (NOT
  APPROVED, archived) and warehouse run `RUN-85A4692E481448B6BB1380D76E07742B`
  (pre-repair). `alabama_war_forecast_v1_manifest.json` records the same
  warehouse run. Their declared `input_hashes` for the v3 exports no longer
  match disk. Neither Alabama builder checks the Southern release decision.
- Ideology: `IDEOLOGY-ROLLCALL-OPENAI-CLASSIFY-20260908` and
  `SPONSORSHIP-IDEOLOGY-PIPELINE-20260908` are accepted with independent review
  but no Phase 5 checklist task carries their evidence; governance documents
  still describe the superseded human bill-review layer.

## Ordered work (this cycle)

Ledger rows in `active_tasks.csv`; collision validator passed.

1. `ALABAMA-WAR-DEPENDENCY-REBUILD-20260910` (primary, serialized shared-mart
   regeneration): rebuild `alabama_war_v1` then `alabama_historical_war_v1`
   from the approved v3 run and current warehouse. Supports `alabama-03`,
   `alabama-09`; does not close them without the parity and universe audits.
2. `PRODUCT-STALE-INPUT-GATES-20260910` (isolated worktree, warehouse-11):
   extend `southern_war_release_gate` checks to the Alabama builders, the
   historical story page and the forecast renderer.
3. `MORGAN-1994-QUARANTINE-20260910` (warehouse-06).
4. `ALABAMA-RACE-UNIVERSE-AUDIT-20260910` (alabama-02/03 evidence, read-only).
5. `IDEOLOGY-COVERAGE-FUNNEL-20260910` (ideology-01 evidence, governance docs).
6. `FORECAST-PUBLIC-CONTRACT-AUDIT-20260910` (forecast-01/05/06 evidence).
7. `WAREHOUSE-RECOVERY-VERIFY-20260910` (warehouse-12 recovery evidence).

Memory: host has 16 GB with ~3 GB free at start; only the primary runs
pandas-heavy warehouse loads, one at a time. Helpers use bounded SQL over
`mode=ro` connections or CSV-only reads.

Acceptance is recorded per task below when reviewed; checklist edits follow
acceptance, never dispatch.

## Checkpoints

### Checkpoint 1 (2026-09-11 04:15Z)

Accepted: `PRODUCT-STALE-INPUT-GATES-20260910` (plus the primary's shared
`require_alabama_historical_release` and the ideology-page gate),
`SOUTHERN-V3-INPUT-REVISION-20260910` (independent review PASS, decision file
amended, run id and published outputs unchanged), `WAREHOUSE-RECOVERY-VERIFY`,
`MORGAN-1994-QUARANTINE` (audit), `ALABAMA-RACE-UNIVERSE-AUDIT`,
`IDEOLOGY-COVERAGE-FUNNEL`, `FORECAST-PUBLIC-CONTRACT-AUDIT`. Checklist
`warehouse-11` checked; revision `2026-09-11T04:13:29Z`, 24/82, browser checks
passed at 1258 and 390 px.

`ALABAMA-WAR-DEPENDENCY-REBUILD-20260910` is **blocked**: `alabama_war_v1`
rebuilt (`AL-WAR-V1-E08D6FCD1A8A49BA6DAD`); the historical builder refused on
seven superseded compatibility totals, and regenerating those inputs is refused
by the Morgan 1994 cell. Required owner decision: `warehouse-06` disposition
(retain-as-reported with stale flags / reviewed adjudication to the provider's
reported integer total / explicit exclusion). Until then the historical export,
`docs/cmo.html`, the ideology page's WAR join and the forecast bundle remain
stale and are refused by their gates; the failing on-disk page tests
(`test_ideology_performance_page.py`, `test_grimsley_2018_is_exact_published_race_residual`)
are correct signals and were not weakened.

Open source questions surfaced (not adjudicated): 2002 House 27 present as a
contested race in the SOS source but absent from `canonical_candidates`;
`comprehensive_rollcall_classifications.csv` modified vs HEAD as an unsettled
ideology scoring input; 2002 House 26 conflicting `vote_observations` sets and
2014 corrupted party labels (warehouse-04/05 evidence).

Next safe actions after the disposition: regenerate
`canonical_cmo_features.csv`/`canonical_cmo_candidates.csv` →
`rebuild_cmo_candidate_quality_v5.py` → `build_alabama_historical_war_v1.py` →
story and ideology page local artifacts → `run_alabama_war_generic_forecast.py`
(after `forecast-04` policy) → forecast renderer with edits E1–E9. No
publication without separate authorization. Do not rerun either committed
2026-09-08 warehouse apply.

### Checkpoint 2 (2026-09-11 05:16Z)

Owner decisions taken this cycle: (1) approved v3 run stays the run of record;
consumers catch up (implemented as reviewed `accepted_input_revisions`, two
revisions, both independently reviewed PASS); (2) `warehouse-06` option A —
adjudicate the Morgan 1994 cell to the provider's reported total 144.

Accepted: `MORGAN-1994-ADJUDICATION-APPLY-20260910`
(`RUN-C0A15A7AB6A6403991BB5FE5143BACFF`), `SOUTHERN-V3-INPUT-REVISION-20260910`
(revision 2). Checklist `warehouse-06` checked; revision `2026-09-11T05:15:39Z`,
26/82.

`ALABAMA-COMPAT-CHAIN-REGENERATION-20260910` ran to the historical builder and is
**blocked** there: compat legislative margins now agree with the certified
`alabama_war_v1` 97/97, but the approved v3 run's Alabama same-cycle ticket
baseline equals the 2026-08-21 federal build and differs from the regenerated
baseline in most districts (max 13.4 pp; `audits/ALABAMA_TICKET_BASELINE_STALENESS_2026_09_11.json`).
Required owner decision: retrain v3 with the refreshed Alabama context (new run,
independent review, Southern historical/map rebuild and republication) or keep
the approved run and record the limitation. Until then the historical Alabama
WAR, both Alabama pages and the forecast remain stale and gate-refused.

Also flagged for adjudication: 2002 HD26 baseline moved 19.9 pp after the
identity re-keying (Marshall County conflicting observation sets, `warehouse-05`);
2002 HD27 absent from `canonical_candidates`.

### Checkpoint 3 (2026-09-11 05:56Z)

Owner decision: retrain v3 on the refreshed Alabama context. Executed under
`SOUTHERN-V3-RETRAIN-REFRESHED-CONTEXT-20260911` (`audits/SOUTHERN_V3_RETRAIN_2026_09_11.md`):
panel → preparation `RUN-504CE4C4DF904D88A5A40D268F3FCEAB` → archive of
`4AF79A70` → retrain `WAR-POST2016-V3-A937708D4E0A5232D3F5` → 15+9 tests →
sensitivity parity → independent review APPROVED → decision re-bound (55 gate/v3
tests pass) → `alabama_war_v1`, `alabama_historical_war_v1`, forecast bundle,
Southern historical run rebuilt; page candidates under `artifacts/site/`.
Checklist `alabama-03`, `alabama-09` accepted; revision `2026-09-11T05:55:16Z`,
28/82.

Awaiting owner authorization: publication of the four pages (`docs/`), which
all still reflect the superseded lineage. Before publication the Alabama
validation card (`alabama-11`) must carry the 2014 HD52/HD56 and 2002 HD26
baseline-driven changes, and the forecast public-contract edits E1–E9 should be
applied. The Southern map builder runs only at publication time.

### Checkpoint 4 (2026-09-11 14:50Z) — released

Structural fix implemented (training-frame digest; run
`WAR-POST2016-V3-530FBD4238CC483E557C`, outputs byte-identical, contract review
APPROVED). Forecast edits E2–E8 applied; Alabama release card published; all
four products republished and browser-checked (`audits/SITE_RELEASE_2026_09_11.md`).
Commit `f407b9d0` pushed to `origin/master`; rollback reference `720c350`.
Checklist 32/82. Umbrella closed; next work items are listed in the release
record's limitations and the checklist.
