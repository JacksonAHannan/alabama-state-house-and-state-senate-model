# Task contract: IDEO-CMO-WAR-001

- Accountable role: `legislative_ideology`
- Owner: `/root`
- Status: `active`
- Objective: Rebuild ideology analysis using the validated WAR-style structural residual as CMO while retaining federal and presidential raw-baseline outcomes separately.
- Acceptance checks: All candidate CMO values reconcile to v4 by stable ID; labels distinguish WAR residual from raw ticket overperformance; focused tests pass; non-persistence limitation is retained.
- Read scope: `data/processed/war/cmo_v4_*`; canonical ideology evidence; existing absolute ideology pipeline.
- Write scope: `scripts/analyze_absolute_ideology_rebuild.py`; `tests/test_absolute_ideology_rebuild.py`; `research/cmo_ideology/absolute_rebuild_*`; `project_docs/model/ABSOLUTE_IDEOLOGY_REBUILD.md`; this contract; its ledger row.
- Upstream inputs: Independently validated `CMO-WAR-ANALOGUE-001` outputs.
- Expected outputs: Rebuilt ideology panel, estimates, diagnostics, and report.
- Warehouse mode: read-only.
- Handoff recipient: `validation_release` and `web_product`.
