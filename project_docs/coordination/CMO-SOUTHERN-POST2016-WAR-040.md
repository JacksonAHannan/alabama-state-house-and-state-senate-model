# Task contract: CMO-SOUTHERN-POST2016-WAR-040 — retrain WAR on the modern Southern warehouse

- Accountable role: `cmo_model`
- Owner: `/root`
- Status: `review`
- Objective: Fit and validate a versioned Southern candidate WAR model using only strict-ready warehouse races with election cycles after 2016.
- Non-goals: Do not modify canonical warehouse facts, use research-only rows, add finance to the headline estimand, overwrite Alabama-only WAR outputs, or publish to `docs/`.
- Upstream snapshot: Validated Southern WAR preparation run `RUN-7EACF4A3805E4328A3DE0A361051AF35` in `data/processed/elections/alabama_elections.sqlite`.
- Read scope: `mart_southern_war_training_no_finance`; `warehouse_build_run`; existing v5 WAR implementation and methodology.
- Write scope: `scripts/retrain_post2016_southern_war.py`; `scripts/tests/test_post2016_southern_war.py`; `data/processed/war/post2016_southern_war/`; `project_docs/model/POST2016_SOUTHERN_WAR.md`; `project_docs/audits/POST2016_SOUTHERN_WAR_VALIDATION.md`; `project_docs/coordination/CMO-SOUTHERN-POST2016-WAR-040.md`.
- Warehouse mode: `read-only`
- Inputs: Strict-ready finance-free D-versus-R outcomes where `cycle > 2016`, including observed ticket context and accepted incumbency.
- Outputs: Race scores, candidate-cycle scores, candidate effects, time-forward diagnostics, coverage, and a content-addressed run manifest.
- Acceptance checks: Input rows all have `cycle > 2016` and strict status; race keys and candidate-cycle keys are unique; exactly one D and one R score is emitted per race; D/R candidate-oriented values are symmetric; replacement residuals center within declared groups; time-forward folds train only on earlier cycles; manifest hashes reproduce; targeted tests and the full suite pass.
- Handoff recipient: `validation_release`
- Known risks: Cross-state longitudinal candidate identity is model-local and name-based because the warehouse does not yet expose a Southern person bridge; singleton candidate pairs identify only a differential; the short 2018–2024 window limits repeat-candidate validation.

## Handoff

- Model run: `WAR-POST2016-3E87657081BBBCB16754`.
- Training sample: 3,658 strict-ready races, 7,316 candidate-cycle rows, 5,869 model-local candidate effects, 14 states, and strict cycles 2018, 2019, 2020, 2022, 2023, and 2024.
- Selected fit: candidate ridge penalty 1; time-forward MAE on 1,239 held-out races with a previously observed candidate is 4.214 points versus 4.745 for a zero prior-candidate effect.
- Checks: 5 focused tests passed; 24 combined WAR/preparation/legacy CMO tests passed; workflow validation and bytecode compilation passed.
- Full-suite caveat: the same unrelated historical-finance fixture failure documented before this task remains (`352` expected complete races versus `353` produced). No post-2016 WAR test failed.
- Publication: none. The run remains a research candidate pending independent validation.
