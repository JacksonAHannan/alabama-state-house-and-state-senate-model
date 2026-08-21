# Task contract: IDEO-CMO-V3-001

- Accountable role: `legislative_ideology`
- Owner: `/root`
- Status: `complete`
- Objective: Rebuild all ideology estimates and graphics using direct ticket CMO v3.
- Acceptance checks: All 1,018 panel scores match v3 by candidate ID; no context score enters an ideology outcome; focused tests pass.
- Read scope: `data/processed/war/cmo_v3_*`; canonical ideology evidence; existing absolute analysis.
- Write scope: `scripts/analyze_absolute_ideology_rebuild.py`; `tests/test_absolute_ideology_rebuild.py`; `research/cmo_ideology/absolute_rebuild_*`; `project_docs/model/ABSOLUTE_IDEOLOGY_REBUILD.md`; this contract; its ledger row.
- Upstream inputs: Independently validated CMO v3 outputs.
- Expected outputs: Rebuilt analysis panel, estimates, audits, and report.
- Warehouse mode: read-only.
- Handoff recipient: `validation_release` and `web_product`.
