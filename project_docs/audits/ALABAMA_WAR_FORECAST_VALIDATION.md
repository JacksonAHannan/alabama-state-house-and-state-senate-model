# Alabama WAR forecast validation

Build `ca64e43e988cc59c12bc` generated `2026-10-05T21:19:36.330704+00:00`.

- Alabama retrospective coverage: 97 races (2018 and 2022).
- Forward test: 33 Alabama 2022 races after training on 2039 eligible Southern races after 2016 and before 2022.
- Generic structural candidate MAE: 7.651; generic-ballot baseline MAE: 7.072.
- Selected specification: `war_structural_plus_candidate_history` by owner-required model definition; forward validation is advisory.
- Prospective coverage: 48 D-R races in each scenario.
- Candidate history is carried forward in 23 headline races; incumbency is included structurally; finance is false; and the forecast identity reconciles within floating-point tolerance.
- Graphics exports: the environment-seat joint's margin reproduces the modeled-seat distribution exactly (checked at build time).
- Owner-selected model assumption: the uniform national-to-Alabama generic-ballot transfer's Alabama-specific validity is not established beyond the single 2022 forward holdout.
- Holdout assessment: the selected structural specification performed worse than the generic-ballot-only benchmark on the sole Alabama 2022 holdout.
- Probability scale: Student-t(5) scale 7.75 selected by maximum likelihood on the holdout margin residuals (80% interval coverage 85%; Brier 0.0165); the scale is tuned and evaluated on the same 33 races, so no independent probability evaluation exists.
- Limitation: Alabama supplies only one direct forward cycle, so calibration and structural estimates remain sample-limited.
