# Task contract: WEB-CMO-VISUAL-FIX-001 — CMO scale and contrast repair

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Repair CMO-page scale overlap and replace remaining white-on-light-blue boxes with readable blue/oxblood treatments.
- Acceptance checks: Desktop and mobile browser inspection shows no scale/control overlap; all white text meets contrast against its computed background; CMO map, candidate details, wikiboxes, selectors, and timelines remain functional; focused tests and independent validation pass.
- Read scope: Current CMO builder, shared Blue/Oxblood theme, generated CMO page, and web tests.
- Write scope: `scripts/build_war_story_page.py`; `dashboard/blue_oxblood_theme.css`; relevant web tests; generated files under `artifacts/site/`, `artifacts/blue_oxblood_site/`, and `docs/`; `project_docs/coordination/WEB-CMO-VISUAL-FIX-001.md`.
- Upstream inputs: Commit `6d0fd3c` and the currently served generated site.
- Expected outputs: Corrected CMO page and repeatable browser/contrast validation.
- Warehouse access: read-only.
- Handoff recipient: `validation_release`.

## Handoff

- Completed: 2026-08-23
- Changed: CMO scale geometry, narrow-screen detail containment, oxblood wikibox headers, and focused regression tests.
- Generated: refreshed public pages under `docs/` and the CMO site artifact.
- Checks: focused web suite passed 16/16; exact-width browser sweep across all 1,018 candidate observations found no marker/label collisions or mobile overflow; independent validation passed.
- Caveats: none for this visual repair. The local preview server remains the review target until a separate publication request.
