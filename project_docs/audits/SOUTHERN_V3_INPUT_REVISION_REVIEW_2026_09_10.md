# Southern v3 accepted input revision — independent review (2026-09-10)

Independent, read-only review of the proposed `accepted_input_revisions` mechanism
for the approved Southern v3 release decision and of the evidence offered for one
accepted revision of `data/processed/elections/alabama_elections.sqlite`. The
reviewer (`InputRevisionReview`) did not implement the gate change, the evidence
record, or the scratch replay. Procedure: `project_docs/coordination/AGENT_WORKFLOW.md`
section 5. This file is the review record that the proposed decision entry binds
by SHA256; it must not be edited after the decision is amended.

## Scope and snapshot

- Repository HEAD: `720c3507b147bc0a7c048c4c84ab0262920802c1` (`git rev-parse HEAD`).
  The gate change is uncommitted working-tree state (`git status`: `M scripts/southern_war_release_gate.py`,
  `M scripts/tests/test_southern_war_release_gate.py`, `?? project_docs/audits/SOUTHERN_V3_INPUT_REVISION_2026_09_10.json`).
- Approved run of record: `WAR-POST2016-V3-4AF79A70EAA8F39EBD49`, decision
  `project_docs/audits/SOUTHERN_V3_RELEASE_DECISION.json` (2026-09-08, `approved_for_descriptive_historical_use`).
- Files hashed by the reviewer (streamed, 1 MiB blocks):
  - `data/processed/elections/alabama_elections.sqlite` — `77379bb50124ddbba150581c537765f79ffd48e804a596f6243aef8a0c9e4432`, 5,819,056,128 bytes.
  - `data/processed/war/post2016_southern_war_v3/manifest.json` — `c6c09e19335965380e068c40484437bf460db81add232dc8d7cf78d135a905a6` (equals `manifest_sha256` in the decision).
  - `project_docs/audits/SOUTHERN_V3_INDEPENDENT_REVIEW_2026_09_08.md` — `cd0847259e84592e528d5b1d9784e6db77b1caf52fe5ace8e708bf4f0c0ff9d0` (equals `review_record_sha256` in the decision).
  - `project_docs/audits/SOUTHERN_V3_RELEASE_DECISION.json` — `1b6a5c62cd92987c8004bdf26518c5edb4c5acb73f709207db9b5cd56c331263` (not yet amended; no `accepted_input_revisions` key).
  - `project_docs/audits/SOUTHERN_V3_INPUT_REVISION_2026_09_10.json` — `ab38e81ada16ae58c4e27bf65b48fe2c8f57add1062b19ab18bb86683bf2cc11` (revised text incorporating the recovery-verification finding).
  - `project_docs/audits/WAREHOUSE_RECOVERY_VERIFICATION_2026_09_10.md` — `6fa05ab196b457b5de5978017de0cb49fd3b7e021c0cc63d206cdca992bf039b`.
  - `artifacts/war/alabama_dependency_rebuild_20260910/v3_scratch_replay.py` — `69a2ab47c6c8453642eb00ef378608629900d6f4c069f91a8cc892bbdda5e215`.
  - `data/processed/elections/backups/pre-legacy-source-locators-integer-2026-09-08.sqlite` — `7dc4def8fd96995a7e6c1584f0a5aa7ba97f612663d3a227a549845722a1d0e1`.
- Writes by the reviewer: this file, plus the scratch replay re-run described in
  check 4 (writes only under `artifacts/war/alabama_dependency_rebuild_20260910/v3_scratch/`).
  The warehouse was opened only via `sqlite3.connect('file:...?mode=ro', uri=True)`
  with `PRAGMA query_only=ON`. No pandas loads of warehouse tables.

## Check 1 — gate strictness (code review, tests, edge probes)

Read the full `git diff -- scripts/southern_war_release_gate.py scripts/tests/test_southern_war_release_gate.py`
(+193/-1) and the resulting module. Behaviour confirmed by reading and by probes:

- `reviewed_input_revisions(decision, root)` returns `{(path, declared_sha256): accepted_sha256}`.
  It raises `ReleaseGateError` when `accepted_input_revisions` is not a list (including JSON `null`),
  an entry is not a dict, `path`/`review_record_path` is missing or empty, `declared_sha256`/`accepted_sha256`/`review_record_sha256`
  is not 64 lowercase hex characters, `declared_sha256 == accepted_sha256`, the review record path is absolute
  or resolves outside the root, the review record is missing, its SHA256 differs from `review_record_sha256`,
  or the same `(path, declared_sha256)` appears twice. An absent key yields `{}`.
