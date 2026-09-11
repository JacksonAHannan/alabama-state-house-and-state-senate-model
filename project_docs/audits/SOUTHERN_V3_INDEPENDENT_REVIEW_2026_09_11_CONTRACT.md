# Independent review: exact Southern v3 run (manifest input-contract re-declaration, 2026-09-11)

Decision: APPROVED FOR DESCRIPTIVE HISTORICAL USE

Applies only to the exact run `WAR-POST2016-V3-530FBD4238CC483E557C` (manifest
SHA256 `c879265a3e09af1fe1dd9793d3da816d6357e26336801a4267063cdbb8596d63`)
built on warehouse run `RUN-504CE4C4DF904D88A5A40D268F3FCEAB`, training-frame
digest `cc9204796781b99a9d2945bf1a2caf9bcd1cba8c3f90d100622c5b162025874b`
(3,660 rows), as a descriptive same-cycle race residual under
`POST2016_SOUTHERN_WAR_V3_FIELD_CONTRACT.md` (SHA256
`ef02716dda09bdfe38258da5047521d46cbb91e057ee103b0c837da0ca35f4d5`). This
approval inherits the scientific review of
`WAR-POST2016-V3-A937708D4E0A5232D3F5`
(`SOUTHERN_V3_INDEPENDENT_REVIEW_2026_09_11.md`, SHA256
`5e4459f981e6c2565c1d7e1e4212f40c1cbe0c35422d94d0c297b92ead384b14`) without
repeating it, and supersedes `WAR-POST2016-V3-A937708D4E0A5232D3F5` (manifest
`714958e7725b6d04454b05b59ecb82bb8cdc5f29976502bd6ffa1a5958831218`) for the
Southern historical WAR route; the superseded run stays preserved byte-for-byte
at `artifacts/war/alabama_dependency_rebuild_20260910/v3_A937708D.pre-contract-change/`
and is not withdrawn as a historical record. The model, its 13 analytical
outputs, diagnostics and configuration are byte-identical to the superseded
run; the only change under review is how the manifest declares the warehouse
input and the release gate that enforces it. It is not predictive validation,
external-reference certification, or publication approval; publication remains
a separate authorization. No source, model, manifest, warehouse row, script,
test or public output was changed by this review; its only write is this file.
`SOUTHERN_V3_RELEASE_DECISION.json` still binds the superseded run and must be
re-bound to this run and this record by its owner before any downstream builder
may treat the decision as approval.

## Scope and independence

Scoped review of the owner-authorized structural fix: the v3 manifest no longer
declares `data/processed/elections/alabama_elections.sqlite` (5.8 GB) by
whole-file hash; it declares `training_frame` = content digest of the one query
the model consumes (`mart_southern_war_training_with_finance`, `cycle > 2016`,
`training_status = strict_war_ready_no_finance`), computed by the new
`scripts/southern_war_training_frame.py`, plus the consumed frame as output
`training_frame.csv`; `southern_war_release_gate.require_declared_training_frame`
recomputes the live digest and refuses on mismatch. Fresh reviewer context;
nothing under review was implemented by this reviewer. HEAD
`720c3507b147bc0a7c048c4c84ab0262920802c1` with the large preserved dirty
working tree; the run bundle, gate, loader, contract and test changes are
unstaged or untracked and were read in place. The warehouse was opened only
with `?mode=ro` and `PRAGMA query_only=ON` (confirmed `1`) through the stdlib
`sqlite3`; the model loader it shares with the gate (`v2.load_training`) also
opens `?mode=ro`. No loader, repair, retrain, builder or sensitivity rerun was
executed; no whole-file warehouse hash was needed or computed. The 2026-09-11
review stands as the scientific standard; none of its acceptance meanings was
weakened or re-opened.

Snapshot (SHA256):

- `data/processed/war/post2016_southern_war_v3/manifest.json`
  `c879265a3e09af1fe1dd9793d3da816d6357e26336801a4267063cdbb8596d63`
