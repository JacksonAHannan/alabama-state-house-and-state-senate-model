# Task contract: VALIDATE-CMO-CQI-V5-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently validate CMO v5 direct arithmetic, candidate-effect estimation, temporal safety, model selection, uncertainty, symmetry, and case-study conclusions.
- Non-goals: Edit model implementation, source data, canonical warehouse objects, or public pages.
- Upstream snapshot: `CMO-CQI-V5-001` release candidate.
- Read scope: v5 builder/tests/outputs/report, canonical CMO inputs, and v3/v4 comparison outputs.
- Write scope: `project_docs/audits/CMO_CQI_V5_VALIDATION.md`; `project_docs/coordination/VALIDATE-CMO-CQI-V5-001.md`; `project_docs/coordination/active_tasks.csv`.
- Warehouse mode: `read-only`
- Inputs: CMO v5 model candidate and frozen canonical source exports.
- Outputs: PASS/FAIL audit covering arithmetic, leakage, candidate identities, model selection, uncertainty, subgroup symmetry, case studies, and reproducibility.
- Acceptance checks: Reproduce all direct scores from source margins; prove current federal margin is absent from lag predictors; independently reconstruct cycle/source replacement levels and candidate ridge effects; verify forward-cycle estimates use earlier cycles only; verify selected structural specification and penalty follow declared gates; verify candidate differential reconciliation and interval/status logic; inspect Mike Curtis, Morrow, Boyd, party/chamber/era subgroups, singleton behavior, fallback races, and deterministic hashes; run focused tests and workflow validation.
- Handoff recipient: `orchestrator`
- Known risks: Sparse repeat candidates, partially connected candidate networks, fallback baseline comparability, and retrospective full-panel estimates must remain explicit.
