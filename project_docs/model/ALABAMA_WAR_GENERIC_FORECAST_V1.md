# Alabama WAR generic-candidate forecast v1

Build: `ca64e43e988cc59c12bc`

Generated: `2026-10-05T21:19:36.330704+00:00`

The forecast starts from a generic Democrat against a generic Republican, then carries each nominee's own demonstrated WAR forward where a prior Alabama race is matched, at the persistence estimated on Southern v3 repeat candidates (0.432). Unmatched nominees stay generic; ideology and fundraising are absent. Incumbency remains a symmetric race condition in the WAR structure.

The baseline is each district's prior presidential margin shifted by the national generic ballot. That uniform national-to-Alabama generic-ballot transfer is an owner-selected model assumption; its Alabama-specific validity is not established beyond the single 2022 forward holdout. The published post-2016 Southern WAR `decaying_lag` ridge design predicts the ordinary legislative-minus-baseline gap using ticket partisanship, time, state, chamber, ticket family, prior presidential context, ticket change, and incumbency balance. The 2022 diagnostic fits eligible Southern races before 2022; the prospective fit uses all eligible post-2016 Southern races through 2024.

The candidate-independent structural adjustment produced a 7.651-point 2022 MAE versus 7.072 for the generic-ballot district baseline. The published specification applies that structural expected gap at the project owner's direction. It performed worse than the generic-ballot-only benchmark on the sole Alabama 2022 holdout; that comparison remains explicit. Candidate history is added after the structural prediction in 23 of 48 headline races. Probabilities use Student-t(5) with a 7.75-point scale, the maximum-likelihood scale of the 33 holdout margin residuals (nominal 80% interval covers 85% of them); a single 33-race holdout remains a material uncertainty for the probability layer. Chamber simulations add correlated national, statewide, chamber, and district error components.

Graphics exports: `2026_environment_seat_joint` cross-tabulates each draw's shared environment shift (national plus statewide error, 1-point bins) with modeled Democratic seats, and its margin over the environment reproduces the modeled-seat distribution exactly. `run_ledger` keeps one row per chamber for each distinct forecast result. The polling replay (`scripts/build_forecast_polling_replay.py`) re-applies the polling-average rule as of earlier dates with candidates and every other input held at this run; it is a sensitivity series, not an archived forecast history.
