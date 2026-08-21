# Task contract: VALIDATE-IDEOLOGY-CMO-V2-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`

## Handoff

- Outcome: `PASS`
- Evidence: one-to-one equality for all 1,018 stable candidate IDs; zero missing
  or extra IDs; Barbara Boyd 2022 HD-32 D equals -4.368377 in the analysis and
  -4.3683773667 in four public payload observations; all 4,697 public
  candidate-CMO observations reconcile by ID; stale preliminary fields are not
  referenced by the builder or page; focused tests pass 17/17.
- Changed implementation/public/model files: none.
- Report: `project_docs/audits/IDEOLOGY_CMO_V2_VALIDATION.md`.
- Downstream invalidation: none.
- Next action: accountable owner may publish the validated ideology rebuild.
- Objective: Independently verify that all ideology-page CMO values derive from CMO v2 context scores and that stale preliminary-CMO values are absent.
- Acceptance checks: Full candidate-ID equality check passes; Barbara Boyd's 2022 HD-32 value is approximately -4.37 in analysis and page payload; focused tests pass; findings are recorded.
- Read scope: `data/processed/war/cmo_v2_candidates.csv`; `research/cmo_ideology/absolute_rebuild_*`; `docs/ideology-performance.html`; relevant build and test scripts.
- Write scope: `project_docs/audits/IDEOLOGY_CMO_V2_VALIDATION.md`; this contract; its active-task ledger row.
- Upstream inputs: `IDEO-ABS-REBUILD-001`; `WEB-IDEOLOGY-CMO-V2-001` release candidate.
- Expected outputs: Independent PASS/FAIL release report.
- Warehouse mode: read-only.