- `artifacts/war/alabama_dependency_rebuild_20260910/v3_A937708D.pre-contract-change/manifest.json`
  `714958e7725b6d04454b05b59ecb82bb8cdc5f29976502bd6ffa1a5958831218`
- `artifacts/war/alabama_dependency_rebuild_20260910/v3_contract_change_delta.json`
  `2618b09d910c12071bc84f7e103cca358a05fafe5ce22ca01021838775822928`
- `scripts/southern_war_training_frame.py`
  `9f7d15695959e45f8018fd7dfa5e7b702781eb60dadcd91fa1b91414c5bca2a7`
- `scripts/retrain_post2016_southern_war_v3.py`
  `5cb2cc77953a6ab5b72ef6a9c5f6d021bc6303ea1b737c28cccdd86605048809`
- `scripts/southern_war_release_gate.py`
  `7019f5df58ea526fb6bf08815efee5d24ec0115ca6a2ed654d8569fec447dcb1`
- `scripts/tests/test_post2016_southern_war_v3.py`
  `6dbca6378bdfd97b28c3df9c08a57fa88bd367a3b557495a209a352e55c1a5a9`
- `scripts/tests/test_southern_war_release_gate.py`
  `c345cce2367e85b280188822fe1b0fc9340c3a3d0ab68da44a85fec9cdbe6a21`
- `scripts/tests/test_product_stale_input_gates.py`
  `ee6cac3eaff7fb3b97db8ac426f3d772756e34e0b788fe3906be6126d7543b37`
- `project_docs/model/POST2016_SOUTHERN_WAR_V3_FIELD_CONTRACT.md`
  `ef02716dda09bdfe38258da5047521d46cbb91e057ee103b0c837da0ca35f4d5`
  (HEAD blob = predecessor value `3de27261136fb5574fc7be90b23d599de919c9b8226a2c62772b5936190618dc`)
- `project_docs/model/POST2016_SOUTHERN_WAR_V3.md`
  `d082092462595fc5c62bd7f4436d856e85e6b1a33e302ec707a4d27979aaf152`
- `project_docs/audits/POST2016_SOUTHERN_WAR_V3_VALIDATION.md`
  `67e6ea9d544d37354229fd3ded8d1041e255c7eeb3cc8020b0ae458d20a60f2a`
- `project_docs/audits/SOUTHERN_V3_CONTEXT_SENSITIVITY.md`
  `f22dafec13f525723928fa74c5dd7c41e53f7c4ebc5a58854afd277850dc4fba`
- `data/processed/war/post2016_southern_war_v3_context_sensitivity/summary.json`
  `1184eed9982680339488584c012d12a854eab98fdad28fe66b7fcafb1139224b`
- `project_docs/audits/SOUTHERN_V3_RELEASE_DECISION.json` (still binding the superseded run)
  `3bcfdb114e1b81a26a78bd4e826f5785e4ff07743de6a67f91f7b99ba8974af7`
- `project_docs/audits/SOUTHERN_V3_INDEPENDENT_REVIEW_2026_09_11.md` (inherited review)
  `5e4459f981e6c2565c1d7e1e4212f40c1cbe0c35422d94d0c297b92ead384b14`
- `data/processed/elections/alabama_elections.sqlite` 5,819,064,320 bytes, latest
  `warehouse_build_run` row `RUN-504CE4C4DF904D88A5A40D268F3FCEAB` (not hashed;
  the training frame was compared by content)

## Checks

Each check names what was run and what it returned. All readers were inline
repository-Python (`.venv/Scripts/python.exe -c`, pandas, stdlib `sqlite3`,
`hashlib`) over the files named above; SQL was bounded to
`mart_southern_war_training_with_finance` and `warehouse_build_run`.

