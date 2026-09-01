# Post-2016 Southern WAR v3 validation

Research run `WAR-POST2016-V3-D9C7EE17BD14B8C7D23A` uses warehouse build `RUN-4ED478C647B34A7B9A402970625DB334`.

## Enforced gates

- All 3,658 rows are strict-ready and have `cycle > 2016`.
- Race keys are unique and candidate-cycle grain is exactly two major-party rows per race.
- Headline `war` exactly equals `raw_gap - fitted_structural_expected_gap`.
- Democratic and Republican candidate-cycle scores are exact opposites.
- No pooled candidate coefficient, second-stage penalty, or residual allocation enters WAR.
- Structural specification selection remains time-forward; same-cycle fitted residuals are clearly labeled descriptive rather than forecasts.
- Missing lag and finance evidence remains explicit; finance is excluded from headline WAR.
- Inputs, code, outputs, field contract, and reports are SHA-256 registered.

## Release decision

This corrects the v2 WAR-definition error but remains a research candidate pending independent validation of structural specification, context coverage, calibration, and uncertainty.
