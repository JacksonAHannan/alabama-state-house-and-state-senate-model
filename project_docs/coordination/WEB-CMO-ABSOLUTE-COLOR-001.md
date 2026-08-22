# Task contract: WEB-CMO-ABSOLUTE-COLOR-001

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Make CMO map color intensity a direct linear function of the absolute point value displayed in the legend, rather than the current square-root transformation that visually behaves like a relative scale.
- Non-goals: Recalculate CMO, alter candidate/race scores, change comparison-view definitions, or modify canonical warehouse data.
- Upstream snapshot: Validated CMO v4 public payload and map at commit `81b04aa`.
- Read scope: `data/processed/war/cmo_v4_candidates.csv`; `data/processed/war/cmo_v4_races.csv`; current CMO page builder and tests.
- Write scope: `scripts/build_war_story_page.py`; `scripts/tests/test_cmo_story_historical_cycles.py`; `artifacts/site/alabama-legislative-cmo.html`; `docs/cmo.html`; `project_docs/coordination/WEB-CMO-ABSOLUTE-COLOR-001.md`; `project_docs/coordination/active_tasks.csv`.
- Warehouse mode: `read-only`
- Inputs: Approved CMO v4 candidate and race outputs.
- Outputs: Linear signed-point color function, consistent legend/note/tooltips, tests, and regenerated CMO page.
- Acceptance checks: A value of 15 receives exactly half the endpoint color interpolation used by 30; signs retain Democratic/Republican direction; zero remains neutral; all three map modes use their uncensored point values with a symmetric ±30 visual cap; labels no longer claim square-root scaling; focused tests and independent browser validation pass.
- Handoff recipient: `validation_release`
- Known risks: Extreme CMO values remain visually capped at 30 points, while tooltips must continue showing uncapped values.
