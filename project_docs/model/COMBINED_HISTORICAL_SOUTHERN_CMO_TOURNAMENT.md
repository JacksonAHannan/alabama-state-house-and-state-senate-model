# Combined historical Southern CMO tournament

## Scope

This experimental rerun uses the independently validated combined HEDA and
OpenElections panel. It expands the strict sample from 1,805 to 2,273 races.
The 468 additions are concentrated in Missouri (2000-2016) and Georgia (2012
and 2016). It is not a canonical warehouse or production-forecast input.

## Selection rule

Seven prespecified specifications are evaluated with forward-year and
leave-one-state-out folds. A model must finish within one margin point of the
best forward-year RMSE. Among models that pass that temporal guardrail, the
lowest leave-state-out RMSE wins; whole-precinct sensitivity and simplicity
break ties.

The selected model is `full_temporal`. Its predictors are a symmetric
incumbency balance, time, baseline margin, baseline-by-time and
incumbency-by-time interactions, with state, chamber, and federal-context
office effects. Ridge regularization uses alpha 10.

## Results

| Model | Forward RMSE | Leave-state-out RMSE | Whole-precinct LOSO RMSE | Selected |
|---|---:|---:|---:|---|
| full temporal | 15.574 | 16.090 | 14.750 | yes |
| portable temporal | 15.964 | 15.254 | 14.080 | no: missed forward guardrail by 0.239 |
| state/chamber/incumbency | 14.725 | 18.504 | 17.444 | no |
| baseline only | 18.142 | 23.592 | 24.339 | no |

Relative to the baseline-only model, the selected model reduces forward RMSE
by 2.568 points and leave-state-out RMSE by 7.503 points. Its mean winner
accuracy is 85.6% forward and 84.1% leave-state-out.

The fitted diagnostic effects are descriptive rather than causal. The selected
model estimates a symmetric incumbent advantage of 12.965 margin points, a
-0.448-point change per two years, and a -2.232-point change in down-ballot gap
for a ten-point increase in the Democratic federal baseline.

## Comparison with the HEDA-only run

The earlier 1,805-row run selected `portable_temporal`. Adding the Missouri and
Georgia observations makes that model's forward RMSE 0.416 points worse and
causes it to fall outside the temporal guardrail, while the fuller state-aware
model remains inside. Leave-state-out performance changes little for both
temporal models. This is evidence that selection is sensitive to cycle mix,
not evidence that state effects will necessarily transport to Alabama in 2026.

## Limits

- All inputs remain secondary-source observations.
- Missouri supplies most new rows, so the expanded sample is not geographically balanced.
- Coverage still begins in 2000; 1994-1998 remain missing.
- Candidate residuals are cross-fitted descriptive estimates, not standalone causal measures of candidate quality.
- Production use requires independent validation and a separate decision about portability to Alabama.
