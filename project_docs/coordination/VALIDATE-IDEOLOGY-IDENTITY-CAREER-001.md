# Task contract: VALIDATE-IDEOLOGY-IDENTITY-CAREER-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `active`
- Objective: Independently validate the candidate-legislator identity repair and the separation of pre-election and career ideology marts.
- Read scope: Repair scripts/tests, task contract/audit, election candidate universe, legislative warehouse, ontology, and generated ideology staging outputs.
- Write scope: `project_docs/validation/IDEOLOGY_IDENTITY_CAREER_REPAIR_VALIDATION.md` only.
- Warehouse mode: `read-only`
- Upstream inputs: Outputs of `IDEOLOGY-IDENTITY-CAREER-REPAIR-001`.
- Expected output: PASS/FAIL report with commands, cardinality checks, temporal leakage checks, long-service coverage checks, and any blockers.
- Acceptance checks: Reproduce focused tests; verify 2022 code decoding, unique cycle/chamber member links, no future-vote leakage, career cutoff labels, four-session coverage, and ambiguity quarantine.
- Handoff recipient: `/root`.
