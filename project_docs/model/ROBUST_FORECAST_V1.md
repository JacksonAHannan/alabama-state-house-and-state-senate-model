# Robust forecast research pipeline v1

## Scope and selection

The modern tournament contains 1,188 contested Southern legislative races in
2018–2024. Forward folds predict 2020, 2022, and 2024 using only earlier
cycles. The 2024 incumbency layer is model-ready for 323 of 335 races; the 12
unresolved races retain missing values and are omitted from the common
tournament comparison.

Four nested margin specifications are tested: the direct national-environment
baseline; demographic response; demographics plus incumbency/open-seat status;
and those fields plus a shrunk, strictly prior-cycle candidate-quality signal.
Candidate quality is keyed to normalized candidates, not seats, and receives a
zero adjustment plus an availability flag when no prior race exists.

| Model | Mean forward MAE | Delta vs baseline | 2024 delta | Promoted |
|---|---:|---:|---:|---|
| baseline | 4.751 | 0.000 | 0.000 | yes |
| demographics + incumbency | 5.591 | +0.839 | +0.349 | no |
| plus prior candidate quality | 5.630 | +0.878 | +0.260 | no |
| demographics | 6.031 | +1.279 | +0.483 | no |

No challenger clears the prespecified average/latest-cycle/worst-cycle gate.
The headline 2026 margin therefore remains the poll- and demographic-transfer
environment baseline. Historical CMO and favorable national-environment cases
are published only as scenarios.

## Finance

Finance is not fitted. The repository has strong Alabama finance coverage but
no comparable, cutoff-consistent candidate-finance mart across the four modern
calibration states. Treating Alabama-only coverage as a cross-state feature
would confound state with availability. The finance gate records zero eligible
cross-state coverage rather than converting missing observations to zero.

## Probability and uncertainty

Probability families are fitted to the selected model's out-of-sample margins.
A Student-t curve with 5 degrees of freedom and scale 5.75 has the lowest
candidate Brier score (`0.02980`) and log loss (`0.09955`). It replaces neither
the expected margin nor the separate shared-error simulation.

The selected forward errors decompose to approximately 2.01 state, 1.03
chamber, and 5.91 district margin points. Historical final generic-ballot poll
errors supply a separate 2.20-point national component. The 50,000-draw full-
uncertainty view shares national and Alabama draws across districts, shares a
chamber draw within each chamber, and adds district-specific error. Conditional
probabilities and full-uncertainty probabilities remain separately labeled.

## Calibration audit and output views

Calibration tables report MAE, RMSE, Brier score, and bias by state, chamber,
margin band, incumbency status, and demographic type. The demographic types
are majority-nonwhite, high-white-college, and other; a comparable cross-state
urban/suburban/rural label is not currently available.

The research output contains one selected `headline` view and three scenarios:
historical CMO, Democratic-favorable environment, and Republican-favorable
environment. Scenarios cannot alter model selection. Chamber distributions
currently count the 48 modeled contested Alabama races only; fixed and
unmodeled seats must be added from the certified roster during a subsequent
web-product integration.
