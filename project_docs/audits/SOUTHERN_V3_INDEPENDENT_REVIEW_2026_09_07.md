# Independent review: exact Southern v3 run

Decision: **NOT APPROVED FOR RELEASE**. Technical/provenance review completed;
independent scientific acceptance remains incomplete. A completed review assignment
is not a passed product gate. No source, model, manifest or public output changed.

## Scope and independence

User requested independent review of `WAR-POST2016-V3-8BB52074EC806C5BF6BF`.
Manifest SHA256: `0ea558730b9e953d95853d552960886c855b8bb3f9fb9cb2ee0a3c44a47c7638`.
HEAD: `88878b973fdac3cee95a8d8648da321e38e0021c`, with existing dirty worktree.
The named current artifact bundle, producing code, current contract, validation
report and relevant WIP were reviewed, not every repository change.

A fresh read-only subagent reviewed specification/provenance evidence. The primary
reviewed standards/status integration and ran four additional existing artifact
tests. These primary checks are not independent scientific approval. Neither
reviewer trained a model or generated new scores. Source parity, context sensitivity
experiments and scientific uncertainty acceptance were not independently completed.

Read-only scope checks: git status, HEAD resolution, scoped `git diff HEAD`,
staged/unstaged inspection, direct file reads and manifest hash comparisons.
No staged changes existed in the selected scope. Unrelated/untracked warehouse
work was preserved. The initial all-repository status output was truncated;
subsequent inspection was narrowed to the named review files. There is no claim
that every unrelated working-tree file was reviewed.

## Standards

1. **Unresolved upstream approval is not enforced downstream.** The v3 manifest
   and validation report explicitly retain pending independent validation, while
   `build_southern_historical_war_v1.py:321` emits
   `validated_descriptive_historical_release` without resolving that upstream
   approval. Numerical and warehouse-run checks are not the required independent
   release decision. This conflicts with AGENTS.md's non-negotiable distinction
   between research, validated and published artifacts. Do not promote by changing
   a status string. The existing historical output is not newly approved here.
2. **Transitive source provenance remains unresolved.** The readiness inventory
   records 97 missing source-file IDs, and source/context dependency reconciliation
   remains open. Whole-file or old warehouse-run validation cannot certify all
   current consumers after repairs. This fails the current completion contract's
   source-lineage requirement; no new claim that all affected values are wrong is
   made. See `SOUTHERN_RELEASE_READINESS_2026_09_07.md` and its JSON evidence.

No style-only or speculative abstraction changes are requested.

## Spec

Independent reviewer findings, retained separately from Standards:

1. **The existing contract-hash gate fails.** Test
   `test_post2016_southern_war_v3.py:100` expects field-contract SHA256
   `272c60027414654d37ef6d5851cc6224cb432ea12bdf6df05cf53a48b0c7ae32`;
   current document SHA256 is
   `3de27261136fb5574fc7be90b23d599de919c9b8226a2c62772b5936190618dc`.
   The contract explicitly preserves historical hashes. This is documented
   contract drift needing a reviewed compatibility/disposition record, not
   permission to rewrite the old run manifest or weaken the assertion.
2. **Missing-context sensitivity and uncertainty acceptance are not recorded.**
   The current field contract requires review of zero-filled compatibility
   encodings before release. The validation report still leaves context and
   uncertainty review pending. Existing coverage/error summaries are not evidence
   that this review was accepted. This finding does not impose forecast-probability
   calibration or an unrequested model expansion on descriptive historical WAR.
3. **Temporal claims must remain bounded.** Tournament fits use earlier-cycle
   training (`retrain_post2016_southern_war_v2.py:280`); specification selection
   aggregates the evaluation cycles (`:314`); cross-fitting permits other
   same-cycle observations (`:338`). These are descriptive boundaries, not evidence
   of rolling hyperparameter selection or independent prospective evaluation.
   Same-cycle residual fitting itself is explicitly allowed by the contract.

## Verification and limitations

- All 13 registered output hashes and all three implementation hashes match.
- Three other non-database input hashes match. The 2018 context-file byte mismatch
  has a separately reviewed exact consumed-field parity disposition; it is not
  counted again as unexplained drift. The revised contract remains mismatched.
- Full warehouse bytes were not rehashed. Current snapshot/source limitations are
  retained in the readiness audit; an unchanged old input run is not full parity.
- Independent reviewer: repository Python, isolated temporary TESTMON_DATAFILE,
  `pytest --testmon --testmon-noselect` on the single manifest/config/hash test:
  **1 failed**, solely at the changed field-contract hash assertion.
- Primary: repository Python, isolated `southern-v3-review-primary.testmon.sqlite`,
  `pytest --testmon --testmon-noselect -p no:cacheprovider
  scripts/tests/test_post2016_southern_war_v3.py
  -k 'not manifest_hashes_contract_and_finance_exclusion' -q`:
  **4 passed, 1 deselected in 2.61s**. These inspect existing artifacts; no builder
  or model fit ran. Together the two invocations exercised all five tests once.
- No full suite, browser release test, source repair, model sensitivity experiment,
  retraining or publication was performed. The independent reviewer did not
  validate candidate scores; primary identity tests do not fill that scientific
  acceptance gap.

## Next bounded work

Preserve this exact run and evidence. First disposition the revised contract
against its immutable run-era version without relabeling historical approval.
Then reconcile source/context lineage and perform the explicitly required
missing-context sensitivity/uncertainty review under the descriptive contract.
Only an independently accepted result may clear the upstream release gate;
Southern final regional/browser checks remain subsequent work.

Summary: Standards — 2 findings, strongest issue unresolved upstream approval;
Spec — 2 acceptance blockers plus 1 temporal-interpretation limitation, strongest
issues failed contract-hash gate and absent sensitivity/uncertainty acceptance.
