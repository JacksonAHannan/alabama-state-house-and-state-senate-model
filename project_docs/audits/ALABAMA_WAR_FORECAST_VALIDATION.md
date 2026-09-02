# Alabama WAR forecast validation

Build `00509565ea4fb62b4e10` generated `2026-09-02T00:44:48.885584+00:00`.

- Alabama retrospective coverage: 97 races (2018 and 2022).
- Forward test: 33 Alabama 2022 races after training on 2037 eligible Southern races after 2016 and before 2022.
- Generic structural candidate MAE: 9.559; generic-ballot baseline MAE: 7.073.
- Selected specification: `generic_war_structural` by owner-required model definition; forward validation is advisory.
- Prospective coverage: 48 D-R races in each scenario.
- Candidate-specific WAR is zero, incumbency is included structurally, candidate history is false, finance is false, and the forecast identity reconciles within floating-point tolerance.
- Holdout assessment: the selected structural specification performed worse than the generic-ballot-only benchmark on the sole Alabama 2022 holdout.
- Limitation: Alabama supplies only one direct forward cycle, so calibration and structural estimates remain sample-limited.
