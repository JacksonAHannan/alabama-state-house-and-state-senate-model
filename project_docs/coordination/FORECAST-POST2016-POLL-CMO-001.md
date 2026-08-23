# Task contract: FORECAST-POST2016-POLL-CMO-001 — post-2016 polling-CMO forecast experiment

- Accountable role: `forecast_model`
- Owner: `/root`
- Status: `complete`
- Handoff: Experimental build `9e80eeed748dfc67daaf`; not approved for headline promotion.
- Objective: Test a forecast family trained only on elections after 2016 in which final generic-ballot polling supplies the prospective federal baseline and legislative downballot lag, incumbency, and fundraising are estimated as residual adjustments.
- Non-goals: Do not replace the live forecast, revise canonical election or finance observations, treat missing finance as zero, or claim causal effects for fundraising.
- Upstream snapshot: Commit `3f355b5`; current Alabama historical finance mart, current post-2016 CMO features, final-cycle Silver-rated generic-ballot polling, and current 2026 prospective features.
- Read scope: `data/processed/war/fcpa_fundraising_experiment_panel.csv`; `data/processed/war/fcpa_candidate_cycle_finance.csv`; `data/processed/elections/canonical_cmo_candidates.csv`; `data/processed/ideology/candidate_legislator_identity_crosswalk.csv`; `data/raw/polling/fivethirtyeight_raw_polls.csv`; `data/raw/polling/nate_silver_pollster_ratings.csv`; `data/processed/polling/votehub_silver_bplus_topline_environment.csv`; `data/processed/war/2026_*`; existing forecast utilities and model documents.
- Write scope: `scripts/run_post2016_polling_cmo_forecast.py`; `data/processed/forecast_calibration/post2016_polling_cmo_*`; `project_docs/model/POST2016_POLLING_CMO_EXPERIMENT.md`; `project_docs/coordination/FORECAST-POST2016-POLL-CMO-001.md`.
- Warehouse mode: `read-only`
- Inputs: Historical Alabama contested legislative races in 2018 and 2022 with explicit incumbency and finance evidence; polling-implied national swing; current 2026 poll-adjusted district baseline and candidate finance observations.
- Outputs: Frozen experiment panel, forward-cycle predictions, specification metrics, coefficient/stability diagnostics, 2026 scenario estimates, manifest, and model note.
- Acceptance checks: One-direction forward test trains on 2018 and predicts 2022; no row uses its own-cycle legislative result as a feature; polling baseline uses polling-implied rather than realized national swing; missing finance remains explicit; results compare baseline, lag, incumbency, fundraising, and combined models; deterministic rebuild and manifest checks pass.
- Handoff recipient: `validation_release` if promotion or publication is requested.
- Known risks: Only one genuinely forward Alabama holdout cycle exists after 2016; historical finance is full-cycle rather than cutoff-aligned; fundraising is endogenous to race competitiveness; results are experimental unless corroborated with comparable multi-state finance.
