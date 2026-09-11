# Independent review: exact Southern v3 run (retrained 2026-09-11 on refreshed Alabama baseline)

Decision: APPROVED FOR DESCRIPTIVE HISTORICAL USE

Applies only to the exact run `WAR-POST2016-V3-A937708D4E0A5232D3F5` (manifest
SHA256 `714958e7725b6d04454b05b59ecb82bb8cdc5f29976502bd6ffa1a5958831218`)
built on warehouse run `RUN-504CE4C4DF904D88A5A40D268F3FCEAB` (warehouse file
SHA256 `5d61aff3cb3f1fcbb459df61721f8366fe150b0058e5d037b20f2a441c1400a5`), as a
descriptive same-cycle race residual under
`POST2016_SOUTHERN_WAR_V3_FIELD_CONTRACT.md` (SHA256
`3de27261136fb5574fc7be90b23d599de919c9b8226a2c62772b5936190618dc`). This
approval supersedes `WAR-POST2016-V3-4AF79A70EAA8F39EBD49` (manifest
`c6c09e19335965380e068c40484437bf460db81add232dc8d7cf78d135a905a6`, approved
2026-09-08) for the Southern historical WAR route; the superseded run stays
archived byte-for-byte and is not withdrawn as a historical record. It is not
predictive validation, external-reference certification, or publication
approval; publication remains a separate authorization. No source, model,
manifest, warehouse row or public output was changed by this review; its only
write is this file. `SOUTHERN_V3_RELEASE_DECISION.json` still binds the
superseded run and must be re-bound to this run and this record by its owner
before any downstream builder may treat the decision as approval.

## Scope and independence

Task `SOUTHERN-V3-INDEPENDENT-REVIEW-20260911`, role `validation_release`,
fresh reviewer context; nothing under review was implemented by this reviewer.
HEAD `720c3507b147bc0a7c048c4c84ab0262920802c1` with the large preserved dirty
working tree; the run bundle, docs, script and test changes are unstaged, the
archive and sensitivity directories untracked, all read in place. The warehouse
and the pre-refresh backup were opened only with `?mode=ro` and
`PRAGMA query_only=ON` (confirmed `1`) through the stdlib `sqlite3`, one process
at a time; the 5.8 GB warehouse was hashed by streaming. No loader, repair,
retrain, builder or sensitivity rerun was executed. The 2026-09-08 review record
was used as the check standard and none of its acceptance meanings was
weakened; settled dispositions (v4 deferral, finance exclusion, Virginia
baseline retention, Alabama certified-canvass bridge) were not reopened and no
new evidence against them was found.

Snapshot (SHA256):

- `data/processed/war/post2016_southern_war_v3/manifest.json`
  `714958e7725b6d04454b05b59ecb82bb8cdc5f29976502bd6ffa1a5958831218`
- archived `.../post2016_southern_war_v3_archive/WAR-POST2016-V3-4AF79A70EAA8F39EBD49/manifest.json`
  `c6c09e19335965380e068c40484437bf460db81add232dc8d7cf78d135a905a6`
- `data/processed/elections/alabama_elections.sqlite` (5,819,064,320 bytes)
  `5d61aff3cb3f1fcbb459df61721f8366fe150b0058e5d037b20f2a441c1400a5`
- `scripts/retrain_post2016_southern_war_v3.py`
  `f6222c60bf0289fdd19e0d8fe8bc041bd0f4e7d61b4ebe95ff70a2aa05131b57`
- `scripts/tests/test_post2016_southern_war_v3.py`
  `067458610777b7e317b1d5846796395f1310223b4d7080d17e0968cb3c4c50bf`
- `artifacts/war/alabama_dependency_rebuild_20260910/v3_retrain_delta.json`
  `8342be1308369b73b94f04eff8755d370ec4326fc9504da0fc3e532511e70a41`
- `project_docs/audits/ALABAMA_TICKET_BASELINE_STALENESS_2026_09_11.json`
  `41158dc04d74ecd993c2944861a376c615b6dd8dd3a137621a9829bed3c23b75`
