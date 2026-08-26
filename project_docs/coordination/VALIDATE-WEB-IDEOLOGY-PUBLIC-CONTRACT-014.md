# Task contract: VALIDATE-WEB-IDEOLOGY-PUBLIC-CONTRACT-014

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Replace the obsolete two-bloc ideology assertions in the publication-consistency test with the independently approved three-group WAR-first contract.
- Acceptance checks: Test requires the current title, WAR-first section order, three group labels, Split Ticket attribution, absence of public CQI labels and legacy 3D/Candidate Atlas artifacts, and the caucus compatibility redirect; focused publication test passes against the approved candidate once published.
- Read scope: Approved `VALIDATE-WEB-IDEOLOGY-WAR-012` report, current page builder/artifact, and `scripts/tests/test_published_site_consistency.py`.
- Write scope: `scripts/tests/test_published_site_consistency.py`; `project_docs/coordination/VALIDATE-WEB-IDEOLOGY-PUBLIC-CONTRACT-014.md`; `project_docs/coordination/active_tasks.csv`.
- Upstream inputs: Approved WAR-first release candidate SHA `74D66315684355098892DCB142999CA95F7E526B160460179EB9C90248F9C16E`.
- Expected outputs: Updated release test expressing the approved public contract and task handoff.
- Warehouse mode: `read-only`
- Handoff recipient: `WEB-IDEOLOGY-WAR-PUBLISH-012`.

## Handoff

- Updated only `test_public_ideology_and_caucus_routes_are_merged` in `scripts/tests/test_published_site_consistency.py`.
- The contract now requires the current `Alabama Democratic groupings, 1998–2022` title; WAR-first section order; traditionalist, bridge, and progressive groups; schema version 2 with the stable internal `candidate_quality_index`; Split Ticket attribution and URL; absence of public CQI, Candidate Atlas, and legacy 3D artifacts; and the existing caucus compatibility redirect.
- The test function passes when evaluated against approved artifact SHA `74D66315684355098892DCB142999CA95F7E526B160460179EB9C90248F9C16E` plus the current caucus redirect.
- `python -m py_compile scripts/tests/test_published_site_consistency.py` and workflow validation pass.
- The unmodified current `docs/` copy correctly fails the new ideology contract because publication has not occurred. The complete publication module also currently reports a separate pre-existing forecast-export byte mismatch; that finding is outside this task's test-only write scope.
- Ready for `WEB-IDEOLOGY-WAR-PUBLISH-012` to publish the approved artifact and rerun the focused publication module.
