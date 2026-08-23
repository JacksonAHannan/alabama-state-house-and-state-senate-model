# Task contract: FORECAST-POST2016-HEADLINE-001 — publishable post-2016 headline forecast

- Accountable role: `forecast_model`
- Owner: `/root`
- Status: `complete`
- Objective: Convert the approved post-2016 polling-CMO experiment into a deterministic headline forecast package with Democratic- and Republican-favorable national polling-error scenarios.
- Non-goals: Do not change canonical election, roster, finance, polling, or warehouse data; do not publish `docs/` in this task; do not retune the model after viewing 2026 seat outcomes.
- Upstream snapshot: Post-2016 polling-CMO build `30d4e3967a7bbc38700e`, current polling through 2026-08-17, and robust-v1 national polling-error and chamber uncertainty estimates.
- Read scope: `data/processed/forecast_calibration/post2016_polling_cmo_*`; `data/processed/forecast_calibration/robust_forecast_v1_*`; `data/processed/war/2026_final_candidate_roster.csv`; `scripts/run_post2016_polling_cmo_forecast.py`.
- Write scope: `scripts/promote_post2016_headline_forecast.py`; `data/processed/forecast_calibration/post2016_headline_v1_*`; `project_docs/model/POST2016_HEADLINE_FORECAST_V1.md`; `project_docs/coordination/FORECAST-POST2016-HEADLINE-001.md`.
- Warehouse mode: `read-only`
- Inputs: The nine-scenario experimental forecast, its manifest and forward metrics, the selected within-cycle orthogonal fundraising specification, and robust-v1 polling-error/uncertainty components.
- Outputs: Three 48-race public forecast views, headline uncertainty, chamber seat distributions, public model metrics, and a hashed manifest.
- Acceptance checks: Headline equals the full within-cycle orthogonal specification; scenario margins equal headline plus or minus one historical national polling-error standard deviation; all views contain the same 48 unique races; probabilities and intervals reconcile; missing finance remains missing; builds are deterministic.
- Handoff recipient: `web_product`
- Known risks: One Alabama forward holdout supports the candidate adjustment; historical finance is full-cycle rather than cutoff-aligned; the promotion is an editorial choice explicitly requested by the project owner.

## Handoff

- Build `e178fb3f50c98c9c312b` contains three 48-race views and preserves missing finance for five races.
- The Democratic- and Republican-favorable views are exactly ±2.20385 margin points from the headline.
- Headline uncertainty and modeled-seat distributions use 50,000 reproducible simulations.
- Downstream consumer: `WEB-PUBLIC-HEADLINE-COPY-001`.
