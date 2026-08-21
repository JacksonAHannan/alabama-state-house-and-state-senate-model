# Task contract: CMO-METHODOLOGY-V2-001 revised CMO estimands

- Accountable role: `cmo_model`
- Owner: `/root`
- Status: `complete`
- Objective: Implement and validate a revised CMO system that separates raw ticket overperformance, candidate-variable-free context-adjusted CMO, within-cycle CMO, and a fully predictive expected-performance model while addressing all ten approved methodological priorities.
- Non-goals: Do not mutate the canonical warehouse, raw sources, forecast probabilities, or public `docs/` pages in this task. Public migration will use a separate serialized web contract after model validation.
- Upstream snapshot: Commit `4bc17d8`; `canonical_cmo_features.csv`; `canonical_cmo_candidates.csv`; historical federal baselines; current Fundamentals+ and legacy CMO outputs.
- Read scope: `data/processed/elections/`; `data/processed/war/`; `research/cmo_ideology/`; current CMO and forecast scripts; current model documentation.
- Write scope: `scripts/rebuild_cmo_methodology_v2.py`; `scripts/tests/test_cmo_methodology_v2.py`; `data/processed/war/cmo_v2_`; `project_docs/model/CMO_METHODOLOGY_V2.md`; `project_docs/model/CMO_MODEL_CARD.md`; this contract and its active-task row.
- Warehouse mode: staging proposal.
- Inputs: 509 currently eligible 1994–2022 D/R legislative races plus candidate identities, finance, incumbency, demographic, statewide, federal, presidential, and geography-quality fields available at the frozen snapshot.
- Outputs: Versioned race and candidate scores; baseline ensemble diagnostics; nominal-contest tiers; margin/logit/robust specifications; nested forward predictions; crossed candidate/opponent estimates; race-specific uncertainty; repeat/successor/future construct-validity diagnostics; revised model report.
- Acceptance checks: No current-cycle candidate-derived variable enters headline context CMO; predictive model is separately labeled; every score retains raw and within-cycle versions; all outer-cycle predictions are generated without training-cycle leakage; candidate/opponent effects are constrained and partially pooled; uncertainty varies by race quality/specification; deterministic rebuild; schema/key/null checks; focused tests pass.
- Handoff recipient: `validation_release`, then `web_product`.
- Known risks: Sparse repeat candidates, changing office availability, nominal contests, historical geography quality, era-confounded feature coverage, and limited genuinely forward cycles.
