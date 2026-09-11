# Task contract: VALIDATE-SOUTHERN-HISTORICAL-PANEL-003

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Confirm the rebuilt release manifests resolve the sole remaining provenance failure after substantive validation passed.
- Non-goals: No implementation, data, model, warehouse, or website changes.
- Upstream snapshot: Dependency-ordered HEDA and panel rebuild after validation v2.
- Read scope: Current HEDA and historical-panel manifests, their pipelines, source inputs, and generated outputs.
- Write scope: `project_docs/audits/SOUTHERN_HISTORICAL_PANEL_VALIDATION_V3.md`; `project_docs/coordination/VALIDATE-SOUTHERN-HISTORICAL-PANEL-003.md`
- Warehouse mode: `read-only`
- Inputs: Rebuilt release manifests and v2 validation findings.
- Outputs: Final pass/fail provenance confirmation.
- Acceptance checks: Recompute build IDs and all input/output hashes; verify HEDA manifest reflects current staging script and panel manifest reflects current HEDA manifest; confirm focused tests remain 8/8.
- Handoff recipient: `cmo_model`
- Known risks: Approval remains for experimental use only, not canonical promotion.