- `require_declared_files(manifest, root, accepted_revisions)` hashes every declaration in `input_hashes`,
  `code_hashes`, `outputs`, `reports`; a file passes only if its current digest equals the declared digest, or
  `accepted_revisions[(relative, declared)]` equals the current digest exactly. A third byte state, a missing
  file, a revision keyed to another declared digest or another path, and a revision to a different accepted
  digest all still raise. Undrifted files behave exactly as before whether or not a revision is present.
  No environment variable, file-existence, or size/mtime fallback exists in the module (grep for `environ`,
  `getenv`, `exists()`; the only `is_file()` uses are the pre-existing review-record check and the new
  review-record-must-exist check, both of which are followed by a SHA256 comparison).
- `require_approved_release` calls `require_declared_files(manifest, root, reviewed_input_revisions(decision, root))`
  only after the existing schema/manifest/run-id/review-record/decision checks pass; the decision file's
  own bytes are not gate-bound (pre-existing), so amending it does not disturb `manifest_sha256`, `run_id`
  or the original `review_record_sha256` checks.
- `sha256()` now streams 1 MiB blocks; same digest, no whole-file read of the 5.8 GB warehouse.

Commands and results:

```
.venv/Scripts/python.exe -m pytest --testmon --testmon-noselect -p no:cacheprovider scripts/tests/test_southern_war_release_gate.py -q -k "not current_v3"
  -> 20 passed, 1 deselected in 0.62s
.venv/Scripts/python.exe -m pytest --testmon --testmon-noselect -p no:cacheprovider scripts/tests/test_southern_war_release_gate.py -q -k "current_v3"
  -> 1 failed: test_current_v3_release_decision_is_exact_and_enforced
     ReleaseGateError: Declared manifest file changed: data/processed/elections/alabama_elections.sqlite
```

The single failure is by design (decision not yet amended) and its only cause is the warehouse digest:
the reviewer hashed all 25 declarations of the approved manifest (6 inputs, 3 code files, 13 outputs,
3 reports) and only `data/processed/elections/alabama_elections.sqlite` drifts (`8cb49945…` declared,
`77379bb5…` current); every other declared file matches. A temp-directory probe of ten malformed/duplicate/
escaping entries all raised; a valid entry passed; a third byte state and a missing file raised; undrifted
files passed with and without a revision. Calling `require_declared_files` on the live approved manifest with
the mapping `{('data/processed/elections/alabama_elections.sqlite', '8cb49945…'): '77379bb5…'}` passes, and
with any other accepted digest raises — so the amended decision will unblock exactly this byte state and
nothing else.

Observation (not a defect): relative to HEAD the working-tree diff also contains the 2026-09-08 accepted
`require_declared_files` addition and its `test_approval_cannot_hide_changed_declared_files` regressions
(`WAREHOUSE_COMPLETION_REPAIRS_2026_09_08.md`, "Accepted code: declared dependency integrity"); any commit
will carry both changes together. Consumers: `build_alabama_war_v1.py`, `build_southern_historical_war_v1.py`,
`build_southern_war_map.py`, `build_alabama_historical_war_v1.py` (the last also calls `require_declared_files(published, ROOT)`
on the Alabama v1 manifest, which does not declare the warehouse file, so the new parameter is not needed there).

## Check 2 — live digests

- Live warehouse SHA256 (streamed): `77379bb50124ddbba150581c537765f79ffd48e804a596f6243aef8a0c9e4432`,
  5,819,056,128 bytes — equals `declared_input.current_sha256` and `current_size_bytes` in the evidence JSON.
- Approved manifest `input_hashes['data/processed/elections/alabama_elections.sqlite']` =
  `8cb49945d657b0d928dee1bfdaa33d4729c5c8fbda5c51217d1cc55492ba03b5` — equals `declared_sha256`.
- Result: match.

## Check 3 — warehouse build ledger (read-only)

Query: `SELECT * FROM warehouse_build_run WHERE started_at_utc >= '2026-09-08T13:00' ORDER BY started_at_utc`
(124 rows total in the table; `MAX(started_at_utc)` = `2026-09-08T15:37:24.479919+00:00`). Rows returned, in order:

