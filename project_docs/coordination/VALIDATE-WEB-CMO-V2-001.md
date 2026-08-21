# Task contract: VALIDATE-WEB-CMO-V2-001 independently validate CMO v2 publication

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently assess the staged CMO v2 public dashboard and methodology for numerical fidelity, terminology, interaction integrity, stale artifacts, accessibility/contrast, and release readiness.
- Acceptance checks: Public candidate values match `cmo_v2_candidates.csv`; all four estimands remain distinct; all 16 cycle/chamber controls and seven map modes are present; maps, row selection, race wiki-box, and baseline toggles are structurally functional; no legacy Fundamentals+ claims remain; methodology agrees with the approved model card; HTML/JS and focused/full tests pass; report a clear PASS or FAIL with actionable findings.
- Read scope: `data/processed/war/cmo_v2_*`; `project_docs/model/CMO_MODEL_CARD.md`; `project_docs/audits/CMO_METHODOLOGY_V2_VALIDATION.md`; `scripts/build_war_story_page.py`; `docs/cmo.html`; `docs/cmo-methodology.html`; relevant tests and shared theme.
- Write scope: `project_docs/audits/CMO_V2_PUBLICATION_VALIDATION.md`; this contract and its active-task row only.
- Warehouse mode: read-only.
- Upstream inputs: Review candidate from `WEB-CMO-V2-001` and independently approved CMO v2 model outputs.
- Expected output: Independent validation report with checks, evidence, caveats, and release verdict.
- Handoff recipient: `/root`.

## Handoff

- Outcome: `PASS`
- Remediation gates passed: exact 497 px CMO containment; identity cautions only
  on the 387 surname-only unresolved rows; all fragment/local links resolve;
  focused 12/12 tests; real map and console checks.
- Final blocker checks: dashboard and builder use chamber-cycle median; all 63
  2010 Governor contexts name Ron Sparks and Robert Bentley; all 63 2010
  Attorney General contexts name James H. Anderson and Luther Strange.
- Changed implementation/public/model files: none.
- Generated output: `project_docs/audits/CMO_V2_PUBLICATION_VALIDATION.md`.
- Downstream invalidation: none.
- Next action: web owner may publish the approved staged pages.
