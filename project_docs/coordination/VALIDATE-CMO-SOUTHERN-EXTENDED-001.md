# Task contract: VALIDATE-CMO-SOUTHERN-EXTENDED-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently validate the historical Southern CMO tournament rerun on the 2,383-row Arkansas-extended panel.
- Non-goals: No implementation, warehouse, production forecast, Alabama CMO, or website changes.
- Upstream snapshot: `CMO-SOUTHERN-EXTENDED-TOURNAMENT-001` review candidate.
- Read scope: Validated extended panel; tournament implementation; new outputs/tests/note; validated 2,273-row benchmark.
- Write scope: `project_docs/audits/CMO_SOUTHERN_EXTENDED_VALIDATION.md`; `project_docs/coordination/VALIDATE-CMO-SOUTHERN-EXTENDED-001.md`
- Warehouse mode: `read-only`
- Inputs: 2,383 rows, 31,934 predictions, and 4,766 candidate residuals.
- Outputs: Pass/fail experimental model approval and caveats.
- Acceptance checks: Deterministic rebuild; temporal/state fold isolation; guardrail-based portable-temporal selection; symmetric unique residuals; metrics/effects/comparison claims; hashes/counts; five focused/shared tests.
- Handoff recipient: `orchestrator`
- Known risks: Arkansas-only pre-2000 evidence; incomplete context footprint; represented-cycle sensitivity.
