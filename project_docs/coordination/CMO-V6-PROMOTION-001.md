# Task contract: CMO-V6-PROMOTION-001 — promote the Southern-prior decomposition

- Accountable role: `cmo_model`
- Owner: `/root`
- Status: `complete`
- Objective: Promote the independently validated v6 Southern-prior decomposition as the current historical CMO research product while preserving Direct CMO exactly.
- Non-goals: Do not use the v6 structural expectation as a direct 2026 forecast adjustment and do not alter canonical election observations.
- Upstream snapshot: Validated 2,402-race Southern panel build `7046318246201891028d`, CMO v5 inputs, and `CMO_ALABAMA_SOUTHERN_PRIOR_V6_VALIDATION.md`.
- Read scope: `data/processed/war/cmo_v5_*`; `data/processed/war/extended_v2_historical_southern/`; `project_docs/audits/CMO_ALABAMA_SOUTHERN_PRIOR_V6_VALIDATION.md`.
- Write scope: `scripts/rebuild_cmo_southern_prior_v6.py`; `data/processed/war/cmo_v6_southern_*`; `project_docs/model/CMO_METHODOLOGY_V6_SOUTHERN_PRIOR.md`; `project_docs/coordination/CMO-V6-PROMOTION-001.md`.
- Warehouse mode: `read-only`
- Inputs: Validated v5 CMO race/candidate outputs and Alabama-excluded Southern structural tournament.
- Outputs: Versioned v6 race, candidate, quality, validation, case-study, and manifest files plus current methodology documentation.
- Acceptance checks: Direct CMO is invariant to v5 within `1e-12`; all output keys are unique; decomposition identities hold; `python -m pytest scripts/tests/test_cmo_southern_prior_v6.py -q` passes.
- Handoff recipient: `forecast_model`
- Known risks: The pre-2016 Southern expectation fails the modern-era promotion gate and must remain historical decomposition only.
