# Historical Finance Recovery

This mart makes finance selection explicit: DIME/FollowTheMoney recipient totals are used for 1998-2010, and Alabama FCPA principal-campaign-committee summaries are used for 2014-2022. Missing candidates remain unknown; only an identified committee with no cycle activity is treated as an observed zero.

Fundraising ratios use a $500 additive constant on both sides.

| Cycle | Complete races | Eligible races | Coverage |
|---:|---:|---:|---:|
| 1994 | 0 | 72 | 0.0% |
| 1998 | 64 | 85 | 75.3% |
| 2002 | 43 | 74 | 58.1% |
| 2006 | 51 | 62 | 82.3% |
| 2010 | 56 | 63 | 88.9% |
| 2014 | 48 | 56 | 85.7% |
| 2018 | 59 | 64 | 92.2% |
| 2022 | 31 | 33 | 93.9% |

Candidate observations recovered: 785/1018 (77.1%).

The unresolved queue is written to `canonical_historical_finance_review.csv`. The 1994 cases are also written to a separate archival-request manifest; public historical records are the remaining avenue for that cycle.
