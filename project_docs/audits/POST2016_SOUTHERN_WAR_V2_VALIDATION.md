# Post-2016 Southern WAR v2 validation

Model run `WAR-POST2016-V2-710F713D8C6FBCDB4D4C` uses validated warehouse run `RUN-85A4692E481448B6BB1380D76E07742B`.

## Enforced gates

- All 3,660 races are strict-ready and have `cycle > 2016`.
- Race keys and prior-presidential joins are one-to-one.
- Structural predictions exclude their own race and never use later cycles.
- Missing lag context is explicit and contributes zero through unavailable lag features.
- Finance is complete for 3,102 races; incomplete rows retain null amounts/adjustments in model interfaces.
- Finance specifications are compared on identical complete-row forward folds.
- Candidate D/R orientations, ridge differentials, and uncertainty labels reconcile.
- Inputs, code, outputs, and reports are SHA-256 registered.

## Release decision

This is a research candidate pending independent validation. Finance is a sensitivity only and is labeled `rejected_not_comparable_total_spending_and_endogenous` by its predictive gate; it is not part of headline WAR.
