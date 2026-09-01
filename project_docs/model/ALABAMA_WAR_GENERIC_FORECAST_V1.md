# Alabama WAR generic-candidate forecast v1

Build: `4a24f61e28a3d5987062`

Generated: `2026-09-01T02:45:13.849126+00:00`

The forecast evaluates a generic Democrat against a generic Republican. Candidate identity, prior WAR/CMO, repeat-candidate performance, ideology, and fundraising are absent; prospective candidate WAR is exactly zero. Reviewed incumbency remains a symmetric structural race condition.

The baseline is each district's prior presidential margin shifted by the national generic ballot. A ridge model trained only on Alabama's post-2016 contested races predicts the ordinary legislative-minus-baseline gap using the environment baseline, its curvature and time interaction, chamber, and incumbency balance. The model trains on 2018 and is tested on 2022 before being refit on both cycles for 2026.

The candidate-independent structural adjustment produced a 9.490-point 2022 MAE versus 7.073 for the generic-ballot district baseline. It therefore failed the promotion gate and is zero in the headline forecast. This is the corrected WAR identity for generic candidates: the residual WAR term is zero. Probabilities use Student-t(5) with a 4.00-point scale chosen on that single holdout; that limited probability sample is a material uncertainty. Chamber simulations add correlated national, statewide, chamber, and district error components.
