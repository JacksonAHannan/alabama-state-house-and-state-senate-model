# Tennessee-extended historical Southern CMO tournament

The unchanged seven-model tournament was rerun on 2,402 independently
validated observations. The only new evidence is 19 Tennessee 1998 contests
with reconciled outcomes and at least 95 percent exact-join governor context
coverage.

| Model | Forward RMSE | Leave-state-out RMSE | Whole-precinct LOSO RMSE | Selected |
|---|---:|---:|---:|---|
| portable temporal | 14.457 | 15.326 | 14.088 | yes |
| full temporal | 14.370 | 16.943 | 14.567 | no |
| symmetric incumbency | 14.923 | 18.927 | 18.071 | no |
| state/chamber/incumbency | 14.953 | 18.968 | 17.494 | no |
| baseline only | 17.852 | 22.941 | 24.339 | no |

`portable_temporal` remains selected. It is 0.087 points behind the best
forward RMSE, inside the fixed one-point guardrail, and retains the best
leave-state-out and whole-precinct leave-state-out RMSE. Relative to baseline
only, it improves forward RMSE by 3.395 points and leave-state-out RMSE by
7.615 points.

Compared with the prior 2,383-row run, portable-temporal forward RMSE rises
from 14.278 to 14.457 and leave-state-out RMSE rises from 15.084 to 15.326.
The selection is unchanged, but Tennessee is modestly harder to predict than
the prior sample.

Descriptive fitted effects are a symmetric incumbent advantage of 14.258
margin points, a +0.148-point change per two years, and a -3.130-point change
in down-ballot gap per ten-point increase in Democratic baseline. These are
model coefficients, not causal estimates.

This remains an experimental cross-state calibration panel. Tennessee 1998
contributes only contested districts that pass strict OCR reconciliation and
coverage gates; excluded districts remain available in the integration audit.