1. **Byte identity with the superseded run — pass.** For the 13 CSV outputs
   present in both bundles, SHA256 of each file with the first
   (`model_run_id`) column removed line-by-line: 13/13 identical with equal row
   counts (race_war 3,660; candidate_cycle_war 7,320;
   structural_forward_predictions 31,620; structural_forward_metrics 120;
   validation_cross_fitted_predictions 3,660; structural_coefficients_by_cycle
   204; lag_diagnostics_by_cycle 6; v2_correction_comparison 3,660; coverage
   94; finance_forward_predictions 29,003; finance_forward_metrics 78;
   finance_nested_predictions 2,754; finance_nested_metrics 8). Manifest
   `diagnostics` equal (`==`), `configuration` equal (`==`),
   `warehouse_build_run_id` unchanged (`RUN-504CE4C4DF904D88A5A40D268F3FCEAB`),
   `source_commit`/`warehouse_code_commit` unchanged (`720c3507…`). The four
   unchanged `input_hashes` entries equal the predecessor's; only the contract
   entry moved (`3de27261…` → `ef02716d…`, the new section). The predecessor
   bundle is intact: its manifest hashes to `714958e7…` (the value the 09-11
   review approved) and 13/13 outputs match that manifest's hashes and row
   counts, carrying only `WAR-POST2016-V3-A937708D4E0A5232D3F5`. The two
   regenerated reports differ from the predecessor's only by run ID: replacing
   `530FBD42…` with `A937708D…` in the on-disk bytes reproduces the predecessor
   manifest's report hashes exactly for both documents.
2. **Declarations — pass.** 26/26 declared files match disk: 5/5
   `input_hashes`, 4/4 `code_hashes` (now including
   `scripts/southern_war_training_frame.py`), 14/14 `outputs` (hash and row
   count), 3/3 `reports`. All 14 outputs carry only
   `model_run_id = WAR-POST2016-V3-530FBD4238CC483E557C`. No `input_hashes` key
   contains `sqlite`. `training_frame.sha256` is 64 lowercase hex, `rows` =
   3660, `loader` = `scripts/southern_war_training_frame.py`, `source` names the
   mart, cutoff and status. `training_frame.csv`: 3,660 data rows, 43 columns,
   `model_run_id` first, no `build_run_id`; its
   (state_code, cycle, chamber, district) set equals `race_war.csv`'s with 0
   duplicate keys; all rows have `cycle ≥ 2018` and
   `training_status = strict_war_ready_no_finance`.
3. **Live digest — pass.** (a)
   `southern_war_training_frame.live_training_frame_digest()` on the live
   warehouse returned `cc920479…5874b` and `RUN-504CE4C4…`, equal to the
   manifest's `training_frame.sha256` and `warehouse_build_run_id` (0.2 s).
   (b) Independent implementation: own `?mode=ro` + `query_only=1` connection,
   own SQL (same column list, `ORDER BY war_outcome_id` rather than the loader's
   order), own `.0`-stripping of `district`, `baseline_office_family` via
   `v1.office_family`, then drop `build_run_id`, mergesort by RACE_KEYS,
   `to_csv(index=False, float_format='%.12g', lineterminator='\n')`, SHA256 of
   UTF-8: `cc920479…5874b`, equal to the manifest (3,661 lines, 2,745,489
   bytes). Live frame: 3,660 rows, one build run (`RUN-504CE4C4…`, status
   `validated`, target `southern_war_preparation_no_finance`), which is also
   the latest `warehouse_build_run` row. (c) Independence from the run ID:
   setting every `build_run_id` to `RUN-ALTERED-0000`, dropping the column
   entirely, and shuffling row order all reproduce the declared digest under
   both implementations. Altering one `dem_votes` value by 1 changes the
   digest; a 1e-11 relative perturbation of one `baseline_dem_margin` changes
   it; 1e-12 and 1e-14 do not (Finding 2). (d) `training_frame.csv` equals the
   live frame: identical column order, 0 string mismatches, numeric max |Δ|
   2.9e-11 (CSV read-back rounding); reading the output with
   `float_precision='round_trip'`, dropping `model_run_id` and applying the
   digest rule reproduces `cc920479…5874b` exactly — the declared digest is
   auditable from the output CSV without the warehouse. `race_war.csv`
   `baseline_dem_margin`, `legislative_dem_margin`, D/R votes and
   `war_outcome_id` equal the live frame (max |Δ| 7.1e-15).
