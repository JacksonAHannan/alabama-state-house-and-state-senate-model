# Alabama WAR dependency rebuild — 2026-09-10

Execution evidence for `ALABAMA-WAR-DEPENDENCY-REBUILD-20260910` under
[CHECKLIST-EXECUTION-20260910.md](../coordination/CHECKLIST-EXECUTION-20260910.md).
Status: **partially complete, blocked.** The modern Alabama WAR export was
rebuilt from the approved Southern run; the historical backcast refused,
correctly, because its compatibility inputs predate the certified-canvass
repair. No publication, commit, or warehouse write occurred.

## Starting state

Working-tree manifests (snapshotted to
`artifacts/war/alabama_dependency_rebuild_20260910/*.pre-rebuild.manifest.json`
with `pre-rebuild.hashes.json`, nine files):

| Export | Run | Southern source | Warehouse run |
|---|---|---|---|
| `alabama_war_v1` | `AL-WAR-V1-688D1D476170C330841D` | `WAR-POST2016-V3-8BB52074EC806C5BF6BF` (NOT APPROVED, archived) | — |
| `alabama_historical_war_v1` | `AL-HIST-WAR-V1-EA0E2C252439D4584227` | `WAR-POST2016-V3-8BB52074EC806C5BF6BF` | `RUN-85A4692E481448B6BB1380D76E07742B` (pre-repair) |
| `alabama_war_forecast_v1` | build `b5ae4b8054e027862fbe` | via `alabama_war_v1` above | `RUN-85A4692E481448B6BB1380D76E07742B` |

Approved source: `WAR-POST2016-V3-4AF79A70EAA8F39EBD49`
(`SOUTHERN_V3_RELEASE_DECISION.json`, 2026-09-08), warehouse
`RUN-92AB8DE353AC47D6AECE3D7767C29FCD`.

## Release-gate refusal and reviewed input revision

`require_approved_release` on the approved v3 manifest refused with
`Declared manifest file changed: data/processed/elections/alabama_elections.sqlite`.
The declared digest `8cb49945…` was the live file at fit time (13:19:42Z); the
two later metadata-only runs `RUN-91B2A0C3435548A1B6932613B3073995` and
`RUN-55E4997B16DA4330BF6E2EE7A1E5FD36` left it at `77379bb5…`.

Evidence: a scratch replay of the v3 fit against the current warehouse
(`artifacts/war/alabama_dependency_rebuild_20260910/v3_scratch_replay.py`,
outputs under `v3_scratch/`, nothing approved touched) reproduced all 13
approved CSV outputs byte-for-byte without the `model_run_id` column, with equal
diagnostics, configuration, code hashes and warehouse run; only the sqlite
input hash differed. The scratch run id `WAR-POST2016-V3-142199F69DF8300F1E20`
differs solely because the run id is derived from input hashes.
[SOUTHERN_V3_INPUT_REVISION_2026_09_10.json](SOUTHERN_V3_INPUT_REVISION_2026_09_10.json)
records the digests, ledger sequence and replay; the backup-mechanism
explanation of the byte lineage comes from
[WAREHOUSE_RECOVERY_VERIFICATION_2026_09_10.md](WAREHOUSE_RECOVERY_VERIFICATION_2026_09_10.md).

Owner direction (2026-09-10): the approved run stays the run of record;
downstream products catch up to it without discarding progress. Implemented as
an explicit, reviewed exclusion rather than a re-approval:

- `scripts/southern_war_release_gate.py`: `reviewed_input_revisions()` and an
  `accepted_revisions` argument on `require_declared_files()`. A drifted
  declared file passes only when the decision lists an entry with the exact
  declared and current digests and a review record whose hash matches; any
  third byte state, other file, malformed or duplicate entry refuses. Tests:
  `test_reviewed_input_revision_accepts_exact_revised_bytes`,
  `test_input_revision_cannot_widen_into_file_existence` (6 cases),
  `test_input_revision_does_not_cover_a_second_drift`.
- Independent review
  [SOUTHERN_V3_INPUT_REVISION_REVIEW_2026_09_10.md](SOUTHERN_V3_INPUT_REVISION_REVIEW_2026_09_10.md)
  (SHA256 `451ffaf512975ed1e42e63ff599da13b54c2984c675f802162dedcaf5449ef54`):
  PASS. The reviewer re-ran the replay (13/13 identical), hashed all 25
  manifest declarations (only the sqlite drifts), reproduced the ledger, and
  probed the gate's edge cases.
