# Task contract: VALIDATE-OPENELECTIONS-STAGING-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently validate OpenElections historical normalization, party resolution, aggregation, reconciliation, and provenance.
- Non-goals: No implementation, canonical warehouse, model, or website changes.
- Upstream snapshot: `ELECTION-GEO-OPENELECTIONS-NORMALIZE-001` review candidate.
- Read scope: Staging pipeline/tests/outputs/manifest, validated acquisition bundle, and Klarner reconciliation source.
- Write scope: `project_docs/audits/OPENELECTIONS_HISTORICAL_STAGING_VALIDATION.md`; `project_docs/coordination/VALIDATE-OPENELECTIONS-STAGING-001.md`
- Warehouse mode: `read-only`
- Inputs: 720,261 relevant normalized observations across fourteen state-cycle combinations.
- Outputs: Pass/fail staging validation report and explicit usable-cycle assessment.
- Acceptance checks: Deterministic temporary rebuild; mode sums verified; office/district parsing audited; party resolution cannot overwrite known source labels; keys and aggregates reconcile; manifest hashes/counts match; suspicious state-cycles identified; focused tests pass.
- Handoff recipient: `forecast_model` historical panel builder.
- Known risks: Georgia 2016 has widespread missing source party labels; Arkansas 2008 appears incomplete; South Carolina 2006 contains context but no legislative contests.
