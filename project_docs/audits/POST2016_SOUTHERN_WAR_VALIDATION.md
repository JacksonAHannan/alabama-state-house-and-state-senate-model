# Post-2016 Southern WAR validation

Generated at `2026-09-01T00:38:47.722544+00:00` for model run `WAR-POST2016-3E87657081BBBCB16754` from validated warehouse run `RUN-7EACF4A3805E4328A3DE0A361051AF35`.

## Passed gates

- 3,658 input races all have `cycle > 2016` and `training_status=strict_war_ready_no_finance`.
- Race keys are unique; 7,316 candidate-cycle rows provide exactly one Democratic and one Republican observation per race.
- No required outcome, ticket baseline, direct-overperformance, or incumbency field is missing.
- Candidate-oriented direct and residual values are symmetric within each race.
- Every time-forward validation row has `train_max_cycle < cycle`.
- Model outputs, code, and the read-only warehouse snapshot are SHA-256 registered in the manifest.

## Coverage and uncertainty

The fit spans 14 states and cycles 2018, 2019, 2020, 2022, 2023, 2024; 1,078 model-local candidates appear in more than one race. Research-only observations remain excluded rather than being silently promoted. Candidate identity limitations and isolated-pair identification are carried as row-level status fields.

## Automated checks

The focused post-2016 WAR suite passed 5 tests. The repository-wide suite retained the pre-existing unrelated failure in `test_canonical_historical_finance.py`: its fixture expects 352 canonical-finance-complete races while the current finance build contains 353. No Southern WAR retraining test failed.
