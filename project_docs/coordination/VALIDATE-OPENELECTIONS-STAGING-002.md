# Task contract: VALIDATE-OPENELECTIONS-STAGING-002

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Confirm the Georgia 2016 presidential-office parser correction and rebuilt staging provenance.
- Non-goals: No implementation, warehouse, model, or website changes.
- Upstream snapshot: Rebuilt `ELECTION-GEO-OPENELECTIONS-NORMALIZE-001` after USP classifier correction.
- Read scope: Revised pipeline/tests, staging outputs/manifest, and validation v1.
- Write scope: `project_docs/audits/OPENELECTIONS_HISTORICAL_STAGING_VALIDATION_V2.md`; `project_docs/coordination/VALIDATE-OPENELECTIONS-STAGING-002.md`
- Warehouse mode: `read-only`
- Inputs: Rebuilt 728,340-observation staging candidate.
- Outputs: Final pass/fail experimental staging approval.
- Acceptance checks: All 8,079 Georgia 2016 presidential rows classify USP; context count increases accordingly; prior passing checks remain valid; manifest hashes/counts and focused tests pass.
- Handoff recipient: `forecast_model`
- Known risks: Cycle-specific fitness caveats from validation v1 remain.
