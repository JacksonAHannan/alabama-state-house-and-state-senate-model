# Task contract: CMO-CQI-V5-001

- Accountable role: `cmo_model`
- Owner: `/root`
- Status: `complete`
- Objective: Replace the structurally over-residualized CMO v4 with a dual-estimand v5 product: direct source-aware ticket overperformance and a partially pooled Candidate Quality Index selected for repeat/future candidate validity.
- Non-goals: Change canonical election returns, geography, candidate identities, ideology evidence, the 2026 forecast, or public site files before model validation.
- Upstream snapshot: Canonical election feature/candidate exports and approved CMO v3/v4 audit products as of commit `b734871`.
- Read scope: `data/processed/elections/canonical_cmo_*.csv`; `data/processed/elections/historical_federal_district_baselines.csv`; `data/processed/war/cmo_v3_*`; `data/processed/war/cmo_v4_*`; `scripts/rebuild_cmo_methodology_v2.py`; existing CMO tests and documentation.
- Write scope: `scripts/rebuild_cmo_candidate_quality_v5.py`; `scripts/tests/test_cmo_candidate_quality_v5.py`; `data/processed/war/cmo_v5_*.csv`; `project_docs/model/CMO_METHODOLOGY_V5.md`; `project_docs/coordination/CMO-CQI-V5-001.md`; `project_docs/coordination/active_tasks.csv`.
- Warehouse mode: `read-only`
- Inputs: Canonical contested D–R race/candidate panel, source-aware state/federal/presidential ticket baselines, incumbency flags, predetermined presidential history, and demographics.
- Outputs: Race and candidate scores, candidate effects, structural components, model tournament, repeat/future validation, case-study audit, uncertainty/reliability fields, and provenance manifest.
- Acceptance checks: Direct CMO exactly reconciles to legislative minus selected ticket baseline; no lag predictor algebraically reuses the current selected baseline; candidate quality is partial-pooled and its Democratic-minus-Republican race differential reconciles to the two candidate effects; tournament includes direct, cycle-centered, and hierarchical alternatives and prioritizes held-out repeat-candidate prediction; Mike Curtis remains positive on direct CMO and is not labeled deterministically bad when CQI uncertainty crosses zero; forward-cycle, party-symmetry, transition, and case-study diagnostics are published; deterministic tests pass.
- Handoff recipient: `validation_release`
- Known risks: Candidate and opponent effects are only jointly identified; most candidates are singletons; older baselines and prior presidential history have uneven coverage; CQI must expose shrinkage and uncertainty rather than imply precision.