- `SOUTHERN_V3_RELEASE_DECISION.json` gained one `accepted_input_revisions`
  entry bound to that review hash. `model_run_id`, `manifest_sha256`, the
  original review record and every published Southern output are unchanged.

```powershell
& .venv/Scripts/python.exe -m pytest --testmon --testmon-noselect -p no:cacheprovider scripts/tests/test_southern_war_release_gate.py scripts/tests/test_product_stale_input_gates.py -q
```

40 passed in 7.69s, including the live-decision test.

## Step 1 — `alabama_war_v1` rebuilt

```powershell
& .venv/Scripts/python.exe scripts/build_alabama_war_v1.py
```

`AL-WAR-V1-E08D6FCD1A8A49BA6DAD`: 97 races, 194 candidate-cycle rows,
`source_model_run_id = WAR-POST2016-V3-4AF79A70EAA8F39EBD49`, gate passed
before any read. Formula and orientation identities asserted by the builder
(tolerance 1e-9).

## Step 2 — `alabama_historical_war_v1` refused (correct)

```powershell
& .venv/Scripts/python.exe scripts/build_alabama_historical_war_v1.py
```

Gate passed; `apply_published_modern_scores` then failed:
`Mismatched elements: 7 / 97`, max absolute difference 0.079 pp between the
compatibility input `data/processed/war/cmo_v5_races.csv` raw gaps and the
certified `alabama_war_v1` raw gaps. This is the stale-input condition
quantified independently by
[ALABAMA_HISTORICAL_RACE_UNIVERSE_2026_09_10.md](ALABAMA_HISTORICAL_RACE_UNIVERSE_2026_09_10.md):
seven in-universe 2018/2022 races (2018 House 81, 83, Senate 14, 27; 2022
House 32, 68, 92) carry pre-certified totals and 17 2022 races carry stale
incumbency in `canonical_cmo_features.csv`. The prior historical export was
therefore never consistent with the certified warehouse; the new gate and the
builder's own assertion now make that a refusal rather than a silent build.

### Regeneration chain and its blocker

`cmo_v5_races.csv`/`cmo_v5_candidates.csv` derive from
`canonical_cmo_features.csv`/`canonical_cmo_candidates.csv`
(`scripts/rebuild_cmo_candidate_quality_v5.py`), which derive from the
warehouse through `scripts/build_canonical_cmo_features.py`. That builder
refuses before any read (`require_reported_vote_quality`, whole `alabama_sos`
Governor/Attorney General/legislative slice) on the unresolved fractional
Morgan 1994 Attorney General cell (144.4, precinct 26001; see
[MORGAN_1994_FRACTIONAL_CELL_QUARANTINE_2026_09_10.md](MORGAN_1994_FRACTIONAL_CELL_QUARANTINE_2026_09_10.md)).
The historical Alabama WAR, the story page, the ideology page's WAR join and
the forecast bundle are all downstream of this cell until `warehouse-06` has
an owner disposition.

## Consumers now refusing (by design)

- `scripts/build_war_story_page.py`, `scripts/build_democratic_transition_page_v2.py`:
  `require_alabama_historical_release` refuses because the historical export
  declares the pre-rebuild `alabama_war_v1/race_war.csv` and the archived
  Southern run.
- `scripts/build_2026_forecast_dashboard.py`: declared forecast input
  `post2016_southern_war_v3/manifest.json` changed.
- Tests reading those on-disk exports fail for the same reasons:
  `test_ideology_performance_page.py` (11 gate refusals) and
  `test_historical_war_story_page.py::test_grimsley_2018_is_exact_published_race_residual`
  (archived vs approved residual differ by 0.00031). They were not weakened;
  they pass once the historical export is rebuilt from certified inputs.

## Not established

- Historical Alabama WAR on certified totals (blocked as above).
- Forecast bundle on the approved lineage (`run_alabama_war_generic_forecast.py`
  not run; also awaits `forecast-04` polling refresh policy).
- Any numerical impact on the 412 backcast races; the seven modern deltas are
  bounded at 0.079 pp raw gap.
- Publication of any page.

## 2026-09-11 continuation: adjudication, compatibility chain, and a stale-baseline finding

