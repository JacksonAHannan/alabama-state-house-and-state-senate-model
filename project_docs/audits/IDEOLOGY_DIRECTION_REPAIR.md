# Ideology graphic direction repair

## Diagnosis

The underlying estimates were directionally consistent:

- The within-election, within-chamber CQI contrast was +4.50 points for the
  traditionalist-populist bloc relative to the progressive-modern bloc.
- A one-standard-deviation move toward greater absolute conservatism was
  associated with +9.04 CQI points before 2008 and +7.80 points in 2008–2014.
- The post-2016 Democratic Shor–McCarty sample contains only five observations
  and remains unestimated.

The apparent contradiction came from the chart design. Positive bloc
differences were plotted to the right, but the right side of the track used the
progressive blue tint. The number itself was also shown without naming which
bloc held the advantage.

## Repair

- The negative/left side is now labeled `Progressive-modern advantage` and
  tinted blue.
- The positive/right side is labeled `Traditionalist-populist advantage` and
  tinted oxblood.
- Values are rendered as an explicit leader and advantage, for example
  `Traditionalist-populist +4.5`, with the signed contrast retained below.
- The era chart now labels its direction as lower or higher CQI for a
  one-standard-deviation move toward greater conservatism.
- The explanatory note states that the discrete bloc contrast and continuous
  Shor–McCarty regression use different samples and ideology measures, while
  defining positive values in the same substantive direction.

No estimates, cluster assignments, or source data changed.

## Validation

```powershell
python scripts/build_democratic_transition_page.py
python -m pytest scripts/tests/test_ideology_performance_page.py -q
```

Result: `14 passed`.

A fresh 1440-pixel browser rendering confirmed that the CQI row displays
`Traditionalist-populist +4.5` on the oxblood/right side and that the federal
and presidential rows use the same direction.

## Handoff

- Outcome: `accepted candidate`
- Upstream snapshot used: Current validated CQI v5, Democratic cluster output,
  and absolute-ideology era estimates.
- Changed source files: `scripts/build_democratic_transition_page.py` and
  `scripts/tests/test_ideology_performance_page.py`.
- Generated outputs: `artifacts/site/ideology-performance.html`.
- Manual decisions: None.
- Assumptions and limitations: The two graphics are directionally comparable
  but do not estimate the same contrast or use identical candidate coverage.
- Warehouse changes requested: None.
- Downstream invalidation: `docs/ideology-performance.html` remains unchanged
  until a separately validated publication build.
- Reviewer: Focused tests and browser rendering passed; independent release
  validation remains required before publication.
- Next action: Submit the local page artifact for independent validation before
  rebuilding `docs/`.
