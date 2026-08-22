# Task contract: VALIDATE-REPO-CLEANUP-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently verify that the conservative repository cleanup removes obsolete public CMO artifacts, preserves reproducibility and active work, establishes valid canonical commands, and does not break the site or test suite.
- Acceptance checks: Hygiene audit passes; canonical CMO/site commands run; no v2/v3/preliminary CMO exports remain in `docs/data/`; all v4 exports remain exact; raw/manual/processed historical inputs are preserved; focused tests and full suite pass; deleted public copies remain recoverable from Git or processed outputs.
- Read scope: Cleanup diff, repository status, canonical pipeline documentation, publication outputs, tests, and retained processed model files.
- Write scope: `project_docs/audits/REPOSITORY_CLEANUP_VALIDATION.md`; this contract; its ledger row.
- Upstream inputs: `REPO-CLEANUP-001` review candidate.
- Expected outputs: Independent PASS/FAIL report and final task statuses.
- Warehouse mode: read-only.