Owner disposition for `warehouse-06` (option A): the Morgan cell was adjudicated
to the provider's reported integer total. Applied as
`RUN-C0A15A7AB6A6403991BB5FE5143BACFF` by
`scripts/repair_morgan_1994_fractional_cell.py` after independent pre-application
review ([MORGAN_1994_ADJUDICATION_REVIEW_2026_09_10.md](MORGAN_1994_ADJUDICATION_REVIEW_2026_09_10.md),
PASS): adjudication `ADJ-1994-MORGAN-26001-AG2-K48` (approved), one
`vote_observations` row 144.4 → 144.0 with before-image and raw workbook hashes,
separate verified backup `pre-morgan-1994-adjudication-2026-09-10.sqlite`.
Post-commit (read-only, against the backup): only that cell, +1 build, +1 QA and
+1 adjudication rows differ; 117 other tables identical; `quick_check` ok; FK 0;
zero fractional observations remain; the compat-feature guard slice passes.

Compatibility chain regenerated in order after a further backup
(`pre-1994-federal-mart-rebuild-2026-09-10.sqlite`):
`build_canonical_geographic_weights.py` (CSV; 2010/2018/2022 weights identical
to the accepted 08-26 file, 2014 drops 26 rows), `build_1994_cmo_baseline.py`
(`RUN-22C8E3AE51C34579A6BCD9A49EF8C700`; 1994 precincts now code-keyed, 7,384 vs
6,441 weight rows), `build_historical_federal_baselines.py`
(`RUN-70A750C82BEC43D686E5F4B1FE13461C`; one code fix: read 1994 precinct keys
as text), `build_canonical_cmo_features.py`, `rebuild_cmo_candidate_quality_v5.py`
(509 races / 1,018 candidates, universe unchanged). Effects on
`canonical_cmo_features.csv`: the 21 certified 2018/2022 vote corrections (7
in-universe margins, max 0.079 pp); 2022 incumbency flags corrected on 101 rows
(17 in-universe); 1994 baselines moved median 0.06 / max 4.4 pp (HD85) from the
identity re-keying; **2002 HD26 baseline moved −4.3 → −24.2 with fallback share
0 → 5.1%**, the Marshall County contest whose conflicting `vote_observations`
sets remain unadjudicated (`warehouse-05`; see the race-universe audit).

The warehouse byte change triggered the v3 gate again; a second scratch replay
again reproduced all 13 approved outputs byte-for-byte (the training frame reads
only `mart_southern_war_training_with_finance`, cycle > 2016, whose materialized
inputs are untouched), independently reviewed
([SOUTHERN_V3_INPUT_REVISION_2_REVIEW_2026_09_10.md](SOUTHERN_V3_INPUT_REVISION_2_REVIEW_2026_09_10.md),
PASS) and recorded by re-pointing the decision's single revision entry
(`e2dbdb9d…`, first revision kept under `superseded_accepted`).

### Historical rebuild refused again — approved v3 Alabama baseline is stale

`build_alabama_historical_war_v1.py` now passes its gates but refuses at the
modern parity assertion: 89/97 raw gaps disagree, max 8.77 pp. Legislative
margins agree 97/97; the disagreement is the same-cycle ticket baseline.
[ALABAMA_TICKET_BASELINE_STALENESS_2026_09_11.json](ALABAMA_TICKET_BASELINE_STALENESS_2026_09_11.json)
records the diagnosis: the approved run's Alabama `baseline_dem_margin` equals
the `federal_index_margin` of the **2026-08-21** federal-baseline build (96/97
exact). Regenerating that baseline from the current warehouse with unchanged
code and byte-identical modern weights changes 131/139 (2018) and 128/140 (2022)
district margins (median 0.19 / 0.05 pp, max 13.4 / 8.8 pp), through allocated
two-party totals, not parsing or coverage. Source rows and nodes are identical
since the 09-07 backup; the change is attributed [INFERENCE] to the accepted
September precinct-identity repairs that post-date the 08-21 mart. No 08-21
warehouse image survives to prove the mechanism.

Consequence: `alabama_war_v1`, the Alabama slice of the published Southern
historical WAR, the prior historical export and the forecast all rest on a
superseded ticket baseline. Retraining v3 with a refreshed Alabama context is a
change to an approved, published model and requires the owner's decision; this
task is blocked on it. Nothing here alters any approved artifact.
