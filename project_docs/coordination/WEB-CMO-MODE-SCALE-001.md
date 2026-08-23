# Task contract: WEB-CMO-MODE-SCALE-001 - mode-specific CMO map and detail display

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Give residual candidate quality a visually distinct map scale and make the selected-candidate headline measure follow the active map view.
- Non-goals: No changes to CMO, candidate-quality, governor, presidential, election, or warehouse calculations.
- Upstream snapshot: Commit `a9773a9` and the current generated CMO payload.
- Read scope: `scripts/build_war_story_page.py`; current generated CMO page; relevant web tests.
- Write scope: `scripts/build_war_story_page.py`; `scripts/tests/test_cmo_story_historical_cycles.py`; generated CMO output under `artifacts/site/` and `docs/`; this contract.
- Warehouse mode: `read-only`.
- Inputs: Approved CMO v6 candidate payload embedded by the existing builder.
- Outputs: Mode-specific map legends/palettes and synchronized candidate headline values/labels.
- Acceptance checks: `python scripts/build_blue_oxblood_site.py`; focused web tests pass; browser checks verify each map mode changes both map scale and selected-candidate headline without runtime errors.
- Handoff recipient: `validation_release`.
- Known risks: Candidate values are party-oriented while some map values are district Democratic differentials; labels must state orientation clearly and missing values must not become zero.

## Handoff

- Completed: 2026-08-23
- Changed: Added mode-specific map configurations, a separate residual-quality palette and ±20-point scale, synchronized selected-candidate headline values and labels, correct party orientation, ordinal labels, and explicit unavailable states.
- Generated: Refreshed `docs/cmo.html` and the tracked CMO site artifact.
- Checks: Focused tests passed 16/16; 4,072 candidate-by-mode combinations matched their expected headline value with zero mobile overflow; independent validation passed at desktop, 497 px, and 390 px.
- Caveats: The current payload has no missing governor comparisons, but the shared missing-value branch was validated with presidential gaps and does not coerce null to zero.
