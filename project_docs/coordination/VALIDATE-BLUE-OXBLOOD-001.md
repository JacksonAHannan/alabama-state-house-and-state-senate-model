# Task contract: VALIDATE-BLUE-OXBLOOD-001 independent release validation

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently validate the Blue/Oxblood public-site release candidate and issue a documented pass/fail release decision.
- Non-goals: Do not modify implementation files, model outputs, warehouse tables, public pages, or data. Do not fix discovered defects; report them with reproducible evidence.
- Upstream snapshot: `WEB-LIVE-BRAND-001` review candidate as built on 2026-08-21.
- Read scope: `dashboard/blue_oxblood_theme.css`; `scripts/site_brand.py`; `scripts/build_blue_oxblood_site.py`; `scripts/tests/test_site_brand.py`; all current public builders and tests; `docs/`; `artifacts/blue_oxblood_site/`; current Git diff and status.
- Write scope: `project_docs/audits/BLUE_OXBLOOD_RELEASE_VALIDATION.md`; `scripts/tests/test_legislator_ideology_page.py`; this contract and its active-task row only.
- Warehouse mode: read-only.
- Inputs: Six themed public HTML pages, existing publication outputs, existing model payloads, current tests, and the `WEB-LIVE-BRAND-001` handoff.
- Outputs: Independent validation report with exact commands, test results, functional checks, regressions, unrelated failures, and a clear `PASS`, `PASS WITH NON-BLOCKING FINDINGS`, or `FAIL` decision.
- Acceptance checks: Rebuild reproducibility; focused and relevant regression tests; script/payload preservation; no placeholder geography; actual forecast and CMO maps; chamber/cycle/district control behavior; desktop/mobile rendering; internal navigation; remote-font and console-error audit; no model-data change attributable to branding; review of the Vote Smart 4-versus-5 assertion.
- Handoff recipient: `/root` for release or remediation.
- Known risks: Dirty worktree with extensive unrelated user work, large embedded payloads, network-dependent Leaflet basemap tiles, and a pre-existing stale Vote Smart count assertion.

## Handoff

- Outcome: `blocked release`
- Upstream snapshot used: `WEB-LIVE-BRAND-001` review candidate, 2026-08-21
- Changed source files: none
- Generated outputs: `project_docs/audits/BLUE_OXBLOOD_RELEASE_VALIDATION.md`
- Commands run: workflow validator; complete Blue/Oxblood rebuild with
  before/after SHA-256 comparison; 36 focused/relevant tests; full 359-test
  suite; JavaScript compilation; remote-font scan; Selenium desktop/mobile,
  console, navigation, map, and interaction checks.
- Validation results: deterministic rebuild; actual Leaflet and SVG maps and
  controls passed; internal links and console passed; 358 full-suite tests
  passed. Release failed because the legislator page visibly says four Vote
  Smart profiles while its payload has five, the corresponding test fails, and
  the CMO page has 87 px of document-level mobile overflow at the tested width.
- Manual decisions: none
- Assumptions and limitations: network basemap tiles were allowed; favicon-only
  console noise was excluded; headless Chrome reported an effective 497 px
  client width for the requested 430 px window.
- Warehouse changes requested: none
- Downstream invalidation: rebuild all six public pages after the two web-layer
  corrections; model outputs remain valid.
- Reviewer: `/root/blue_oxblood_validation` (`validation_release`)
- Next action: web owner corrects Vote Smart count copy/test and mobile CMO
  `.model-status` responsiveness, then requests revalidation.

## Revalidation handoff

- Outcome: `blocked release`
- Upstream snapshot used: remediated `WEB-LIVE-BRAND-001`, 2026-08-21
- Changed source files: `scripts/tests/test_legislator_ideology_page.py`
- Generated outputs: `project_docs/audits/BLUE_OXBLOOD_RELEASE_VALIDATION.md`
- Validation results: Vote Smart copy/payload/test now consistently report five;
  deterministic rebuild passed; focused suite 36/36; full suite 359/359; all
  maps, controls, links, scripts, fonts, and console checks passed. Release
  remains blocked because CMO is 539 px wide at a 497 px client width; ideology
  is 513 px wide.
- Manual decisions: updated the stale assertion to the independently verified
  current payload value of five, as explicitly authorized by the orchestrator.
- Warehouse changes requested: none
- Downstream invalidation: rebuild site after responsive containment fixes only.
- Reviewer: `/root/blue_oxblood_validation` (`validation_release`)
- Next action: web owner constrains CMO validation-grid children and ideology
  era-row values at mobile widths, then requests final revalidation.

## Final validation handoff

- Outcome: `accepted candidate`
- Upstream snapshot used: final responsive `WEB-LIVE-BRAND-001`, 2026-08-21
- Changed source files: none during final gate
- Generated outputs: `project_docs/audits/BLUE_OXBLOOD_RELEASE_VALIDATION.md`
- Validation results: deterministic rebuild; focused 36/36; full suite 359/359;
  zero overflow on all six pages at exact 497 px effective client width; maps,
  controls, links, JavaScript, local-font contract, portrait, and console passed.
- Manual decisions: none during final gate
- Warehouse changes requested: none
- Downstream invalidation: none
- Reviewer: `/root/blue_oxblood_validation` (`validation_release`)
- Next action: orchestrator may commit and push the approved candidate.

## Reproducibility addendum handoff

- Outcome: `accepted candidate`
- Validation results: two complete wrapper runs produced identical hashes for
  all six pages, matching the approved hashes; all six pages again measured
  497 px scroll width at a 497 px effective client width.
- Reviewer: `/root/blue_oxblood_validation` (`validation_release`)
- Next action: PASS stands; orchestrator may commit and publish.
