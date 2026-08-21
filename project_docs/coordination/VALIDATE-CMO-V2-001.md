# Task contract: VALIDATE-CMO-V2-001 independent CMO v2 validation

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently audit the revised four-estimand CMO staging release for leakage, identity correctness, temporal validity, statistical invariants, output integrity, and fidelity to the ten approved methodological priorities.
- Non-goals: Do not edit model code, model outputs, model documentation, warehouse tables, or public pages.
- Upstream snapshot: `CMO-METHODOLOGY-V2-001` review candidate built from commit `4bc17d8` inputs.
- Read scope: `scripts/rebuild_cmo_methodology_v2.py`; its tests; all `cmo_v2_*` outputs; current and revised model cards; frozen upstream CMO inputs and diagnostics.
- Write scope: `project_docs/audits/CMO_METHODOLOGY_V2_VALIDATION.md`; this contract and its active-task row.
- Warehouse mode: read-only.
- Inputs: Versioned v2 outputs and frozen upstream inputs.
- Outputs: Independent PASS/FAIL report with reproducible findings.
- Acceptance checks: Verify no candidate-derived headline features; stable-person longitudinal joins; outer-cycle and nested-forward temporal separation; keys, counts, nulls, bounds and party orientation; contest-tier handling; source-aware baseline math; within-cycle centering; partial pooling; race-varying uncertainty; construct-validity design restrictions; deterministic rebuild; focused and full tests; explicit identification of any claims not supported by outputs.
- Handoff recipient: `/root` and `web_product`.
- Known risks: Small number of cycles, sparse repeats, era change, historical geography, and unmeasured seat context.

## Handoff

- Outcome: `FAIL`
- Validation results: source-aware baseline math, race-level estimands,
  candidate-free headline features, cycle separation, tiers, bounds,
  centering, orientation, race-varying uncertainty, deterministic rebuild,
  focused 6/6 tests, and full 366/366 tests passed. Stable-person identity,
  candidate-level attribution/diagnostics, two construct-validity claims, and
  model-run provenance failed.
- Blocking evidence: 14 eligible-panel effect IDs occur multiple times in one
  cycle; `ALPERSON-SMITH` conflates seven distinct candidates and both parties.
  Thirteen of 128 reported repeat rows use same-cycle-duplicated and/or
  cross-party IDs. Retirement and independent-prediction claims exceed the
  implemented designs. No v2 run manifest or equivalent provenance exists.
- Changed production/model files: none (deterministic rebuild reproduced exact
  bytes).
- Generated output: `project_docs/audits/CMO_METHODOLOGY_V2_VALIDATION.md`.
- Downstream invalidation: candidate history, partial-pooled effects,
  appearance reliability, and candidate-based construct-validity outputs.
- Next action: CMO model owner repairs/filters stable identities, narrows the
  construct designs/claims, adds run provenance, rebuilds, and requests
  revalidation.

## Remediation revalidation

- Outcome: `FAIL`
- Passing remediation: zero duplicate cycle/effect keys; Smith, Anderson, Jack
  Williams, and Phil Williams collision families split correctly; repeat count
  122; bivariate/incumbent-departure output labels corrected; four input and
  code hashes valid; deterministic 12-file rebuild; focused 7/7 and full
  367/367 tests.
- Remaining blockers: 79 surname-only IDs still span cycles; nine change
  chamber/district, four contaminate the repeat sample, and examples such as
  1994/2014 `COPELAND` remain pooled without person evidence. The model card
  retains one unsupported “independently predict” sentence. The manifest lacks
  a build/run ID and output hashes.
- Changed production/model files: none (validation rebuild reproduced exact
  bytes).
- Downstream invalidation: candidate history, candidate effects/reliability,
  and candidate-based construct-validity outputs.
- Next action: split or corroborate surname-only cross-cycle identities, remove
  the remaining unsupported claim, complete the manifest, and revalidate.

## Final remediation revalidation

- Outcome: `FAIL`
- Passing remediation: all 563 one-token names are unique race-specific
  unresolved IDs; zero longitudinal surname-only joins; Smith, Anderson, Jack
  Williams, and Phil Williams checks pass; repeat n=77; candidate history and
  effects are no longer contaminated; deterministic run ID and all four input,
  code, and ten output hashes verify; two rebuilds identical; focused 7/7 and
  full 367/367 tests.
- Remaining blocker: 103 of 276 rows in the “different candidate” same-seat
  design contain an unresolved current or prior identity. Different
  race-specific IDs do not establish different people; 40 even share the same
  upstream `person_id`. The construct and its 276-row documentation claim are
  invalid until unresolved comparisons are excluded or adjudicated.
- Documentation correction: predictive cycle-balanced MAE is 12.67749, not the
  stale 12.55 printed in the model card.
- Changed production/model files: none (two validation rebuilds reproduced
  exact bytes).
- Next action: restrict the successor design to resolved distinct identities,
  rebuild its statistics, update the model-card MAE, and request narrow final
  revalidation.

## Final successor revalidation

- Outcome: `PASS`
- Validation results: successor design has 173 resolved pairs (172 normalized
  full names, one resolved collision split), zero unresolved rows, and no same
  upstream-person pair misclassified as different. Repeat n=77, successor
  Spearman 0.48873, and predictive MAE 12.67749 agree with documentation. All
  prior race, leakage, identity, orientation, uncertainty, and manifest gates
  pass. Two rebuilds are byte-identical; focused 7/7 and full 367/367 tests
  pass.
- Changed production/model files: none (validation rebuilds reproduced exact
  bytes).
- Downstream invalidation: none.
- Next action: release owner may advance the validated staging outputs to a
  separately controlled publication/migration task.
