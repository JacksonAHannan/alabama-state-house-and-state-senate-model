# Task contract: VALIDATE-SOUTHERN-HISTORICAL-PANEL-002

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Validate remediation of partial context allocation and panel provenance in the historical Southern experimental panel.
- Non-goals: No implementation, canonical warehouse, production model, or website changes.
- Upstream snapshot: Remediated `SOUTHERN-HISTORICAL-PANEL-001` review candidate dated 2026-08-22.
- Read scope: Historical Southern panel pipeline/tests/outputs/manifest and revised HEDA staging/manifest.
- Write scope: `project_docs/audits/SOUTHERN_HISTORICAL_PANEL_VALIDATION_V2.md`; `project_docs/coordination/VALIDATE-SOUTHERN-HISTORICAL-PANEL-002.md`
- Warehouse mode: `read-only`
- Inputs: Remediated panel with expected/allocated/incomplete context counts and strict/permissive eligibility.
- Outputs: Pass/fail experimental-use validation report.
- Acceptance checks: Temporary rebuild; eight focused tests; incomplete context is retained and flagged; strict eligibility contains no partial baseline; permissive-only difference reconciles; panel manifest hashes and counts match.
- Handoff recipient: `cmo_model`
- Known risks: Experimental baselines still depend on secondary HEDA geography and are not canonical facts.