| build_run_id | target | started_at_utc | completed_at_utc | status | code_commit |
|---|---|---|---|---|---|
| RUN-4C2EF8D12CC442D99A516E0D393DE157 | alabama_certified_canonical_total_repair | 13:08:35Z | 13:09:43Z | validated | 88878b97 |
| RUN-92AB8DE353AC47D6AECE3D7767C29FCD | southern_war_preparation_no_finance | 13:16:44Z | 13:18:11Z | validated | 88878b97 |
| RUN-91B2A0C3435548A1B6932613B3073995 | sos_legacy_source_cell_lineage | 15:22:48.115964Z | 15:24:32.777294Z | validated | 720c3507 |
| RUN-55E4997B16DA4330BF6E2EE7A1E5FD36 | shor_manifest_registry_metadata | 15:37:24.479919Z | 15:37:24.496680Z | validated | 720c3507 |

Exactly the two runs `RUN-91B2A0C3…` and `RUN-55E4997B…` follow `RUN-92AB8DE3…` (the v3 fit's own
warehouse run, manifest generated 13:19:42Z); nothing else follows, and the latest row is `RUN-55E4997B…`.
`configuration_json` / `validation_json` scope statements read from the ledger:

- `RUN-91B2A0C3…`: `changed_rows` 228882, `source_rows` 2184861, `before_sha256` `4445e6f9…`,
  `expected_after_sha256`/`after_sha256` `8abac3c2fe94a1fb840993481fe1916bee6fa018177f081363cdcfb63ca33513`,
  `expected_run` `RUN-92AB8DE3…`, proposal `reviewed-integer-proposal.json` (`1ff5f7d6…`), limitations
  "Metadata only. Source facts, source-grain ambiguity and original ingest IDs unchanged. Prior analytical
  outputs not revalidated."
- `RUN-55E4997B…`: `source_file_id` `SRC-3F0ED360408C5AD273F6`, before `{license: null, original_url: null}`,
  after `{license: 'CC0 1.0', original_url: <dataverse URL>}`, `expected_run` `RUN-91B2A0C3…`, limitations
  "Literal URL/license recovery only; retrieval, scope, original ingestion and derived products unchanged."

Cross-check against `WAREHOUSE_COMPLETION_REPAIRS_2026_09_08.md`: the "Resumed source metadata repair"
section records the same 228882 fills, the same full source-table expected-after digest `8abac3c2…` across
2184861 rows, and an independent post-commit verification (source rows equal backup plus the 228882 exact
fills, zero discrepancies; 120 table counts preserved except one build and one QA row; `integrity_check` ok,
`foreign_key_check` clean). The registry paragraph records `RUN-55E4997B…` changing only `access_url`/`license`
for `SRC-3F0ED360…` and the full source digest remaining `8abac3c2…`. The ledger and report agree.

## Check 4 — replay verification (independent recomputation and fresh replay)

