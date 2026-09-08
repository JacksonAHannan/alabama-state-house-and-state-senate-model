# Independent review: exact Southern v3 run (retrained 2026-09-08)

Decision: **APPROVED FOR DESCRIPTIVE HISTORICAL USE**. Applies only to the exact
run `WAR-POST2016-V3-4AF79A70EAA8F39EBD49` (manifest SHA256
`c6c09e19335965380e068c40484437bf460db81add232dc8d7cf78d135a905a6`) built on
warehouse run `RUN-92AB8DE353AC47D6AECE3D7767C29FCD`, as a descriptive same-cycle
race residual under `POST2016_SOUTHERN_WAR_V3_FIELD_CONTRACT.md` (SHA256
`3de27261136fb5574fc7be90b23d599de919c9b8226a2c62772b5936190618dc`). It is not
predictive validation, external-reference certification, or publication approval.
No source, model, manifest, warehouse row or public output was changed by this
review; its only write is this file. `SOUTHERN_V3_RELEASE_DECISION.json` still
binds the archived run and must be re-bound to this run by its owner before any
downstream builder may treat the decision as approval.

## Scope and independence

Task `SOUTHERN-V3-INDEPENDENT-REVIEW-20260908`, role `validation_release`, fresh
reviewer context; nothing under review was implemented by this reviewer. HEAD
`88878b973fdac3cee95a8d8648da321e38e0021c` with the large preserved dirty
working tree; the review files (run bundle, archive, sensitivity outputs, new
scripts and tests) are unstaged/untracked and were read in place. The warehouse
was opened only with `?mode=ro` and `PRAGMA query_only=ON` (confirmed `1`); the
pre-rebuild backup was opened the same way. No loader, repair, retrain or
builder ran. The sensitivity audit script was re-executed once, read-only, into
the reviewer scratch directory to reproduce the committed outputs; the committed
files were confirmed unchanged afterwards (`generated_at_utc` still
`2026-09-08T13:20:14`).

Reviewed against the prior record `SOUTHERN_V3_INDEPENDENT_REVIEW_2026_09_07.md`
(NOT APPROVED) and its three blockers: unresolved source lineage for 97 Alabama
outcomes; Alabama 2022 canonical/certified disagreement; missing-context
sensitivity and uncertainty acceptance not recorded. Settled dispositions (v4
deferral, finance exclusion, Virginia baseline retention) were not reopened; no
new evidence against them was found.

## Standards