- `project_docs/audits/SOUTHERN_V3_RETRAIN_2026_09_11.md`
  `c00bb6e7dde22e267088cbd65d43654808f933cecf09e227bcbac0d455f2f01a`
- `project_docs/audits/SOUTHERN_V3_CONTEXT_SENSITIVITY.md`
  `f6d17de6c88da11ded70a66e8be04093cb76bfe11787eafb0378bf22464e2deb`
- `data/processed/war/post2016_southern_war_v3_context_sensitivity/summary.json`
  `9d60a54f9a781a7f465f6c5a3a023c9679793d6f1ab2f740863a96a5884a086c`
- `artifacts/war/alabama_dependency_rebuild_20260910/SOUTHERN_V3_CONTEXT_SENSITIVITY.4AF79A70.md`
  `eb2359f0639eb9e800ef2d82ee7ee37d98feb36f523cf5c5757f5032daf70bea`
- `project_docs/audits/SOUTHERN_V3_RELEASE_DECISION.json` (still binding the superseded run)
  `ab2b9c4515581a8af61c1938287c0957dc6fbff95bba6f9a8a6fe5fd0d38349d`
- working-tree `data/processed/elections/historical_federal_district_baselines.csv`
  `c0f3ed99a41ffe98d8aec1263cd931e2a9173fbd75840cfe4151b39c05ee5079`
- `data/processed/elections/backups/pre-southern-preparation-refresh-2026-09-11.sqlite`
  5,819,064,320 bytes, latest run `RUN-70A750C82BEC43D686E5F4B1FE13461C` (not hashed; contents compared)

## Checks

Each check names what was run and what it returned. All readers were inline
repository-Python scripts over the files named above; SQL was bounded to the
tables named.

1. **Manifest integrity — pass.** Streamed SHA256 of every declared file in
   the new manifest: 5/5 non-database `input_hashes`, 3/3 `code_hashes`, 13/13
   `outputs` (hash and row count), 3/3 `reports` match; all 13 outputs carry
   only `model_run_id = WAR-POST2016-V3-A937708D4E0A5232D3F5`; the full
   warehouse file hashes to the declared `5d61aff3…00a5`. `warehouse_build_run`
   (`ORDER BY rowid DESC`): the latest row is
   `RUN-504CE4C4DF904D88A5A40D268F3FCEAB`, target
   `southern_war_preparation_no_finance`, status `validated`, code commit
   `720c3507…`, completed `2026-09-11T05:25:44Z`; its `validation_json` reports
   4,582 model-valid outcomes, 4,280 strict / 302 research, 116/116 scheduled
   slices, 0 missing baseline/context/incumbency, 8,085 context rows. The
   preceding rows are the federal-baseline rebuild `RUN-70A750C8…`, the 1994
   CMO baseline `RUN-22C8E3AE…` and the Morgan adjudication `RUN-C0A15A7A…`,
   as the execution record states.
2. **Archive integrity — pass.** The 4AF79A70 archive holds `manifest.json`,
   the 13 output CSVs and `ARCHIVE_NOTE.md`. Archived manifest SHA256 =
   `c6c09e19…5a6` (the value bound by the current decision); 13/13 archived
   outputs match the archived manifest's hashes and row counts and carry only
   the 4AF79A70 run ID. The two regenerated report documents are not in the
   archive; the archived manifest's report hashes (`f1db2255…`, `ea2b95d5…`)
   equal the SHA256 of the HEAD blobs of `POST2016_SOUTHERN_WAR_V3.md` and
   `POST2016_SOUTHERN_WAR_V3_VALIDATION.md` with LF→CRLF applied (the generator
   writes CRLF on this host; git stores LF under `core.autocrlf=true`), so the
   approved run's report bytes remain recoverable from HEAD (see Finding 3).
