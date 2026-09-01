# Task contract: CMO-SOUTHERN-WAR-RESIDUAL-042 — publish race-residual WAR

- Accountable role: `cmo_model`
- Owner: `/root`
- Status: `review`
- Objective: Recalculate every strict post-2016 Southern WAR race as the observed legislative-versus-ticket gap minus the fitted structural gap, matching Split Ticket's published residual definition.
- Non-goals: Do not overwrite v1 or v2; do not call a pooled cross-race candidate coefficient WAR; do not promote incomplete fundraising; do not modify warehouse facts or publish to `docs/`.
- Upstream snapshot: Current warehouse run `RUN-4ED478C647B34A7B9A402970625DB334`; v2 research run `WAR-POST2016-V2-40C209C46EC572EF8278` retained only as a correction comparison and methodology/code dependency.
- Read scope: `mart_southern_war_training_with_finance`; validated prior-presidential context; v2 model code and artifacts; Split Ticket's published WAR methodology.
- Write scope: `scripts/retrain_post2016_southern_war_v3.py`; `scripts/tests/test_post2016_southern_war_v3.py`; `data/processed/war/post2016_southern_war_v3/`; `project_docs/model/POST2016_SOUTHERN_WAR_V3.md`; `project_docs/model/POST2016_SOUTHERN_WAR_V3_FIELD_CONTRACT.md`; `project_docs/audits/POST2016_SOUTHERN_WAR_V3_VALIDATION.md`; `project_docs/coordination/CMO-SOUTHERN-WAR-RESIDUAL-042.md`.
- Warehouse mode: `read-only`
- Inputs: Strict WAR-ready races with `cycle > 2016`, validated ticket and incumbency context, exact-key prior-presidential context where available, and the v2-selected `decaying_lag` structural specification.
- Outputs: One race-level WAR record per eligible contest; two party-oriented candidate-cycle records per race; structural diagnostics; finance sensitivity diagnostics; v2 correction comparison; content-addressed manifest.
- Acceptance checks: `war = direct_overperformance - fitted_structural_expected_gap`; Democratic and Republican candidate-cycle WAR values are exact opposites; no candidate-effect ridge shrinkage enters WAR; every race key is unique; all expected races reconcile; missing context remains explicit; inputs, code, outputs, and reports are hash registered; focused and regression tests run.
- Handoff recipient: `validation_release`
- Known risks: This is Split Ticket-style rather than an exact federal-model reproduction because state-legislative demographic coverage and comparable candidate-plus-outside spending are incomplete. Same-sample fitted residuals are descriptive post-election scores, not out-of-sample forecasts.

## Handoff

- Research-candidate run: `WAR-POST2016-V3-D9C7EE17BD14B8C7D23A`.
- Coverage: 3,658 strict post-2016 races across 14 states and 7,316 party-oriented candidate-cycle rows.
- Definition: `war = raw_gap - fitted_structural_expected_gap`; no pooled candidate effect or second-stage penalty enters WAR.
- Example: Dexter Grimsley has raw gap `D+18.590`, fitted structural expectation `D+5.295`, and corrected WAR `D+13.295`. His self-excluded validation residual is separately labeled `D+14.431`.
- Validation: focused v3 tests passed (5); combined WAR/warehouse regression tests passed (36); full suite produced 641 passes and one independently reproducible historical-finance fixture failure outside this task's write scope (`352` expected complete rows versus `353` observed).
- Review request: independently audit same-cycle structural fits, lag contributions, extreme residuals, context coverage, and uncertainty before promotion.
