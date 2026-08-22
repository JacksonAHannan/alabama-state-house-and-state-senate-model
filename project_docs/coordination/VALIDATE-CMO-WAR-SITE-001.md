# Task contract: VALIDATE-CMO-WAR-SITE-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently validate that the rebuilt CMO and ideology pages publish the approved v4 WAR-style residual, component definitions, versioned downloads, and limitations without stale v3 scores or prose.
- Acceptance checks: Public candidate and race exports byte-match v4 outputs; page payload arithmetic agrees with v4; Barbara Boyd no longer carries the stale score; no headline v3/direct/within-context claims remain; methodology matches implementation; focused publication tests pass.
- Read scope: `scripts/build_war_story_page.py`; `scripts/build_ideology_thesis_page.py`; relevant tests; `data/processed/war/cmo_v4_*`; `docs/cmo.html`; `docs/cmo-methodology.html`; `docs/ideology-performance.html`.
- Write scope: `project_docs/audits/CMO_WAR_SITE_VALIDATION.md`; this contract; its ledger row.
- Upstream inputs: `CMO-WAR-ANALOGUE-001`, `IDEO-CMO-WAR-001`, and the current web release candidate.
- Expected outputs: Independent PASS/FAIL release report with blocking discrepancies and clearly identified nonblocking limitations.
- Warehouse mode: read-only.
