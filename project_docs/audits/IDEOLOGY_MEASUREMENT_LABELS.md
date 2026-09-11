# Ideology measurement labels

## Outcome

The ideology page now explicitly separates two distinct measurements:

1. **Issue-cluster contrast:** a binary comparison between candidates grouped
   from multidimensional issue records, reported in outcome points between
   clusters.
2. **Shor–McCarty slope:** a continuous absolute-ideology association, reported
   in outcome points per one Shor–McCarty standard deviation.

The page no longer places the +4.5 CQI cluster contrast beside the +9.0 and
+7.8 per-standard-deviation slopes without explaining their units.

## Conversion shown on the page

| Era | Shor–McCarty CQI slope | Cluster separation | Implied CQI gap | Observed cluster gap |
|---|---:|---:|---:|---:|
| Before 2008 | +9.04 per SD | 0.424 SD | +3.83 | +3.57 |
| 2008–2014 | +7.80 per SD | 0.522 SD | +4.08 | +5.07 |

The conversion is calculated from the current payload rather than embedded as
static display values. Post-2016 is omitted because the Shor–McCarty coverage
does not support a two-cluster conversion or the era regression.

## Presentation changes

- The first analysis is titled `CQI difference between issue-based blocs` and
  labels its unit as CQI points between clusters.
- The era analysis is titled `CQI slope by absolute ideology and era` and
  labels its unit as CQI points per one Shor–McCarty standard deviation.
- A comparison table shows the slope, empirical cluster separation, implied
  gap, and independently observed cluster gap.
- The methods section defines both measurements and states that neither is an
  average of the other.

No CQI estimates, cluster assignments, Shor–McCarty scores, or model data were
changed.

## Validation

```powershell
python scripts/build_democratic_transition_page.py
python -m pytest scripts/tests/test_ideology_performance_page.py -q
```

Result: `15 passed`.

A new 1440-pixel browser rendering confirmed that the definitions, units, and
conversion table are readable and remain inside the page grid.

## Handoff

- Outcome: `accepted candidate`
- Upstream snapshot used: Completed `WEB-IDEOLOGY-DIRECTION-001` artifact and
  current validated ideology outputs.
- Changed source files: `scripts/build_democratic_transition_page.py` and
  `scripts/tests/test_ideology_performance_page.py`.
- Generated outputs: `artifacts/site/ideology-performance.html`.
- Manual decisions: None.
- Assumptions and limitations: The conversion is descriptive because the two
  measurements have different coverage and model specifications.
- Warehouse changes requested: None.
- Downstream invalidation: The published ideology page remains stale until a
  separate validated `docs/` publication build.
- Reviewer: Focused tests and browser rendering passed; independent release
  validation remains required before publication.
- Next action: Validate and publish the rebuilt ideology page.
