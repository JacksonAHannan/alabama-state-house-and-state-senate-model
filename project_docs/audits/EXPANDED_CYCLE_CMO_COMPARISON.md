# Experimental expanded-cycle CMO comparison

This diagnostic holds the feature specification constant and changes only the
training window. It is not a comparison against the complete published model
and does not alter the published CMO scores.

## Forward-test result

The shared test set contains 155 contested Democratic-Republican races from
2014, 2018, and 2022.

| Training window | Pooled MAE | Pooled RMSE | 2022 MAE | Screen |
| --- | ---: | ---: | ---: | --- |
| 2010 onward | 16.54 | 22.28 | 8.43 | Reference |
| 1998 onward | 16.15 | 21.52 | 9.86 | Fails recent-cycle non-inferiority |
| 1994 onward | 16.89 | 22.08 | 10.48 | Fails |

These supersede the preliminary comparison that lacked 2010 demographics. The
2010 election now uses direct 2006-2010 ACS five-year SLD estimates. The modest
pooled advantage for the 1998 window comes from earlier tests and is accompanied
by a 1.44-point degradation in 2022 MAE. No expanded window passes the screen.

Era/chamber interactions also fail. They reduce some expanded-window errors but
do not beat the base reference while remaining non-inferior in 2022. Absolute
errors remain large, so no historical window or interaction specification is
ready for public promotion.

The resource-adjusted sensitivity fails more decisively. Its pooled MAE is
16.91 for the published-era window, 19.43 from 1998, and 18.41 from 1994,
compared with 16.54 for the published-era total-effect base model. Historical
finance coverage and definitions vary by era, and conditioning on resources
also changes the estimand, so this result supports retaining resource-adjusted
CMO as a secondary descriptive statistic rather than the historical headline.

## Next research gates

1. Inspect the completed cycle-blocked uncertainty and error by
   chamber, incumbency, baseline fallback share, and partisan baseline.
2. Test shrinkage or rolling-era weighting rather than adding unrestricted
   interactions to a small number of cycles.
3. Promote an expanded model only if it improves pooled validation, remains
   non-inferior on the latest forward cycle, and does not create a materially
   worse subgroup.

Machine-readable results are in
`data/processed/elections/validation/expanded_cycle_cmo_*`.