4. **Gate semantics — pass; no protection over consumed inputs is lost.**
   `require_declared_training_frame`: returns without touching the warehouse
   when `training_frame` is absent (predecessor manifest: live digest callable
   provably not invoked); refuses `Malformed training_frame declaration` for a
   string, empty dict, `None` or non-hex `sha256`; refuses
   `Declared training frame changed in the warehouse` when the live digest
   differs (exercised against the live warehouse with `sha256 = 0×64`); passes
   on the live manifest against the live warehouse; ignores the returned run ID
   and the `rows` field, so a content-identical preparation rerun under a new
   `warehouse_build_run_id` passes by design. `require_approved_release` calls
   it after the decision/manifest/review binding checks and
   `require_declared_files`; `require_declared_files` on the live manifest
   passes. Every downstream consumer (`build_southern_historical_war_v1`,
   `build_southern_war_map`, `build_alabama_war_v1`,
   `build_alabama_historical_war_v1`) reaches the new check through
   `require_approved_release`; none catches `ReleaseGateError`, so all fail
   closed. What the model reads from the warehouse: exactly `v2.load_training`
   (the training mart query above plus the `warehouse_build_run` row, which
   must be `validated`); `attach_lag_context` and `add_finance_features` read
   only the byte-declared probability panel and Alabama presidential CSVs and
   frame columns; v3 calls no v1 loader and no other `sqlite3` path. The digest
   covers the header (column set), the full row set and every consumed value
   at 12 significant digits; the v2 manifest, probability panel, Alabama context
   files, contract and all four scripts remain byte-declared. What the 09-08
   whole-file hash additionally froze was incidental: tables the model does not
   read (the predecessor's supporting mart/canonical/bridge comparisons are
   evidence about `RUN-504CE4C4…`, which the manifest still records, not model
   inputs), page layout, and metadata fills — the very drift that forced two
   accepted-revision cycles in two days. Loss accepted as the contract states.
5. **Contract and tests — pass.** The new "Manifest input declarations"
   section states: byte-hashed file inputs (matches the 5 `input_hashes`
   keys); warehouse not whole-file hashed (matches); the one query and its
   predicates (matches `load_training`); `training_frame` with `sha256`,
   `source`, `loader`, `rows` alongside `warehouse_build_run_id` (matches);
   digest excludes `build_run_id` and is computed by the named module
   (matches); `training_frame.csv` one row per race, `model_run_id` first
   (matches); gate recomputes and refuses on mismatch, unrelated warehouse
   changes and content-identical reruns pass (matches Check 4). The section
   does not state the 12-significant-digit float serialization (Finding 2).
   `git diff HEAD -- scripts/tests/test_post2016_southern_war_v3.py`:
   `verify_report` still pins the archived 8BB52074 disposition's
   `archived_contract_path` copy to `272c6002…7ae32` (= `record["sha256"]` =
   `recorded_sha256`), still pins `disposition["current_sha256"]` to
   `3de27261…18dc` as a recorded value, still asserts
   `manifest["code_hashes"] == disposition["code_hashes"]`; only the equality
   of the live contract digest with `current_sha256` was dropped (the live-code
   loop removal was already reviewed on 09-11). The masking test still
   parametrises `current_sha256`. `git diff HEAD --
   scripts/retrain_post2016_southern_war_v3.py`: streaming `sha256`, the
   `training_frame_digest(raw)` call, the `training_frame.csv` output, removal
   of `v2.DATABASE` from `input_paths`, the loader added to `code_paths`, and
   the `training_frame` block — no numerical code changed, consistent with
   Check 1. Tests (command below): **56 passed, 1 failed** in 3.35 s; the
   failure is `test_current_v3_release_decision_is_exact_and_enforced` at
   `manifest_sha256` (`714958e7…` bound vs `c879265a…` live), exactly the
   expected pre-binding state; all 4 training-frame gate tests and the 13
   product stale-input gate tests pass.
