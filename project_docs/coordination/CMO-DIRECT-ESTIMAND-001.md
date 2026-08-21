# Task contract: CMO-DIRECT-ESTIMAND-001

- Accountable role: `cmo_model`
- Owner: `/root`
- Status: `complete`
- Objective: Replace the extrapolative context-residual headline with a source-aware direct ticket-overperformance CMO, tournament defensible ticket baselines and reliability shrinkage, and retain regression-based expectations only as diagnostics.
- Acceptance checks: Morrow's 1998 HD-18 score reconciles to the observed legislative and ticket margins; every score has an auditable arithmetic decomposition; candidate scores remain zero-sum within races; baseline alternatives are evaluated out of cycle; pathological extrapolation diagnostics are reported; model and focused tests pass.
- Read scope: `data/processed/elections/`; `data/processed/war/`; historical CMO scripts and documentation.
- Write scope: `scripts/rebuild_cmo_direct_estimand.py`; `scripts/tests/test_cmo_direct_estimand.py`; `data/processed/war/cmo_v3_*`; `project_docs/model/CMO_METHODOLOGY_V3.md`; `project_docs/coordination/CMO-DIRECT-ESTIMAND-001.md`; its active-task ledger row.
- Upstream inputs: Canonical candidate/race observations, corrected same-district statewide and federal baselines, source-quality fields, and CMO v2 diagnostics.
- Expected outputs: Versioned race/candidate scores, baseline tournament, pathology audit, provenance manifest, and methodology report.
- Warehouse mode: read-only.
- Non-goals: No canonical warehouse mutation or public-site publication in this task.
- Handoff recipient: `validation_release` and downstream ideology/web tasks.
