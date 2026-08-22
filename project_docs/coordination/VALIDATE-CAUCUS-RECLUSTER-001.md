# Task contract: VALIDATE-CAUCUS-RECLUSTER-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently verify that caucus clustering is deterministic, outcome-blind, current-CMO consistent, and interpreted in proportion to stability and era diagnostics.
- Non-goals: Modify clustering code, evidence, or outputs.
- Upstream snapshot: `IDEO-CAUCUS-RECLUSTER-001` candidate outputs.
- Read scope: clustering script, tests, input panel, CMO v4, and generated outputs.
- Write scope: `project_docs/audits/CAUCUS_RECLUSTER_VALIDATION.md`; `project_docs/coordination/VALIDATE-CAUCUS-RECLUSTER-001.md`; `project_docs/coordination/active_tasks.csv`.
- Warehouse mode: `read-only`
- Inputs: Rebuilt party-specific clustering analysis.
- Outputs: Independent pass/fail validation report.
- Acceptance checks: `python -m pytest scripts/tests/test_democratic_ideological_clusters.py -q` and full collection pass; CMO matches v4; outcomes are excluded; selected k follows the rule; weak Republican robustness is identified.
- Handoff recipient: `legislative_ideology`
- Known risks: Missingness and era can masquerade as ideological factions.