6. **Sensitivity — pass.** `summary.json` binds `model_run_id`
   `WAR-POST2016-V3-530FBD4238CC483E557C`, `RUN-504CE4C4…`, `manifest.json`
   `c879265a…` and `race_war.csv` `cd0095ad…` (both equal to disk), the three
   model scripts (equal to disk) and the audit script; `parity_gate = passed`
   at max |Δ| 6.484e-14 on all three columns (tolerance 1e-8); median
   expected-gap SE 0.75915, 79.23 % of WAR intervals exclude zero, 63.03 %
   stable party, 2,376 missing-context rows, 1,284 lag rows — identical to the
   predecessor's values (0.759 / 0.792 / 0.630). `SOUTHERN_V3_CONTEXT_SENSITIVITY.md`
   names the new run and manifest hash and no longer names `A937708D`.

## Findings

1. **Release decision not yet re-bound (severity: expected state).**
   `SOUTHERN_V3_RELEASE_DECISION.json` binds `WAR-POST2016-V3-A937708D4E0A5232D3F5`
   / `714958e7…` / the 09-11 review record; the live gate test fails at
   `manifest_sha256` as designed. Re-bind exactly to
   `WAR-POST2016-V3-530FBD4238CC483E557C`, manifest `c879265a3e09af1fe1dd9793d3da816d6357e26336801a4267063cdbb8596d63`,
   warehouse run `RUN-504CE4C4DF904D88A5A40D268F3FCEAB`, this record and its
   SHA256, decision `approved_for_descriptive_historical_use`; move the
   A937708D binding (with its review record, its `supersedes` chain and the
   sqlite `accepted_input_revisions_at_supersession` history) into
   `supersedes` with `archive_path`
   `artifacts/war/alabama_dependency_rebuild_20260910/v3_A937708D.pre-contract-change/`.
   No `accepted_input_revisions` entry is needed or valid for the warehouse
   file: the new manifest does not declare it. Do not edit the run manifest's
   hash-bound `status`.
2. **Digest precision is 12 significant digits, undocumented (severity:
   informational).** `training_frame_digest` serializes floats with
   `float_format='%.12g'`; live float columns carry up to 17 significant
   digits. A change below ~1e-12 relative in any consumed value passes the
   gate (verified: 1e-12 invisible, 1e-11 detected). The effect on any output
   would be far below the 1e-8 parity tolerance already used by the product,
   so this is not a defect, but the contract section describes "a
   deterministic CSV serialization excluding `build_run_id`" without the
   precision. Action: state the 12-significant-digit rule in the contract
   section (or the module docstring the contract cites) in a later,
   documentation-only change; that will move the contract hash and belongs
   with the next run manifest, not this one.
3. **Live-warehouse failures surface as `ValueError`/`sqlite3.OperationalError`,
   not `ReleaseGateError` (severity: informational; fails closed).** The gate
   reuses `v2.load_training`, which raises `ValueError` when the mart holds
   rows from more than one build run or the run is not `validated`, and
   `sqlite3.OperationalError` when the warehouse file is absent. Every consumer
   propagates these, so no unapproved build can proceed; only the error class
   and message differ from the gate's other refusals. Action: optional — wrap
   the loader call in `require_declared_training_frame` and re-raise as
   `ReleaseGateError`, in a separately gated change.
4. **Mixed line-ending hashes across declared files (severity: informational,
   pre-existing class; predecessor Finding 3 generalised).** The contract and
   the three loader/v1/v2 scripts are declared as LF bytes; the two reports,
   the v2 manifest, the probability panel and `retrain_post2016_southern_war_v3.py`
   are declared as CRLF bytes. Under `core.autocrlf=true` a fresh checkout
   turns the LF files CRLF (git already warns for the contract and gate), so
   `require_declared_files` refuses on any fresh checkout regardless of policy.
   Not introduced by this change; record it in the decision's limits or
   normalise the generator in a later, separately gated change.
