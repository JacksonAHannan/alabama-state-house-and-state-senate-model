# Alabama WAR forecast validation

Build `b76d607f2d81e54697a3` generated `2026-09-11T21:08:27.543428+00:00`.

- Alabama retrospective coverage: 97 races (2018 and 2022).
- Forward test: 33 Alabama 2022 races after training on 2039 eligible Southern races after 2016 and before 2022.
- Generic structural candidate MAE: 7.651; generic-ballot baseline MAE: 7.072.
- Selected specification: `generic_war_structural` by owner-required model definition; forward validation is advisory.
- Prospective coverage: 48 D-R races in each scenario.
- Candidate-specific WAR is zero, incumbency is included structurally, candidate history is false, finance is false, and the forecast identity reconciles within floating-point tolerance.
- Owner-selected model assumption: the uniform national-to-Alabama generic-ballot transfer's Alabama-specific validity is not established beyond the single 2022 forward holdout.
- Holdout assessment: the selected structural specification performed worse than the generic-ballot-only benchmark on the sole Alabama 2022 holdout.
- Probability scale: Student-t(5) scale 8.00 selected by maximum likelihood on the holdout margin residuals (80% interval coverage 85%; Brier 0.0176); the scale is tuned and evaluated on the same 33 races, so no independent probability evaluation exists.
- Limitation: Alabama supplies only one direct forward cycle, so calibration and structural estimates remain sample-limited.
