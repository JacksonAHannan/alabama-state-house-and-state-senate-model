# Task contract: VALIDATE-IDEOLOGY-COVERAGE-RERUN-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently validate the rebuilt ontology-v3 evidence, absolute ideology analysis, and caucus clustering.
- Read scope: Outputs and tests named by `IDEOLOGY-COVERAGE-RERUN-001` plus repaired identity validation.
- Write scope: `project_docs/validation/IDEOLOGY_COVERAGE_RERUN_VALIDATION.md` only.
- Warehouse mode: `read-only`
- Expected output: PASS/FAIL report with freshness, stable-ID, temporal, row-count, and test findings.
- Acceptance checks: Analysis/cluster tests pass; Jack Williams ambiguity does not reappear; generated evidence and analyses postdate the identity repair; no duplicate candidate-evidence keys.
- Handoff recipient: `/root` and web product.
