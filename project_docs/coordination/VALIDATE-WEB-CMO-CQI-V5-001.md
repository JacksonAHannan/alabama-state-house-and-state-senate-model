# Task contract: VALIDATE-WEB-CMO-CQI-V5-001

- Accountable role: `validation_release`
- Owner: `/root/blue_oxblood_validation`
- Status: `complete`
- Objective: Independently validate the CMO v5 public explorer, methodology, exports, visual contract, and absence of legacy v4 artifacts.
- Non-goals: Edit the model, canonical data, site builder, or published pages.
- Upstream snapshot: Validated CMO v5 model and `WEB-CMO-CQI-V5-001` release candidate.
- Read scope: `scripts/build_war_story_page.py`; focused site tests; v5 model outputs; `artifacts/site/alabama-legislative-cmo.html`; `docs/cmo.html`; `docs/cmo-methodology.html`; `docs/data/cmo_v5_*.csv`; shared blue/oxblood site styles.
- Write scope: `project_docs/audits/WEB_CMO_CQI_V5_VALIDATION.md`; `project_docs/coordination/VALIDATE-WEB-CMO-CQI-V5-001.md`; `project_docs/coordination/active_tasks.csv`.
- Warehouse mode: `read-only`
- Inputs: Web release candidate and independently approved v5 outputs.
- Outputs: PASS/FAIL release audit.
- Acceptance checks: Public exports byte-match v5; default map/ranking arithmetic uses direct CMO; quality view uses D-minus-R CQI; detail and table show interval/status/reliability/appearances/pre-election estimate; raw governor and prior-presidential views persist; Mike Curtis values and status match v5; methodology matches implementation; v4 residual language and v4 links are absent; HTML/JS payload parses; focused tests and workflow validation pass; blue/oxblood readability and navigation checks pass.
- Handoff recipient: `orchestrator`
- Known risks: Embedded payload size, legacy string-replacement code, historical encoding artifacts, and sparse-quality interpretation.
