# Extended historical Southern CMO tournament

The unchanged seven-model tournament was rerun on 2,383 validated observations,
including 110 official Arkansas precinct-context additions from 1994, 1996,
and 1998.

| Model | Forward RMSE | Leave-state-out RMSE | Whole-precinct LOSO RMSE | Selected |
|---|---:|---:|---:|---|
| portable temporal | 14.278 | 15.084 | 14.064 | yes |
| full temporal | 13.876 | 16.589 | 14.595 | no |
| state/chamber/incumbency | 14.757 | 18.848 | 17.533 | no |
| baseline only | 17.852 | 22.737 | 24.339 | no |

The portable temporal model again wins. It is 0.401 points behind the best
forward RMSE, inside the one-point temporal guardrail, and has the best
leave-state-out RMSE. Relative to baseline only, it improves forward RMSE by
3.575 points and leave-state-out RMSE by 7.653 points.

Adding Arkansas pre-2000 observations changes selection from the state-aware
`full_temporal` model in the 2,273-row run back to `portable_temporal`. Its
forward RMSE improves from 15.964 to 14.278 and leave-state-out RMSE improves
from 15.254 to 15.084. This favors portability, but the conclusion remains
sensitive to the states and cycles represented.

Descriptive fitted effects are a symmetric incumbent advantage of 13.916
margin points, a +0.409-point time change per two years, and a -2.924-point
change in down-ballot gap per ten-point increase in Democratic federal
baseline. They are not causal estimates.

The Arkansas additions do not represent complete statewide precinct coverage:
they passed legislative-turnout join gates, while their context footprint is
uneven. The run remains experimental and requires independent validation.
