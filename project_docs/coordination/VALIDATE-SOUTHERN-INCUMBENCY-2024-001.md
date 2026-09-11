# Task contract: VALIDATE-SOUTHERN-INCUMBENCY-2024-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete` — PASS for gated experimental modeling. The deterministic rebuild preserves 335 races/670 candidates, correctly uses 2020 and 2022 staggered winners, keeps ambiguity missing, yields 323 ready/12 unresolved and 246 running/77 inferred-open, admits no double-incumbent race, supports only Mainor's switch, reproduces hashes, and passes 5/5 tests.
- Objective: Independently validate the inferred 2024 Southern incumbency staging before any forecast model consumes it.
- Non-goals: No implementation, identity adjudication, warehouse, model, website, or publication changes.
- Upstream snapshot: `PEOPLE-SOUTHERN-INCUMBENCY-2024-001` review candidate.
- Read scope: Incumbency implementation/tests/outputs/source note; referenced MEDSL/Klarner ZIP members and current recent panel.
- Write scope: `project_docs/audits/SOUTHERN_2024_INCUMBENCY_VALIDATION.md`; `project_docs/coordination/VALIDATE-SOUTHERN-INCUMBENCY-2024-001.md`.
- Warehouse mode: `read-only`
- Inputs: Review-candidate staging artifacts and source records.
- Outputs: PASS/FAIL audit with exact evidence and blockers.
- Acceptance checks: Temporary deterministic rebuild; verify 335 races/670 candidates, 2020+2022 winner use for staggered chambers, name normalization and surname-party restrictions, ambiguity remains missing, no double-incumbent ready race, 323 ready/12 unresolved, supported Mainor switch, hashes, and tests.
- Handoff recipient: `/root`, then `forecast_model` only after PASS.
- Known risks: Post-2022 special-election winners are not explicitly modeled and must remain a documented sensitivity.
