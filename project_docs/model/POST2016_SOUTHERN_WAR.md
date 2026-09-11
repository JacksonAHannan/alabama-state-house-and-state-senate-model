# Post-2016 Southern candidate WAR

## Scope

This versioned research run uses 3,658 strict-ready D-versus-R legislative races in 14 Southern states. The cutoff is literal: only cycles strictly greater than 2016 enter training. Available strict cycles are 2018, 2019, 2020, 2022, 2023, 2024. Research-only rows and finance are excluded.

## Estimand

Direct overperformance is the Democratic legislative margin minus the validated same-election ticket baseline. A replacement level is estimated within state, cycle, chamber, and normalized baseline-office family; groups with fewer than three races use the prespecified broader hierarchy. WAR is the ridge-partial-pooled candidate effect on the remaining Democratic-minus-Republican race differential. Positive WAR means electoral value for a candidate regardless of party.

The time-forward repeat-candidate tournament selected a ridge penalty of 1. On 1,239 held-out races with at least one previously observed candidate, MAE was 4.214 points versus 4.745 for a zero prior-candidate effect. Every fold trains only on strictly earlier cycles.

## Interpretation and limitations

This is a historical candidate-effect model, not a promoted 2026 forecast. The warehouse does not yet expose a cross-state Southern person bridge, so longitudinal links are conservative, state-scoped normalized full-name links. Surname-only and same-cycle ambiguous names remain race-specific. A race between two one-time candidates identifies only their differential; both intervals remain labeled uncertain. The separate intrinsic sensitivity subtracts a prespecified three-point generic incumbency margin before refitting; headline WAR retains officeholding as electoral value.

Model run: `WAR-POST2016-3E87657081BBBCB16754`. Warehouse run: `RUN-7EACF4A3805E4328A3DE0A361051AF35`.
