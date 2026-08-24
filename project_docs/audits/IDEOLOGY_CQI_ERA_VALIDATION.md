# Ideology CQI-by-era validation

**Verdict: PASS**

The current `IDEO-CQI-ERA-001` / `WEB-IDEO-CQI-ERA-001` release candidate
correctly estimates and displays the association between absolute
Shor–McCarty ideology and v5 Candidate Quality Index by era. The
screenshot-identified chart no longer displays the raw federal-overperformance
regression.

## Source and sample reconstruction

I reconciled `research/cmo_ideology/absolute_rebuild_panel.csv` to its two
upstream measures before fitting anything:

- all 1,018 panel CQI values equal `candidate_quality_index` in
  `data/processed/war/cmo_v5_candidates.csv`; maximum absolute difference is
  `3.55e-15`;
- all 407 finite `absolute_conservatism_z` observations equal `absolute_np_z`
  in `research/cmo_ideology/symmetric_incumbency_panel.csv` exactly;
- all 407 corresponding Shor IDs agree.

I then independently fit Democratic regressions within each era. The outcome
was v5 CQI. Predictors were an intercept, `absolute_conservatism_z`, incumbency,
nonwhite share, white-college share, and the drop-first chamber indicator. I
computed the OLS coefficient directly with a pseudoinverse, formed the
person-clustered sandwich covariance from group score outer products, and
applied the same finite-sample correction. I did not call the production
`fit()` routine.

## Independently reproduced results

| Era | n | People | CQI per SD rightward | Cluster SE | 95% interval | Status |
|---|---:|---:|---:|---:|---:|---|
| Before 2008 | 143 | 142 | +9.035738 | 2.122576 | +4.875489 to +13.195987 | Estimated |
| 2008–2014 | 61 | 50 | +7.800752 | 4.185058 | -0.401962 to +16.003465 | Estimated |
| 2016 and later | 5 | 5 | — | — | — | Underpowered |

These values match `absolute_rebuild_estimates.csv` to displayed precision.
The 2008–2014 interval crosses zero, and the page does not imply otherwise.
The modern sample correctly stops at the common minimum-size gate rather than
publishing an unstable coefficient.

## Publication and chart audit

Both `artifacts/site/ideology-performance.html` and
`docs/ideology-performance.html` embed the current CQI era rows. Their era
renderer explicitly selects `candidate_quality_index`; the former
`candidate_federal_overperformance` renderer is absent. The staged and public
payloads contain:

- `+9.0357380579`, n=143 before 2008;
- `+7.8007516214`, n=61 in 2008–2014;
- a null, `underpowered`, n=5 modern row.

Neither HTML contains the prior `-2.5043222061` raw-federal coefficient. The
rendered chart itself contains no `-2.5` card. Its heading is `CQI association
by era`, its explanatory copy identifies CQI and the adjustment variables, and
each card labels the estimate `CQI per SD rightward`.

Headless Chrome rendered the cards as `+9.0`, `+7.8`, and `Not estimated`, with
the correct rounded intervals and sample sizes. Results by requested viewport:

| Width | Effective client width | Scroll width | Layout | Severe console errors |
|---:|---:|---:|---|---:|
| 1280 | 1265 | 1265 | Three columns | 0 |
| 497 | 482 | 482 | One column | 0 |
| 390 | 375 | 375 | One column | 0 |

There was no horizontal overflow, and no `-2.5` value appeared within the era
section at any checked width.

## Tests and commands

```powershell
python -m pytest tests/test_absolute_ideology_rebuild.py scripts/tests/test_ideology_performance_page.py scripts/tests/test_published_site_consistency.py scripts/tests/test_site_brand.py -q
python scripts/validate_agent_workflow.py
```

Result: `36 passed`; workflow validation passed. I additionally ran the
independent source reconciliation and regression reconstruction described
above and exercised the public page with Selenium/Chrome.

## Caveats and recommendation

CQI is retrospective, Shor coverage is officeholder-selected, the modern
Democratic sample is only five observations, and the 2008–2014 confidence
interval includes zero. These limitations are disclosed. Approve the release
candidate.
