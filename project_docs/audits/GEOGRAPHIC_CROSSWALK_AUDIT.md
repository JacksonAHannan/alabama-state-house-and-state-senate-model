# Geographic crosswalk audit

The modern crosswalk now treats the district reported with a precinct's legislative result as authoritative. Census-block population and official district assignments are used only for genuine split precincts. Legislative vote shares are retained only as a labeled split fallback, and county shares are reserved for non-geographic batches or splits with no usable activity. The pipeline no longer assumes that election precinct IDs are Census VTD IDs.

## Modern-cycle method comparison

| cycle | chamber | precincts | direct_or_spatial_precincts | fallback_precincts | fallback_share | county_level_ballots | mean_weight_l1_change_vs_legacy | p95_weight_l1_change_vs_legacy | max_weight_l1_change_vs_legacy | precincts_l1_change_gt_0_10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2014 | house | 2291 | 1653 | 505 | 0.220 | 133 | 0.458 | 1.782 | 2.000 | 889 |
| 2014 | senate | 2298 | 1829 | 336 | 0.146 | 133 | 0.279 | 1.513 | 2.000 | 640 |
| 2018 | house | 2240 | 1902 | 203 | 0.091 | 135 | 0.331 | 1.776 | 2.000 | 620 |
| 2018 | senate | 2240 | 1999 | 106 | 0.047 | 135 | 0.186 | 1.393 | 2.000 | 390 |
| 2022 | house | 1939 | 1924 | 15 | 0.008 | 0 | 0.360 | 1.853 | 2.000 | 548 |
| 2022 | senate | 1939 | 1931 | 8 | 0.004 | 0 | 0.209 | 1.588 | 2.000 | 346 |

`weight_l1_change_vs_legacy` is the total absolute change in a precinct's district allocation vector. Zero means identical; two is the theoretical maximum. Older-cycle fallback rows remain explicitly identified and should not be interpreted as exact precinct geography.

The corrected 2022 House crosswalk assigns 31 source precincts at least partly to HD-32.

## Earlier-cycle finding

The same general risk persists before 2018. The separate historical precinct audit classifies a large share of 1994-2006 precinct-district slices as low-confidence or unresolved, and the production historical CMO still labels those baselines provisional. The 2010 canonical export now improves matched nodes with the spatial-block method but retains explicit county fallback for unmatched labels. See `geographic_all_cycle_audit.csv` for the complete 1994-2022 inventory.
