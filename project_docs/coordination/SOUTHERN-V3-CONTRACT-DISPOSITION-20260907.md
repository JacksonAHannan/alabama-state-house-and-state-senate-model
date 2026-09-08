# Task contract: SOUTHERN-V3-CONTRACT-DISPOSITION-20260907

- Accountable role: `validation_release`
- Owner: `/root`
- Status: `complete`
- Objective: Preserve the exact field contract used by the existing Southern v3 run and record a reviewed documentation-only compatibility disposition for the current clarified contract.
- Product/layer and checklist IDs: Southern historical WAR, validation evidence supporting `southern-07`; this task does not complete that checklist item.
- Dependencies: Exact run `WAR-POST2016-V3-8BB52074EC806C5BF6BF` and manifest SHA256 `0ea558730b9e953d95853d552960886c855b8bb3f9fb9cb2ee0a3c44a47c7638`.
- Non-goals: No source repair, model execution, score change, scientific approval, status promotion, publication or release-gate waiver.
- Upstream snapshot: Existing run-era contract SHA256 `272c60027414654d37ef6d5851cc6224cb432ea12bdf6df05cf53a48b0c7ae32`; current clarified contract SHA256 `3de27261136fb5574fc7be90b23d599de919c9b8226a2c62772b5936190618dc`.
- Read scope: Exact v3 manifest, code hashes, run-era contract, current field contract and independent review.
- Write scope: `project_docs/audits/SOUTHERN_V3_RUN_8BB52074_FIELD_CONTRACT.md`; `project_docs/audits/SOUTHERN_V3_CONTRACT_COMPATIBILITY.json`; `scripts/tests/test_post2016_southern_war_v3.py`; this contract and the active-task row.
- Warehouse mode: `read-only`
- Inputs: Immutable v3 artifact bundle and exact documentation hashes.
- Outputs: Run-era contract archive, machine-readable compatibility decision and tamper-resistant tests.
- Acceptance checks: The archived contract matches the manifest-recorded hash; the current contract and all three producer hashes match the disposition; changed evidence cannot be masked; all disposition tests pass.
- Review requirement: Independent documentation review by `/root/al2022_source_implementation`; status `approved_documentation_only` with explicit scientific and publication limits.
- Publication authority: `none`
- Recovery/replay: Documentation and tests only; no model or warehouse side effects. Re-run focused tests after any contract, disposition, manifest or producer-code change.
- Handoff recipient: `validation_release`
- Known risks: A documentation compatibility decision cannot satisfy missing source lineage or scientific sensitivity acceptance.

## Handoff

The run-era contract and current clarified contract are both preserved. The
machine-readable disposition binds their hashes, the exact v3 manifest and all
three producer hashes. Fourteen focused disposition checks passed on September 8.
This resolves the contract-hash finding only; the v3 release decision remains
blocked on source and scientific evidence.
