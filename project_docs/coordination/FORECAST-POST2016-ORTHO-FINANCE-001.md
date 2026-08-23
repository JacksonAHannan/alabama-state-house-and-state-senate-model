# Task contract: FORECAST-POST2016-ORTHO-FINANCE-001 — orthogonalized post-2016 fundraising test

- Accountable role: `forecast_model`
- Owner: `/root`
- Status: `complete`
- Objective: Determine whether fundraising above or below the amount expected from district structure and incumbency improves the post-2016 polling-CMO forecast without double-counting those factors.
- Non-goals: Do not alter canonical finance observations, use realized election outcomes in the fundraising residualizer, select a live headline from the sole 2022 holdout, or publish to `docs/`.
- Upstream snapshot: Experimental post-2016 polling-CMO build `9e80eeed748dfc67daaf` and its frozen inputs.
- Read scope: `scripts/run_post2016_polling_cmo_forecast.py`; `data/processed/forecast_calibration/post2016_polling_cmo_*`; upstream files named in the build manifest.
- Write scope: `scripts/run_post2016_polling_cmo_forecast.py`; `data/processed/forecast_calibration/post2016_polling_cmo_*`; `project_docs/model/POST2016_POLLING_CMO_EXPERIMENT.md`; `project_docs/coordination/FORECAST-POST2016-ORTHO-FINANCE-001.md`.
- Warehouse mode: `read-only`
- Inputs: Finance-complete 2018 and 2022 Alabama contested races, polling-implied federal baselines, reconstructed incumbency, and current 2026 FCPA observations.
- Outputs: Leakage-safe structural-fundraising predictions and residuals, forward metrics against raw fundraising and nonfinance models, coefficient and subgroup diagnostics, updated 2026 sensitivities, and a deterministic manifest.
- Acceptance checks: The 2022 finance residualizer is fit only on 2018; its predictors contain no legislative result or CMO target; all model comparisons use the identical 30-race 2022 holdout; missing 2026 finance remains missing; decomposition arithmetic and manifest hashes reconcile; current forecast tests remain passing.
- Handoff recipient: `validation_release` if promotion or publication is requested.
- Known risks: One forward cycle remains insufficient for promotion; full-cycle historical and partial-cycle 2026 finance are not cutoff-aligned; orthogonalization estimates predictive novelty rather than a causal fundraising effect.

## Handoff

- Build: `30d4e3967a7bbc38700e` (`experimental_not_promoted`).
- Result: the outcome-free within-cycle fundraising residualizer reduced 2022 forward-test MAE from 10.00 for the polling-federal baseline and 9.54 for polling plus incumbency to 7.08 points. Its paired bootstrap improvement versus the baseline was +2.91 points, with a 95% interval of +0.83 to +5.00.
- Coverage: 43 of 48 currently contested 2026 Democratic-versus-Republican races have complete explicit FCPA observations; missing finance remains missing and receives no finance adjustment.
- Checks: 14 output hashes reproduced exactly across consecutive builds; manifest hashes and forecast decomposition reconcile; all nine scenarios contain 48 unique races; 21 forecast/dashboard tests passed; agent-workflow validation passed.
- Files: `scripts/run_post2016_polling_cmo_forecast.py`, `data/processed/forecast_calibration/post2016_polling_cmo_*`, and `project_docs/model/POST2016_POLLING_CMO_EXPERIMENT.md`.
- Caveat: this result uses only the 2022 Alabama forward holdout and historical full-cycle finance, so it is not approved for headline or live-site promotion.
- Downstream action: obtain cutoff-aligned historical finance snapshots or comparable post-2016 Southern finance data, then repeat the forward validation before requesting `validation_release` review.
