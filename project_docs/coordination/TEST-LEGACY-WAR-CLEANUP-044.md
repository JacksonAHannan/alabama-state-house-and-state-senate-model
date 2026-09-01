# Task contract: TEST-LEGACY-WAR-CLEANUP-044 — retire superseded WAR tests

- Accountable role: `validation_release`
- Owner: `/root`
- Status: `complete`
- Objective: Remove low-utility tests that assert superseded WAR, public story, or forecast behavior after promotion of Alabama residual WAR and the generic-candidate forecast.
- Non-goals: Do not remove tests for current Alabama WAR, the generic-candidate forecast, publication consistency, warehouse contracts, or v5/v6 outputs that remain inputs to ideology and historical research; do not delete source data or generated model runs.
- Upstream snapshot: Published release commit `42e2ad1`; Alabama WAR run `AL-WAR-V1-E1F8E11BF2853322239F`; forecast build `4a24f61e28a3d5987062`.
- Read scope: WAR/CMO/forecast tests, their script imports, current site builders, downstream references to historical v5/v6 artifacts, and pytest collection.
- Write scope: `scripts/tests/test_post2016_southern_war.py`; `scripts/tests/test_post2016_southern_war_v2.py`; `scripts/tests/test_cmo_war_analogue.py`; `scripts/tests/test_cmo_story_historical_cycles.py`; `scripts/tests/test_post2016_polling_cmo_forecast.py`; this contract.
- Warehouse mode: `none`
- Acceptance checks: Current WAR, forecast, dashboard, publication, and branding tests pass; remaining v5/v6 tests pass; pytest no longer collects assertions that pooled individual effects are WAR or that the retired forecast/story is public; workflow validation passes.
- Handoff recipient: `validation_release`
- Known risks: Historical scripts remain available for reproducibility, but their retired presentation-specific behavior will no longer have dedicated regression coverage.

## Completion

- Removed 26 collected tests across five superseded suites: Southern WAR v1/v2, CMO v4 WAR analogue, the retired historical CMO story interface, and the replaced polling/CMO forecast.
- Retained v5/v6 compatibility tests because those artifacts remain inputs to ideology and historical research.
- Focused validation: 59 passed.
- Broad validation: 620 passed with the previously documented stale historical-finance fixture excluded; workflow validation passed.