5. **Predecessor bundle is complete for outputs but not for reports (severity:
   informational).** The preserved A937708D bundle holds the manifest and 13
   outputs, without the two regenerated report documents or an
   `ARCHIVE_NOTE.md` (the 4AF79A70 archive has one). Both report byte streams
   are recoverable exactly from the current documents by run-ID substitution
   (Check 1), so nothing is lost; add a note when the `supersedes` entry is
   written.
6. **Tautological assertion (severity: nit).** In `verify_report`,
   `assert actual != record["sha256"]` follows an early `return` on equality
   and can never fail; it documents intent only.

## Verification and limitations

Repository Python (`.venv/Scripts/python.exe`), inline read-only scripts, and
`pytest -p no:cacheprovider`.

- Identity script over both bundles: 13/13 outputs identical without
  `model_run_id`, equal row counts; `diagnostics`/`configuration` equality;
  predecessor manifest `714958e7…`, 13/13 archived outputs match it.
- Declaration script over the new manifest: 26/26 files match (14 outputs with
  row counts, 3 reports, 5 inputs, 4 code); run-ID purity of all 14 outputs;
  `training_frame.csv` key parity with `race_war.csv`.
- Digest script: `live_training_frame_digest()`; independent SQL
  (`?mode=ro`, `PRAGMA query_only=ON` → `1`) and serialization; run-ID,
  column-drop and order invariance; one-vote and 1e-14…1e-9 perturbation
  sensitivity; round-trip recovery of the digest from `training_frame.csv`.
- Gate script: `require_declared_files` and `require_declared_training_frame`
  on the live manifest against the live warehouse; altered digest, altered
  `rows`, altered `warehouse_build_run_id`, four malformed declarations,
  predecessor manifest without the field.
- Report script: run-ID substitution reproduces the predecessor report hashes;
  line-ending survey of declared files; `git ls-files --eol`; `git show HEAD:`
  contract hash.
- `.venv/Scripts/python.exe -m pytest -p no:cacheprovider
  scripts/tests/test_post2016_southern_war_v3.py
  scripts/tests/test_southern_war_release_gate.py
  scripts/tests/test_product_stale_input_gates.py -q`: **56 passed, 1 failed**
  in 3.35 s; the failure is `test_current_v3_release_decision_is_exact_and_enforced`
  at `manifest_sha256` (expected until re-binding).
- Git: `git rev-parse HEAD`; scoped `git status --porcelain`; `git diff HEAD`
  over the retrain script, the gate, the two test files and the contract.

Not verified: the scientific content of the run (inherited from the 09-11
review by byte identity, Check 1); the warehouse file was not hashed (by
design of the change under review); `require_approved_release` was not run
end-to-end with a decision bound to this run, because writing such a decision
is the owner's act — its constituent checks were exercised individually; the
sensitivity audit was not re-executed (its summary binds this run and equals
the predecessor's recomputed values); no historical builder, map builder,
browser check, publication or full repository suite ran.

## Next bounded work

1. Owner of `SOUTHERN_V3_RELEASE_DECISION.json`: re-bind per Finding 1; then
   show `test_southern_war_release_gate.py` fully passing (the live test will
   then exercise `require_declared_training_frame` against the live
   warehouse).
2. Documentation-only follow-ups (Findings 2, 4, 5) at the next gated
   contract revision; optional error-class tidy-up (Finding 3).
3. Only then: historical builder, map builder, browser and download-parity
   checks, carrying forward the 09-11 review's Alabama-slice disclosure
   requirements unchanged (89 races, max 8.77 pp raw gap; six `war_party`
   label changes now recorded in `v3_retrain_delta.json`; Alabama bootstrap
   widths).

Summary: 6 checks passed; 6 findings, none blocking (one expected pre-binding
gate state, four informational, one nit). The run is the approved model under
a tighter, auditable input declaration; this approval inherits the
predecessor's scientific review and supersedes
`WAR-POST2016-V3-A937708D4E0A5232D3F5`. Publication remains a separate
authorization.
