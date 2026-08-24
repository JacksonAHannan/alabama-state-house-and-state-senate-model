# Ideology CQI correction validation

**Verdict: PASS**

The `WEB-IDEOLOGY-CQI-CORRECTION-001` release candidate uses the validated v5
`candidate_quality_index` on the combined ideology/caucus page. It does not
relabel or expose the failed modern Southern-prior residual as CQI.

## Metric identity

Independent joins found 274 public rows and 274 unique candidate IDs. All
274 rows reconcile one-to-one to `data/processed/war/cmo_v5_candidates.csv`;
the largest difference is `4.98e-11`, attributable to JSON serialization.
No public member or staged/published HTML contains
`candidate_quality_residual` or `candidate_cmo`.

As a discriminating check, all 274 published CQI values differ from the v6
Southern residual. The median absolute difference is 11.799 points and the
maximum is 53.052 points.

## Independent Democratic bloc calculations

| Period and bloc | n | Mean CQI | Median CQI |
|---|---:|---:|---:|
| All eras, traditionalist-populist | 76 | +1.036752 | +0.177027 |
| All eras, progressive-modern | 39 | -1.352729 | -0.615901 |
| Post-2016, traditionalist-populist | 4 | +5.317851 | +6.173558 |
| Post-2016, progressive-modern | 20 | -0.169340 | -0.277593 |

The all-era headline difference independently reconstructs to `+2.389481`
points, matching the embedded payload. The page discloses that the modern
traditionalist comparison contains only four candidate-cycles.

## Shor–McCarty modern estimate

The Democratic post-2016 Shor–McCarty federal-performance row remains
underpowered (`n=5`) with a null coefficient and interval. The rendered card
continues to say `Not estimated`; the CQI correction does not manufacture a
modern absolute-ideology estimate.

## Runtime and responsive checks

Independent headless-Chrome checks at 1280, 497, and 390 pixels found no
horizontal overflow or severe console errors. The CQI selectors, post-2016
distribution, candidate detail, and candidate table worked at every width.

## Commands run

```powershell
python -m pytest scripts/tests/test_ideology_performance_page.py scripts/tests/test_published_site_consistency.py scripts/tests/test_site_brand.py -q
python scripts/validate_agent_workflow.py
```

Result: `24 passed`; workflow validation passed.

## Release recommendation

Approve. The page now uses CQI consistently, preserves the sparse modern
Shor–McCarty result as unestimated, and discloses CQI's retrospective nature
and the small modern traditionalist sample.