3. **Delta reproduction — pass, expectations met.** Joined archived vs new
   `race_war.csv` on (state_code, cycle, chamber, district): 3,660 rows both
   sides, key sets identical, no duplicates. `raw_gap` differs (>1e-9) for
   exactly 89 rows, all `AL`, max |Δ| 8.7725 pp; non-AL `raw_gap` max |Δ| 0.0.
   `baseline_dem_margin` differs for the same 89 AL rows only.
   `legislative_dem_margin` identical for all 3,660 (max |Δ| 0.0), so the input
   change is baseline-only. `fitted_structural_expected_gap` moved for 1,786
   rows (97 AL, max 3.7158 pp; 1,689 non-AL across AR/FL/GA/KY/MO/NC/OK/SC/TN/TX,
   max 0.4510 pp — AR 2022 HD62); `war` moved for the same 1,786 rows (AL max
   5.0567 pp at 2022 HD82; non-AL max 0.4510 pp). Other changed columns are the
   baseline-derived `direct_overperformance`, `lag_current_ticket_change`,
   `lag_change_x_years` (89 AL rows each), `war_magnitude` (1,786), the
   cross-fitted validation fields (refit), and `war_party` for 6 rows (Finding
   1). Identities on the new run: `legislative_dem_margin = 100·(D−R)/(D+R)`,
   `raw_gap = legislative_dem_margin − baseline_dem_margin`,
   `war = raw_gap − fitted_structural_expected_gap`, `war_magnitude = |war|` all
   with max error 0.0; `war_party` D/R/EVEN rule 0 violations; 7,320
   candidate-cycle rows = exactly one D and one R per race (0 duplicate
   race×party keys), `candidate_cycle_war = +war` for D and `−war` for R with
   max error 0.0, `score_identification = race_differential_party_orientation`
   throughout; no pooled candidate columns exist.
4. **Training-frame provenance — pass.** Live
   `mart_southern_war_training_with_finance` (`cycle > 2016`,
   `strict_war_ready_no_finance`): 3,660 rows, one build run
   (`RUN-504CE4C4…`), key set equal to the run; `baseline_dem_margin`,
   `legislative_dem_margin`, D/R votes and `war_outcome_id` equal the run's for
   all 3,660 (max diff 0.0). Backup `pre-southern-preparation-refresh-2026-09-11`
   (`mode=ro`, latest run `RUN-70A750C8…`): same 3,660 keys under
   `RUN-92AB8DE3…`; all-column comparison excluding `build_run_id` differs only
   in `baseline_dem_margin` and its derivative `direct_overperformance` for 89 AL
   rows. `mart_southern_war_context_feature`: 8,085 rows both sides, differs
   only in `baseline_dem_margin` for 89 AL rows. `mart_southern_war_outcome`:
   4,582 rows both sides, no column differs apart from `build_run_id`. Alabama
   legislative totals: all 97 AL run rows equal `canonical_candidates`
   D/R `canonical_votes` (spot rows 2018 HD81 4,697/12,823; HD83 8,943/5,143;
   2022 HD68 9,537/8,981; HD92 1,795/11,812; also HD47 2018, HD82 2022), and the
   377-row certified bridge has 0 canonical/certified disagreements. Excluded
   post-2016 rows remain 302 `research_war_ready_no_finance`.
