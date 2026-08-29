# Forecast fundraising-direction repair

Date: 2026-08-28

Owner: `forecast_model`
Task: `FORECAST-FINANCE-DIRECTION-030`

## Finding

The candidate-finance reconciliation was correct. In Senate District 7, the model input records Jared Sluss (D) at **$19,146.16** and Sam Givhan (R) at **$370,509.84**. The error occurred downstream: the public headline selected a within-cycle residualized fundraising feature. Sluss raised much less in absolute terms but slightly more than the first-stage model expected for a Democratic challenger in that context, so the residual and the displayed contribution became Democratic-positive.

That is a defensible research diagnostic, but it is not “relative fundraising strength.” Across the 45 finance-complete contested races, it reversed the direction of the observed fundraising advantage in 18 races.

## Resolution

The headline now selects `polling_federal_plus_incumbency_fundraising`, which uses:

`log1p(D receipts / $50,000) - log1p(R receipts / $50,000)`

The transformation compresses dollar outliers without changing which party raised more. The residualized variants remain in the research tournament but are no longer promoted as the public relative-fundraising component. The promotion script now fails if any finance-complete race's fundraising adjustment opposes its observed fundraising gap.

The direct model's sole forward holdout MAE is **8.43 points**, versus **7.08** for the previously selected within-cycle residualized model, **9.54** for polling plus incumbency, and **10.00** for the polling-federal baseline. This is a deliberate choice of a coherent, auditable construct over a better-scoring but mislabeled and direction-reversing residual in one small holdout.

## Senate District 7

| Measure | Previous headline | Repaired headline |
|---|---:|---:|
| Democratic receipts | $19,146.16 | $19,146.16 |
| Republican receipts | $370,509.84 | $370,509.84 |
| D-minus-R log fundraising gap | -1.805 | -1.805 |
| Fundraising adjustment | D +0.92 | D -8.88 |
| Predicted Democratic margin | -7.87 | -10.38 |
| Conditional Democratic win probability | 11.5% | 6.5% |

## Validation

- Finance-complete headline races: 45 of 48.
- Direction reversals after repair: 0.
- All three incomplete finance observations remain missing and receive a zero finance adjustment.
- The release manifest now selects the direct relative-fundraising specification and records methodology version `post2016_headline_v1_1`.
- The model outputs rebuilt successfully. Dashboard tests remain intentionally pending until the downstream web artifact is rebuilt against the new manifest.