Findings against `AGENTS.md`, `CANONICAL_PIPELINES.md` ("Acceptance meanings")
and `DATA_CONTRACTS.md` ("Alabama certified canvass authority and canonical
bridge").

1. **Alabama source lineage is now evidence-backed (prior blocker 1, resolved).**
   `bridge_alabama_canonical_candidate_certified_result` holds 377 rows, all
   `review_status = approved`, one per canonical candidate (0 duplicate canonical
   IDs; the builder raises on a duplicate certified cell), all under
   `RUN-4C2EF8D12CC442D99A516E0D393DE157`: 203 `surname_unique_race_party`,
   173 `decoded_ballot_code_exact_normalized_name`, 1
   `precinct_workbook_exact_name_alignment_canvass_label_disagrees` (2018 HD83
   Republican; the canvass prints "Gray II", the same provider's precinct
   workbook names `MICHAEL J HOLDEN II` at the unique contest/party/category
   cell, and the cell is the only Republican named cell in that contest, so the
   total is identified independently of the printed label). Each row carries
   `evidence_json` with rationale, the physical cell ID and both sources'
   validation status. All 97 `alabama_canonical` outcomes in
   `mart_southern_war_outcome` carry a scalar `source_file_id`
   (`SRC-A3632F0E8738FDFB544D` for 64 rows in 2018, `SRC-DD940F20743C33261CC2`
   for 33 rows in 2022); both registry rows point at the canvass PDFs whose
   on-disk SHA256 values (`a83be9be…310044`, `2f924587…6091ed`) match the
   registry and the acquisition audits. `third_party_votes` for the 97 rows is
   the certified set total minus bridged D and R, with write-in and other-named
   components recorded in `source_quality_flags_json`; it does not enter
   `legislative_dem_margin` (two-party), so it does not affect WAR. The readiness
   inventory reports 0 missing scalar source-file IDs across 4,582 outcomes.
2. **Alabama 2022 (and 2018) canonical/certified disagreement is resolved by a
   registered, guarded repair (prior blocker 2, resolved).** 21 canonical totals
   (11 in 2018, 10 in 2022; 873 votes of absolute delta) were corrected to the
   certified value under `RUN-4C2EF8D1…`; `qa_warehouse_source_repair` row
   `WQA-ALCERT-RUN-4C2EF8D12CC442D99A516E0D393DE157` carries 21 before-images.
   Every current `canonical_votes` equals its bridged `certified_votes` (0
   disagreements over 377). All 21 certified values were re-checked against the
   hash-pinned row-level evidence (`ALABAMA_2018_CERTIFIED_SOURCE_ROWS.json`,
   SHA256 `14f62727…4664`, 11 of 11 match; every corrected 2018 canonical value
   equalled the incomplete precinct subtotal) and against
   `ALABAMA_2022_CERTIFIED_SOURCE_RECONCILIATION.json` (10 of 10 match, all
   `matched_certified_total`). The repair code updates with
   `WHERE … AND canonical_votes = <before>` guards, refuses winner-flag changes,
   verifies unowned tables by digest, and the producer now raises when a bridged
   canonical total disagrees with the canvass (`alabama_certified_outcome_fields`).
   No winner flag changed. Stale Alabama-side consumers of the old totals are
   recorded in the repair report, not rebuilt; they are outside this product.
3. **Missing-context sensitivity and uncertainty are recorded, bound and
   reproducible (prior blocker 3, resolved as descriptive evidence).** The audit
   binds to this exact run by `model_run_id`, manifest and `race_war.csv`
   SHA256, and rejects a warehouse build run other than the manifest's. Parity
   gate passed at 6.484e-14 on all three columns; a read-only rerun into scratch
   reproduced every summary key exactly (timestamps and runtime excepted). What
   the zero-fill encoding does: for the 2,376 races without validated prior-
   presidential context, the three lag columns enter the design as 0.0, so their
   published `fitted_lag_component` is exactly zero by construction (verified for
   all 2,376) and their headline WAR is the raw gap minus the non-lag part of a
   fit that those rows helped estimate. What it does not do: it does not assert
   an observed zero prior margin, and it does not make the headline a no-lag
   model for lag-available races (the lag terms move lag-available WAR by MAE
   1.33 points, 11.5% sign changes, which is the intended effect of the selected
   design). Refitting without lag columns moves missing-context WAR by MAE 0.33
   points (max 3.9) with 1.8% sign changes, below the bootstrap median expected-
   gap SE of 0.76; the `missing_excluded_fit` alternative (MAE 3.4, 21% sign
   changes) is an instrument that removes missing rows from fitting and drops
   state effects for states with no lag context, not a like-for-like score. What
   the 400-draw within-cycle bootstrap establishes: sampling variability of the
   structural expected gap conditional on the design, alpha 100, the zero-fill
   encoding and the observed race universe (median SE 0.76 points; 79.2% of 5–95
   WAR intervals exclude zero; 63.0% of races keep their D/R label in every
   draw). What it does not establish: variability of the observed raw gap
   itself, specification or alpha selection uncertainty, baseline measurement
   error, out-of-time predictive validity, or any candidate effect. Odd-year
   cycles are materially wider (median interval width 7.6 points in 2019 and
   11.5 in 2023, all-missing lag context) and Alabama is wider than the panel
   (median SE 1.34, 66.0% of intervals exclude zero, 48.5% stable party).
4. **The downstream gate is enforced and currently blocks, as designed.** Both
   builders verify `SOUTHERN_V3_RELEASE_DECISION.json` before reading model
   rows. The live decision still binds the archived manifest
   (`0ea55873…c7638`) and the 2026-09-07 review record; the live-binding test
   `test_current_v3_release_decision_is_exact_and_enforced` therefore fails at
   `manifest_sha256`, and the four fixture gate tests pass. This is the expected
   pre-decision state, not a defect; the decision file must be re-bound to this
   run and this review record by its owner. Do not edit the run manifest's
   `status` string (`research_candidate_pending_independent_validation`); it is
   hash-bound and historical, and the decision record is the authority.
5. **Excluded outcomes remain reason-coded, not scored.** 302 excluded rows
   split exactly into 151 `not_enabled:strict_baseline_eligible` (Virginia lower
   2017: 60; 2021: 91; `research_only_cross_election_precinct_membership`
   baselines) and 151 `not_enabled:strict_incumbency_eligible`
   (`experimental_exact_prior_winner`, ten states, 2019/2023/2024), all with a
   non-null `source_file_id`. The run scores 3,660 rows, equal to the strict
   post-2016 count in the training view and to the sum of strict rows over the
   94 post-2016 slices with strict rows (116 scheduled slices: 20 are 2016
   backcast slices, VA 2017 lower and VA 2021 lower are empty).

## Spec

Specification and provenance findings retained separately from Standards.

1. **Manifest integrity holds.** All 13 output SHA256 values and row counts match
   the files; every output's `model_run_id` column equals the manifest for all
   rows; all three report hashes, the five non-database input hashes and the
   three code hashes match; the full 5.8 GB warehouse file hashes to the
   registered `8cb49945…03b5`, so the run consumed exactly the current
   warehouse bytes. The 2018 context file is registered at its current bytes
   (`064c89b5…d2d90`), retiring the 09-07 consumed-field-parity disposition for
   this run. The contract-hash drift from the 09-07 review is closed: this run
   registers the current contract, and the archived run's documentation-only
   disposition (`SOUTHERN_V3_CONTRACT_COMPATIBILITY.json`) is enforced by tests
   that bind to the archive.
2. **WAR identity, orientation and units match the contract.** From the CSVs:
   `legislative_dem_margin = 100·(D−R)/(D+R)` (max error 7.1e-15), `raw_gap =
   legislative_dem_margin − baseline_dem_margin` (1.4e-14), `war = raw_gap −
   fitted_structural_expected_gap` (1.4e-14), `war_magnitude = |war|`,
   `war_party` follows the D/R/EVEN rule with 0 violations (0 EVEN rows), race
   keys and `war_outcome_id` unique, 7,320 candidate rows = exactly two parties
   per race with `candidate_cycle_war = ±war` (max error 0.0) and
   `score_identification = race_differential_party_orientation`; no pooled
   candidate columns exist. All values are Democratic two-party margin points.
   Lag inputs retain explicit `lag_context_available/source/scope/status`; all
   97 Alabama rows have `alabama_canonical` lag context; Alabama baselines are
   `same_cycle_federal` (96) and `same_cycle_state_fallback` (1), quality
   `canonical_reviewed`.
3. **Temporal claims stay bounded.** `structural_forward_metrics.csv` confirms
   every forward fold trains only on strictly earlier cycles (train max 2018 for
   2019 … 2023 for 2024); the selected `decaying_lag`/alpha 100 is the argmin of
   forward MAE (4.805) over the lag-available aggregate of 937 races, ahead of
   `constant_lag`/100 (4.807) and the best no-lag design (5.110), so the lag
   added-value gate passes by 0.305 points. Selection pools the 2019–2024
   evaluation folds rather than re-selecting per cycle, and the headline is the
   same-cycle full-sample fit labelled `same_cycle_full_sample_descriptive`;
   both are contract-permitted descriptive boundaries and no report makes a
   prospective claim. Cross-fitted residuals remain separate validation fields
   (the audit shows they differ from headline WAR with MAE 2.4 and 84.5% sign
   agreement). The finance nested gate still fails (nested MAE 5.646 vs 5.625
   without finance) and finance stays outside headline WAR.
4. **Regression relative to the archived run is confined to the corrected inputs
   and two intervening, registered warehouse repairs.** Against
   `WAR-POST2016-V3-8BB52074EC806C5BF6BF` (3,660 of 3,660 races matched):
   max |ΔWAR| 0.0760 (Alabama 2022 HD68), 0.0019 elsewhere; 1,786 rows changed
   by more than 1e-9, exactly the 2018 and 2022 cycle populations whose fits
   absorbed the seven corrected races; 0 `war_party` changes; 0 candidate
   `candidate_cycle_result` changes; forward-metric MAE moved by at most 2.6e-4;
   selection, alpha and both gates unchanged. Vote inputs changed only for 2018
   HD81, HD83, SD14, SD27 and 2022 HD32, HD68, HD92 (Δ dem 1–20, Δ rep 0–34);
   baselines, incumbency, lag context, candidate names/IDs and plan fields are
   unchanged for all rows. Two further field differences are not in the
   primary's summary and were traced: (a) `source_file_id` for all 36 Louisiana
   rows went from null in the archive to LA SOS `ByPrecinct_*.csv` IDs, applied
   in place by `RUN-C5CB7CFA8EB0454A9C65904A251D6CD2`
   (`southern_official_source_lineage_repair`, 2026-09-07, 377 rows; its
   after-hash of the outcome mart equals the before-image the 2026-09-08 repair
   recorded), with no change to LA votes or WAR; (b) 91 rows lost numeric
   `democratic_fundraising` (33) and/or `republican_fundraising` (61) amounts,
   all with `finance_complete = 0` and `incomplete_*` race finance status, from
   the 2026-09-05 masking repair `RUN-40A033B9854141F6B05A76173E66D17B`
   (`incomplete_finance_numeric_rows: 0`); finance statuses are unchanged and
   finance is not a headline input. The pre-rebuild backup shows the 2026-09-08
   writes changed only the 97 Alabama outcome rows (`third_party_votes`,
   `source_file_id`, `source_quality_flags_json`; votes for the seven races),
   left the 8,085 context rows identical apart from the run ID, and left every
   finance field in the training view identical.
5. **Limitations carried into release, not blockers.** (a) Every state,
   including Alabama, carries `geography_vintage = provider-reported; plan
   vintage unverified`; plan provenance is a product-wide disclosed limitation,
   not an Alabama regression. (b) The certified canvass observation sets remain
   `validation_status = review` (140 sets per cycle) and 30 2018 candidate rows
   are `review` because precinct subtotals fall below the certified total; the
   contract deliberately keeps the canonical route as the outcome family and
   takes only the certified total and lineage through the bridge, and the
   bridge records both statuses per row. (c) The canvass PDFs' redistribution
   terms are recorded as `review`; that is a publication and raw-commit concern,
   not a descriptive-use concern. (d) `review_status = approved` on bridge rows
   is a mechanical status under the recorded authority decision, with per-row
   evidence, not a per-row human sign-off.

## Verification and limitations

Repository Python (`.venv/Scripts/python.exe`), read-only inline scripts, and
pytest with `-p no:cacheprovider` and an isolated `TESTMON_DATAFILE` under the
reviewer scratch directory.

- Hash/identity script over the manifest: 13/13 output hashes and row counts
  match; 13/13 outputs carry only `WAR-POST2016-V3-4AF79A70EAA8F39EBD49`; 3/3
  report hashes, 5/5 non-database input hashes, 3/3 code hashes match; manifest
  SHA256 `c6c09e19…5a6`. Separate full-file SHA256 of
  `alabama_elections.sqlite`: matches `8cb49945…03b5`.
- Warehouse (`?mode=ro`, `query_only=1`): latest runs
  `RUN-DD7FF8C9…` (2018 append: 140 sets, 352 rows, 322 passed/30 review),
  `RUN-4C2EF8D1…` (repair: 377 bridge rows, 21 corrections, 23 materialized
  rows, schema 27), `RUN-92AB8DE3…` (rebuild: 4,582 outcomes, 4,280 strict,
  302 research, 116/116 slices); bridge cardinality and match-method counts as
  stated; 0 bridge/canonical disagreements; QA row with 21 before-images;
  outcome mart, training view and context table each carry one build run;
  3,660 strict post-2016 rows; Alabama lineage and third-party checks as stated.
- Pre-rebuild backup (`pre-southern-outcome-rebuild-2026-09-08.sqlite`,
  `?mode=ro`): 4,582/4,582 outcome keys matched; 97 rows differ, all Alabama,
  in the fields listed above; context digest identical excluding `build_run_id`;
  0 finance field differences over 3,660 training rows; backup `latest_run`
  `RUN-4C2EF8D1…`, `mart` build run `RUN-85A4692E…`, 0 null LA source IDs.
- Archive comparison (`race_war.csv`, `candidate_cycle_war.csv`,
  `structural_forward_metrics.csv`, `finance_nested_metrics.csv`, manifests):
  counts as stated in Spec 4.
- Evidence pins: 2018 rows JSON SHA256 matches the loader constant; 11/11 2018
  and 10/10 2022 corrected certified values match; HD83 alignment row verified;
  both canvass PDFs hash to their registered values.
- Sensitivity outputs: 5 files, all rows bound to the run; recomputed from the
  by-race files: 0.7918 intervals exclude zero, 0.6303 stable party, median SE
  0.7589, missing-context no-lag MAE 0.3321 with 0.0181 sign changes, 2,376
  missing rows with zero lag component. Read-only rerun
  `python scripts/audit_southern_v3_context_sensitivity.py --output-dir <scratch>
  --report <scratch>/SENSITIVITY_REPRO.md`: parity passed, 6.484e-14; summary
  identical to the committed file on every key except `generated_at_utc`,
  `runtime_seconds`, `run_dir`.
- `pytest scripts/tests/test_post2016_southern_war_v3.py -p no:cacheprovider -q`:
  **15 passed**.
- `pytest scripts/tests/test_alabama_certified_bridge.py
  scripts/tests/test_southern_v3_context_sensitivity.py -p no:cacheprovider -q`:
  **37 passed**.
- `pytest scripts/tests/test_southern_war_release_gate.py -p no:cacheprovider
  -q`: **4 passed, 1 failed** (`test_current_v3_release_decision_is_exact_and_
  enforced` at the stale `manifest_sha256`; expected until the decision is
  re-bound).
- `pytest scripts/tests/test_alabama_2018_source_load.py
  scripts/tests/test_southern_release_readiness.py
  scripts/tests/test_southern_war_preparation_warehouse.py -p no:cacheprovider
  -q`: **65 passed, 1 warning** (all fixture databases under `tmp_path`).
- Registry validation command `pytest --testmon --testmon-noselect
  -p no:cacheprovider scripts/tests/test_post2016_southern_war_v3.py
  scripts/tests/test_alabama_certified_bridge.py -q`: **35 passed** (repeat of
  files above with the task's flags).
- Git: `git rev-parse HEAD`; scoped `git status --porcelain` over the review
  files (all unstaged/untracked; nothing staged in scope).

Not verified: the canvass PDFs were not re-parsed by this reviewer (certified
values were checked against the hash-pinned adapter evidence, not the PDF
text); the two earlier 2026-09-08 backups were not opened or hashed (only their
sizes and the third backup's contents were inspected); the content of the
2026-09-05 finance masking and 2026-09-07 Louisiana lineage repairs was traced
to their registered run records, not re-derived from sources; no non-Alabama
source file, baseline allocation or plan vintage was re-validated (unchanged
since the archived run and outside the rebuilt scope); the Split Ticket
reference was not re-fetched; no full repository suite, historical builder, map
builder, browser check or publication ran; the primary's post-rebuild full-suite
run, required by the task contract before declaring the ratings complete, is
not evidenced in the records read here.

## Next bounded work

1. Owner of `SOUTHERN_V3_RELEASE_DECISION.json`: re-bind it exactly to this run
   (`model_run_id` `WAR-POST2016-V3-4AF79A70EAA8F39EBD49`, `manifest_sha256`
   `c6c09e19335965380e068c40484437bf460db81add232dc8d7cf78d135a905a6`,
   `review_record_path` this file with its SHA256) with decision
   `approved_for_descriptive_historical_use` and limits stating descriptive
   same-cycle use only; then rerun `test_southern_war_release_gate.py` to show
   5 passed. Do not edit the run manifest or archived run.
2. Only then: historical builder, map builder, browser (1258 and 390 px) and
   download-parity checks; the state limitations must carry the plan-vintage,
   certified-source review-status and Louisiana/odd-year uncertainty
   disclosures, and should surface the per-cycle bootstrap uncertainty already
   computed (odd-year widths of 7.6–11.5 points).
3. Record the primary's full repository suite result in the task log before the
   ratings are declared complete; resolve the canvass redistribution-terms
   review before committing the raw PDFs or publishing; Alabama-side consumers
   of the old 2018/2022 totals remain recorded stale under their own products.

Summary: Standards — 5 findings, all three prior blockers resolved with
verifiable evidence, gate enforced and awaiting re-binding; Spec — 5 findings,
identity/orientation/units and temporal boundaries verified, regression limited
to corrected inputs plus two traced intervening repairs, limitations recorded.