5. **Baseline correctness — pass; the refreshed baseline is the one consistent
   with the accepted warehouse identity state.** (a) The archived run's 97 AL
   `baseline_dem_margin` values equal `federal_index_margin` in
   `git show HEAD:data/processed/elections/historical_federal_district_baselines.csv`
   (2026-08-21 build) for 96/97 rows; the 97th (2018 HD62) is the recorded
   `same_cycle_state_fallback` (federal contested coverage 0.112), unchanged in
   both runs. (b) The new run's AL baselines equal the live
   `mart_historical_federal_district_baseline` (rebuilt by `RUN-70A750C8…` on
   2026-09-11) for 96/97 rows, same fallback exception; the working-tree CSV
   equals the mart on all 279 2018/2022 rows. The archived run matches the live
   mart on only 7/97, the new run matches the 08-21 CSV on only 7/97 — the
   staleness finding is reproduced. (c) Statewide allocated two-party totals
   are equal old vs new: 2018 US House 1,468,457.0; 2022 US House 966,108.0
   and US Senate 1,378,900.0; `contested_federal_votes` equal in every
   cycle/chamber; row counts equal (2018: 104 house/35 senate; 2022: 105/35).
   The only statewide movement is −35.19 votes in `all_federal_major_votes`
   over the 2018 house rows (a coverage denominator, not a baseline input).
   The federal-baseline builder differs from HEAD only in reading 1994
   precinct keys as text (`historical_weights`, cycle 1994 branch), which cannot
   touch 2018/2022. `RUN-70A750C8…` is one of the warehouse runs the live
   decision explicitly accepted (`accepted_input_revisions`, review verdict
   `pass`), so the baseline now consumed is the one derived from the accepted
   post-repair identity state, and the superseded run's Alabama raw gaps were
   computed against a pre-repair allocation.
6. **Specification and selection — pass, unchanged.** Manifest:
   `selected_structural_specification = decaying_lag`, alpha 100.0,
   `passes_lag_added_value_gate`, selected forward MAE 4.7958 (archive 4.8054),
   best no-lag 5.0998 (archive 5.1105), improvement 0.3040 (archive 0.3051);
   `finance_headline_included = false`, `candidate_pooling_in_headline_war =
   false`, `headline_fit_scope = same_cycle_full_sample_descriptive`.
   Reproduced from `structural_forward_metrics.csv`: over the 937
   lag-context-available aggregate, `decaying_lag/100` (4.7958) is the argmin
   ahead of `constant_lag/100` (4.8025) and `fundamentals_no_lag/100` (5.0998);
   all 96 fold rows satisfy `train_max_cycle < evaluation_cycle`; per-cycle
   MAEs move by ≤0.008 vs the archive. Finance nested gate still fails (5.6394
   vs 5.6191 without finance).
7. **Sensitivity — pass.** `summary.json` binds `model_run_id`
   `WAR-POST2016-V3-A937708D4E0A5232D3F5`, `RUN-504CE4C4…`, manifest
   `714958e7…` and `race_war.csv` `e1c1ed68…`; parity gate passed at
   6.484e-14 on all three columns. Recomputed from the by-race files (3,660
   rows each, all bound to the run): median expected-gap SE 0.7591, 79.23% of
   WAR intervals exclude zero, 63.03% stable party (prior report: 0.759 /
   0.792 / 0.630); 2,376 missing-context rows with exactly zero lag component;
   missing-context no-lag MAE 0.3340 (max 3.95), sign-change share 0.0181
   (prior 0.3321 / 0.0181). Alabama (97 races, all lag-available): median SE
   1.295 (prior 1.344), median interval width 4.24 (4.39), 67.0% exclude zero
   (66.0%), 49.5% stable party (48.5%) — marginally tighter, still the widest
   state; AL no-lag-spec MAE 1.99 and lag-available-fit MAE 1.87 (lag terms
   matter for Alabama by design).
