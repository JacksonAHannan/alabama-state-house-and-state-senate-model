# Post-2016 Southern WAR v3 validation

Research run `WAR-POST2016-V3-4AF79A70EAA8F39EBD49` uses warehouse build `RUN-92AB8DE353AC47D6AECE3D7767C29FCD`.

## Enforced gates

- All 3,660 rows are strict-ready and have `cycle > 2016`.
- Race keys are unique and candidate-cycle grain is exactly two major-party rows per race.
- Headline `war` exactly equals `raw_gap - fitted_structural_expected_gap`.
- Democratic and Republican candidate-cycle scores are exact opposites.
- No pooled candidate coefficient, second-stage penalty, or residual allocation enters WAR.
- Structural specification selection remains time-forward; same-cycle fitted residuals are clearly labeled descriptive rather than forecasts.
- Missing lag and finance evidence remains explicit; finance is excluded from headline WAR.
- Inputs, code, outputs, field contract, and reports are SHA-256 registered.

## Release decision

This corrects the v2 WAR-definition error but remains a research candidate pending independent validation of structural specification, context coverage, calibration, and uncertainty.
