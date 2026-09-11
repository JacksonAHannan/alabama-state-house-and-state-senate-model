# Alabama WAR generic-candidate forecast v1

Build: `b76d607f2d81e54697a3`

Generated: `2026-09-11T21:08:27.543428+00:00`

The forecast evaluates a generic Democrat against a generic Republican. Candidate identity, prior WAR/CMO, repeat-candidate performance, ideology, and fundraising are absent; prospective candidate-specific WAR is exactly zero. Incumbency remains a symmetric race condition in the WAR structure.

The baseline is each district's prior presidential margin shifted by the national generic ballot. That uniform national-to-Alabama generic-ballot transfer is an owner-selected model assumption; its Alabama-specific validity is not established beyond the single 2022 forward holdout. The published post-2016 Southern WAR `decaying_lag` ridge design predicts the ordinary legislative-minus-baseline gap using ticket partisanship, time, state, chamber, ticket family, prior presidential context, ticket change, and incumbency balance. The 2022 diagnostic fits eligible Southern races before 2022; the prospective fit uses all eligible post-2016 Southern races through 2024.

The candidate-independent structural adjustment produced a 7.651-point 2022 MAE versus 7.072 for the generic-ballot district baseline. The published specification applies that structural expected gap at the project owner's direction. It performed worse than the generic-ballot-only benchmark on the sole Alabama 2022 holdout; that comparison remains explicit. Candidate-specific residual WAR remains zero. Probabilities use Student-t(5) with a 8.00-point scale, the maximum-likelihood scale of the 33 holdout margin residuals (nominal 80% interval covers 85% of them); a single 33-race holdout remains a material uncertainty for the probability layer. Chamber simulations add correlated national, statewide, chamber, and district error components.