8. **Code and test change — pass.** `git diff HEAD --
   scripts/retrain_post2016_southern_war_v3.py`: the only hunk replaces
   `hashlib.sha256(path.read_bytes())` with a 1 MiB streaming loop in
   `sha256()`; no numerical code changed; the working-tree file hashes to the
   manifest's `f6222c60…`. `git diff HEAD --
   scripts/tests/test_post2016_southern_war_v3.py`: `verify_report` drops the
   loop asserting live script digests equal the 8BB52074 disposition's code
   hashes and keeps `manifest["code_hashes"] == disposition["code_hashes"]`
   against the archived 8BB52074 manifest (plus a two-line comment). The
   parametrised `code_hashes` masking test still raises. Tests (see below): 44
   passed, 1 failed — the live gate binding, as designed.
9. **Documentation — pass.** `POST2016_SOUTHERN_WAR_V3.md` and
   `POST2016_SOUTHERN_WAR_V3_VALIDATION.md` name the new run (and
   `RUN-504CE4C4…`); their diffs against HEAD are only the run IDs, the
   Grimsley example (AL 2018 HD85: raw 18.737, fit 5.384, WAR 13.353 — matches
   `race_war.csv`) and the mean absolute fitted lag (4.113 / 1.977 —
   recomputed exactly over 347 / 335 lag rows). The field contract hashes to
   `3de27261…` = the manifest's report and input entry; the other two report
   hashes match disk.
10. **Standards — pass.** Same acceptance meanings as the 09-08 review:
    descriptive same-cycle race residual (`headline_fit_scope`, cross-fitted
    fields remain separate validation columns); not predictive validation; not
    external-reference certification. Product-wide disclosed limitations carry
    forward unchanged: `geography_vintage = provider-reported; plan vintage
    unverified`; certified canvass sets `validation_status = review`; canvass
    redistribution terms remain `review` (publication/raw-commit concern);
    Louisiana and odd-year uncertainty. **Regression versus the approved run:**
    none in specification, gates, identities, orientation, units, universe
    (3,660 / 302), lineage fields, incumbency, lag context, candidate names or
    votes; the value changes are the intended Alabama baseline correction plus
    its pooled-fit spillover (≤0.451 pp outside Alabama). The Alabama-slice
    consequence is material for a small set of races (2022 HD82 −8.77 pp raw
    gap; 2018 HD47 −4.70 pp) and must be disclosed by downstream builders when
    they replace the published slice.

## Findings

1. **Undisclosed `war_party` label changes (severity: low; disclosure, not a
   defect).** Six races change D/R label between the approved and new run:
   AL 2018 HD47 (D +3.749 → R −0.001), AL 2018 HD66 (+0.016 → −0.063), AL 2018
   HD99 (−0.332 → +0.589), AL 2022 HD26 (−0.075 → +0.068), GA 2018 HD147
   (+0.003 → −0.008), TX 2018 SD14 (+0.027 → −0.007). Five are near-zero WAR
   values crossing zero; HD47 is a genuine consequence of its baseline moving
   −15.90 → −11.20. Neither `SOUTHERN_V3_RETRAIN_2026_09_11.md` nor
   `v3_retrain_delta.json` records label changes. Action: add the count and
   list to the delta record before the historical/map builders replace the
   published slice.
2. **Release decision not yet re-bound; stale revision block (severity:
   expected state).** `SOUTHERN_V3_RELEASE_DECISION.json` binds the superseded
   run; `test_current_v3_release_decision_is_exact_and_enforced` fails at
   `manifest_sha256` (`c6c09e19…` vs `714958e7…`). When re-binding, the
   `accepted_input_revisions` entry (declared `8cb49945…` → accepted
   `e2dbdb9d…`) belongs to the superseded run and must not be carried into the
   new binding: the new manifest declares the current warehouse bytes
   (`5d61aff3…`) directly. Do not edit the run manifest's hash-bound `status`.
3. **Report hashes are CRLF-byte hashes (severity: informational,
   pre-existing).** Both the archived and the new manifest register
   `POST2016_SOUTHERN_WAR_V3.md` / `..._VALIDATION.md` as written on this host
   (CRLF); git stores LF. A checkout that does not restore CRLF will make the
   release gate's report check refuse. Not introduced by this retrain; record
   it in the decision's limits or normalise the generator in a later, separately
   gated change.
4. **Alabama remains the widest-uncertainty state (severity: disclosure).**
   Median expected-gap SE 1.295 vs 0.759 panel; 49.5% of Alabama races keep
   their D/R label in every bootstrap draw. Downstream Alabama-facing
   presentation must surface this, as the 09-08 review already required.
5. **Coverage-denominator drift (severity: informational).** The 2018
   house-row sum of `all_federal_major_votes` moved by −35.19 votes while every
   two-party allocated total is identical; `federal_contested_coverage` changed
   for 95 of 279 2018/2022 rows by ≤0.026. No Alabama race crossed the fallback
   rule (minimum coverage among the 96 federal-baseline races is 0.536; the
   single fallback, 2018 HD62, is unchanged).

## Verification and limitations

Repository Python (`.venv/Scripts/python.exe`), inline read-only scripts, and
`pytest -p no:cacheprovider`.

- Hash/identity script over the new manifest: 24/24 declared files match
  (13 outputs with row counts, 3 reports, 5 inputs, 3 code); streamed
  warehouse SHA256 matches. Archive script: 13/13 outputs, manifest
  `c6c09e19…`.
- Warehouse (`?mode=ro`, `query_only=1`): `warehouse_build_run` tail;
  training-view, context-feature and outcome-mart comparisons against the
  backup; `canonical_candidates` and bridge checks as stated.
- Delta/identity/orientation script over both `race_war.csv` files and the new
  `candidate_cycle_war.csv`; selection script over both
  `structural_forward_metrics.csv`; sensitivity recomputation over the two
  by-race CSVs; baseline script over `git show HEAD:…baselines.csv`, the
  working-tree CSV and `mart_historical_federal_district_baseline`.
- `pytest -p no:cacheprovider scripts/tests/test_post2016_southern_war_v3.py
  scripts/tests/test_southern_war_preparation_warehouse.py
  scripts/tests/test_southern_war_release_gate.py -q`: **44 passed, 1 failed,
  1 warning** in 98 s — collected 15 + 9 + 21; the failure is
  `test_current_v3_release_decision_is_exact_and_enforced` at the stale
  `manifest_sha256` (expected until re-binding); the warning is the
  pre-existing pandas `FutureWarning` in the preparation-warehouse test.
- Git: `git rev-parse HEAD`; scoped `git status --porcelain`; `git diff HEAD`
  over the two changed files, the two regenerated docs, the decision file and
  the federal-baseline builder.

Not verified: the sensitivity audit was not re-executed (its committed outputs
were recomputed from the by-race files, and the script's hash is recorded in
`summary.json`); the backup warehouse was compared by contents, not hashed; the
federal-baseline allocation itself (precinct-to-district weights and
observation matching) was not re-derived — this review establishes that the
run consumes the mart the accepted identity state produced, not that the mart
is correct; the canvass PDFs were not re-parsed; no non-Alabama input changed
and none was re-validated; the intermediate compat chain
(`cmo_v5_races.csv`) was not inspected beyond the training-frame endpoint; no
full repository suite, historical builder, map builder, browser check or
publication ran.

## Next bounded work

1. Owner of `SOUTHERN_V3_RELEASE_DECISION.json`: re-bind exactly to
   `WAR-POST2016-V3-A937708D4E0A5232D3F5`, manifest
   `714958e7725b6d04454b05b59ecb82bb8cdc5f29976502bd6ffa1a5958831218`,
   warehouse run `RUN-504CE4C4DF904D88A5A40D268F3FCEAB`, this record and its
   SHA256, decision `approved_for_descriptive_historical_use`, moving the
   4AF79A70 binding (with its archive path and accepted-revision history) into
   `supersedes`; then show `test_southern_war_release_gate.py` at 21 passed.
2. Add the six `war_party` label changes to the retrain delta record.
3. Only then: historical builder, map builder, browser and download-parity
   checks, with Alabama-slice disclosure of the baseline correction (89 races,
   max 8.77 pp raw gap) and the Alabama bootstrap widths; the published
   Southern slice for Alabama is superseded, not merely refreshed.

Summary: 10 checks passed; 5 findings, none blocking (one disclosure gap to
close in the delta record, one expected pre-binding gate state, three
informational). Regression versus the approved run is confined to the intended
Alabama baseline correction and its bounded pooled-fit spillover.