Reviewer script (own streaming code, not the driver's): for each CSV, asserted the header's first column is
`model_run_id`, dropped the first field of every line (verified every dropped value matches
`^WAR-POST2016-V3-[0-9A-F]{20}$` and that each file carries exactly one run id), hashed the remainder with
line endings preserved, and counted data rows. Also recomputed the driver-compatible digest (line endings
stripped) to check the recorded values.

Result on the scratch bundle present at review start (`WAR-POST2016-V3-142199F69DF8300F1E20`): all 13 CSVs
equal the approved bundle without the run id, row counts equal (race_war 3660, candidate_cycle_war 7320,
structural_forward_predictions 31620, structural_forward_metrics 120, validation_cross_fitted_predictions 3660,
structural_coefficients_by_cycle 204, lag_diagnostics_by_cycle 6, v2_correction_comparison 3660, coverage 94,
finance_forward_predictions 29003, finance_forward_metrics 78, finance_nested_predictions 2754,
finance_nested_metrics 8), and all 26 recorded `approved_digest`/`scratch_digest` values in `comparison.json`
and the evidence JSON were reproduced exactly.

Manifest comparison (approved vs scratch): `warehouse_build_run_id` (`RUN-92AB8DE3…`), `diagnostics`,
`configuration`, `code_hashes`, `methodology_version`, `warehouse_code_commit`, `status` all equal;
`input_hashes` differ on exactly one key, `data/processed/elections/alabama_elections.sqlite`
(`8cb49945…` -> `77379bb5…`); `source_commit` differs (`88878b97…` vs HEAD `720c3507…`) as expected for a
later git commit with identical code hashes; `generated_at_utc` differs.

Fresh replay: the reviewer re-ran `.venv/Scripts/python.exe artifacts/war/alabama_dependency_rebuild_20260910/v3_scratch_replay.py`
(`model_run_id` is a deterministic hash of `run_basis`, so the re-run reproduces the same scratch id).
Output: `scratch_run_id` `WAR-POST2016-V3-142199F69DF8300F1E20`, `input_hash_differences` = [sqlite],
`code_hash_differences` = [], `diagnostics_equal` true, `configuration_equal` true,
`all_outputs_identical_without_run_id` true, 13/13 identical, `elapsed_seconds` 22.6 (warm cache). The
reviewer's own digest pass on the fresh outputs again shows 13/13 equal, and the fresh `comparison.json`
`outputs` array equals the evidence JSON's `outputs` array exactly. The fresh scratch manifest's warehouse
input hash is `77379bb5…`, tying the replay to the exact digest being accepted.

Side effect to disclose: the re-run rewrote `v3_scratch/comparison.json`, the scratch manifest
(`generated_at_utc` now `2026-09-11T03:58:01Z`) and the scratch CSVs/reports with identical content;
`comparison.json.elapsed_seconds` is now 22.6 whereas the evidence JSON records 120.3 from the original run.

## Check 5 — byte-lineage limitation

Reviewer measurements: `pre-legacy-source-locators-integer-2026-09-08.sqlite` SHA256
`7dc4def8fd96995a7e6c1584f0a5aa7ba97f612663d3a227a549845722a1d0e1` (matches the evidence JSON). SQLite
header fields read directly from the files:

| file | size | pages | file_change_counter | schema cookie | mtime (local) |
|---|---:|---:|---:|---:|---|
| alabama_elections.sqlite (live) | 5,819,056,128 | 1,420,668 | 904 | 589 | 2026-09-08 10:38:30 |
| pre-legacy-source-locators-2026-09-08.sqlite | 5,799,350,272 | 1,415,857 | 1 | 1 | 10:10:47 |
| pre-legacy-source-locators-integer-2026-09-08.sqlite | 5,799,350,272 | 1,415,857 | 1 | 1 | 10:19:38 |
| pre-shor-registry-metadata-2026-09-08.sqlite | 5,819,052,032 | 1,420,667 | 1 | 1 | 10:35:05 |

All three backup-writing code paths use `Connection.backup()` (`scripts/repair_sos_cell_lineage.py:177,289`,
`scripts/sync_warehouse_source_registry.py:183,332`). Every backup carries schema cookie 1 and change counter 1,
which is what the SQLite online-backup API produces for a fresh destination regardless of content, while the
live file carries 589/904. This independently corroborates `WAREHOUSE_RECOVERY_VERIFICATION_2026_09_10.md`
section 4 (cookie 1 vs 589, identical `sqlite_master` content, control experiment) and the revised
`byte_lineage_limitation` text: no backup-API image can byte-match the live file, so the absence of a backup
hashing `8cb49945…` is expected and carries no evidential weight against the declared digest. The page-count
deltas are also consistent with the recorded scope (+4,811 pages for the 228,882-row five-field fill; +1 page
for the one-row registry update).

Assessment: the gap is adequately disclosed. The evidence JSON states the limitation, cites the mechanism and
the audit that reproduced it, and lists what is not established (`not_established`: publication, downstream
product validity, row-level equality beyond the recorded transactional checks). The earlier "plausible
checkpoint" wording has been replaced by an explained mechanism; the recovery audit's own "does NOT establish"
bullet still calls the `8cb49945…` mismatch "open" while deferring to the evidence JSON, which is now the
better-supported statement.

Does logical equivalence suffice for a descriptive historical release decision? Yes, for this decision.
The approval covers a descriptive same-cycle race residual identified by `model_run_id`, whose 13 declared
outputs are byte-unchanged and whose consumers read those outputs, not the warehouse. The relevant invariant
for "the approved run stays the run of record" is that the accepted input bytes reproduce the approved
numbers under the approved code and configuration; the replay against `77379bb5…` demonstrates exactly that,
with identical diagnostics, configuration, code hashes and warehouse build run, and the ledger shows only two
metadata-only runs with transactional before/after source digests and independent post-commit verification
in between. Byte lineage would add nothing to this claim beyond what the header analysis already explains,
and the gate re-blocks on any further byte change. What the replay does not prove — row-level warehouse
equality for consumers other than the v3 fit, and downstream product validity — is correctly left in
`not_established` and is not needed for this decision.

## Check 6 — governance

- `model_run_id` `WAR-POST2016-V3-4AF79A70EAA8F39EBD49`, `manifest_sha256` `c6c09e19…`, and the original
  review record (`cd084725…`) are unchanged; `git status`/`git diff --stat HEAD` show no modification to
  `SOUTHERN_V3_RELEASE_DECISION.json`, `SOUTHERN_V3_INDEPENDENT_REVIEW_2026_09_08.md`,
  `data/processed/war/post2016_southern_war_v3/`, or `docs/southern*` / `docs/data/southern*`.
- The proposal adds a key to the decision file that the gate reads only for the exact (path, declared,
  accepted, review-record hash) tuple; the approval string, run id and manifest binding are untouched.
- The owner's authorization is quoted in the evidence JSON (`authorization`: "Owner instruction 2026-09-10:
  the rebuilt Southern WAR run is satisfactory and remains the run to use; downstream products are to catch up
  to it without discarding progress. Publication of docs/ remains a separate authorization.").
- Publication is not implied: `not_established` lists "publication approval" first, and the decision's
  `limits` text ("not … publication approval; downstream builders must still pass their own gates") is unchanged.

## Findings

1. **(Info, P3) Evidence JSON `elapsed_seconds` now differs from `comparison.json`.** Caused by this review's
   fresh replay (22.6 s vs the recorded 120.3 s); all other fields including the 13 digest pairs are identical.
   Either leave as is (the evidence JSON records the original run) or update the one number. No effect on the gate.
2. **(Info, P3) `WAREHOUSE_COMPLETION_REPAIRS_2026_09_08.md` line 250–251 labels `4445e6f9…` as the SHA256 of
   `pre-legacy-source-locators-2026-09-08.sqlite`.** That value is the full source-table digest recorded as
   `before_sha256` in `RUN-91B2A0C3…`; the file's SHA256 is `7dc4def8…`. Pre-existing wording, not introduced by
   this proposal; worth a one-line clarification so future byte-lineage readers are not misled.
3. **(Info, P3) Unused revision entries are silently ignored.** An `accepted_input_revisions` entry whose
   `(path, declared_sha256)` is not declared in the manifest neither raises nor widens acceptance; a typo in
   `path` surfaces only as the ordinary "Declared manifest file changed" refusal. Acceptable strictness-wise;
   noted for operators.
4. **(Info) Commit boundary.** The working-tree diff bundles the 2026-09-08 accepted declared-file guard with
   this revision mechanism; the commit message/changelog should name both.

No defect was found in the gate logic, the evidence, or the replay. No finding blocks acceptance.

## Verdict

Verdict: PASS — the accepted input revision for data/processed/elections/alabama_elections.sqlite (8cb49945… -> 77379bb5…) is supported by the reproduced replay and ledger evidence.

The decision entry may be added with `path` `data/processed/elections/alabama_elections.sqlite`,
`declared_sha256` `8cb49945d657b0d928dee1bfdaa33d4729c5c8fbda5c51217d1cc55492ba03b5`, `accepted_sha256`
`77379bb50124ddbba150581c537765f79ffd48e804a596f6243aef8a0c9e4432`, `review_record_path`
`project_docs/audits/SOUTHERN_V3_INPUT_REVISION_REVIEW_2026_09_10.md` and `review_record_sha256` equal to this
file's final SHA256. After amendment, `test_current_v3_release_decision_is_exact_and_enforced` is expected to
pass (only the warehouse declaration drifts, and the mapping was shown to pass on the live manifest).

## Remaining limitations

- This is file-integrity and reproduction acceptance for one input revision of one approved run. It is not
  renewed scientific acceptance, not publication approval, and not validation of any downstream Alabama,
  forecast, or ideology product; those must rebuild and pass their own gates (`build_alabama_war_v1.py` currently
  derives from the superseded `WAR-POST2016-V3-8BB52074EC806C5BF6BF`).
- Row-level equality of the live warehouse with its 2026-09-08 pre-metadata state was not recomputed here;
  it rests on the recorded transactional digests and the independent post-commit verification cited above.
- The replay proves equivalence for the v3 code path only. Other whole-database byte-hash consumers still need
  their own freshness review, as the 2026-09-08 report already states.
- Any future byte change to the warehouse re-blocks the gate and would require a new reviewed entry; this
  mechanism must not be used to accumulate unreviewed drift.
- Tests ran with `--testmon --testmon-noselect`; no full repository suite ran for this review.
