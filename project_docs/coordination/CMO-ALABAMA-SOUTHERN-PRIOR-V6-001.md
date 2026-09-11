# Task contract: CMO-ALABAMA-SOUTHERN-PRIOR-V6-001

- Accountable role: `cmo_model`
- Owner: `/root`
- Status: `complete`
- Objective: Build an Alabama CMO v6 research candidate that uses the independently validated Southern panel to estimate generic down-ballot lag and incumbency before attributing the remaining differential to candidates.
- Non-goals: No canonical warehouse, production forecast, website, or publication changes; Direct CMO is not redefined.
- Upstream snapshot: Validated 2,402-row Southern panel and tournament build `7046318246201891028d`; current Alabama CMO v5 inputs and identities.
- Read scope: V2 Southern panel/manifest/tournament; CMO v5 code and outputs; Alabama CMO source marts.
- Write scope: `scripts/rebuild_cmo_southern_prior_v6.py`; `scripts/tests/test_cmo_southern_prior_v6.py`; `data/processed/war/cmo_v6_southern_*`; `project_docs/model/CMO_METHODOLOGY_V6_SOUTHERN_PRIOR.md`; `project_docs/coordination/CMO-ALABAMA-SOUTHERN-PRIOR-V6-001.md`.
- Warehouse mode: `read-only`
- Inputs: Validated Southern structural sample and current Alabama race/candidate observations.
- Outputs: Race- and candidate-level research tables, external-prior diagnostics, generic incumbency decomposition, validation comparison, and deterministic provenance.
- Acceptance checks: Direct CMO exactly matches v5; Southern expectation is fitted without Alabama; expected and incumbent-neutral gaps are finite for eligible races; candidate residuals are D/R symmetric; generic incumbency is separately visible; all joins are cardinality-checked; Mike Curtis and Barbara Boyd cases are audited; missing values are not converted to zero; focused tests pass.
- Handoff recipient: `forecast_model` only after a model comparison, then `validation_release` before promotion.
- Known risks: Cross-state baselines use different offices and source quality; only 52 Alabama rows occur in the Southern panel; historical Alabama source definitions differ by cycle.
