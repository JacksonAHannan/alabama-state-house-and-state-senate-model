# Task contract: VALIDATE-CMO-SOUTHERN-COMBINED-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently validate the combined-panel historical Southern CMO tournament, model selection, and candidate residual outputs.
- Non-goals: No implementation, canonical warehouse, production forecast, or website changes.
- Upstream snapshot: `CMO-SOUTHERN-COMBINED-TOURNAMENT-001` review candidate.
- Read scope: Combined panel/manifest; tournament implementation; new outputs/tests/methodology note; validated HEDA-only benchmark.
- Write scope: `project_docs/audits/CMO_SOUTHERN_COMBINED_VALIDATION.md`; `project_docs/coordination/VALIDATE-CMO-SOUTHERN-COMBINED-001.md`
- Warehouse mode: `read-only`
- Inputs: 2,273 strict combined races and generated 28,770 predictions/4,546 candidate residuals.
- Outputs: Pass/fail experimental model approval and documented caveats.
- Acceptance checks: Independent deterministic rebuild; temporal and state fold isolation; declared selection rule; symmetric unique candidate residuals; output hashes/counts; comparison claims; focused tests.
- Handoff recipient: `orchestrator`
- Known risks: Missouri-heavy additions, secondary sources, pre-2000 gap, state-aware model portability.
