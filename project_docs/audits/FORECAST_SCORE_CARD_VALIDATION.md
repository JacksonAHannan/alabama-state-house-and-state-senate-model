# Forecast score-card validation

## Verdict

**PASS.** The current `WEB-FORECAST-SCORE-CARD-001` release candidate renders one accuracy metric in one compact grid column, without reserving the former two empty card slots. Forecast interactions and responsive behavior remain intact.

## Evidence

### DOM and computed layout

Chrome was run with CDP device-metric overrides at 1280, exact 497, and exact 390 CSS-pixel viewport widths.

At every width:

- `#modelScores` contained exactly one direct child.
- Computed `grid-template-columns` was exactly `150px` (one column).
- The metric container measured 152px wide including its border, while its only child measured 150px wide.
- Desktop container/child heights were 54.5/52.5px; mobile heights were 45.39/43.39px. There was no vacant second or third row/column area.
- Document horizontal overflow was zero.
- Browser logs contained zero severe console/runtime errors.

The rendered metric is labeled `2022 holdout MAE`, consistent with the single score supplied by the current dashboard builder.

### Forecast controls

The page rendered exactly three forecast tabs: Headline, Dem scenario, and Rep scenario. Independently clicking each control updated `aria-selected` to that control alone and updated the model description to the corresponding scenario. The DOM rerender completed without console errors.

### Source inspection

- The public page's active render function inserts one `span` into `#modelScores`.
- `.model-scores` defines a single `minmax(0,150px)` column at both default and mobile breakpoints, with `width: max-content` and `max-width: 100%`.
- No CSS track remains for two absent score cards.

## Commands and results

```powershell
python -m pytest scripts/tests/test_forecast_dashboard.py scripts/tests/test_published_site_consistency.py scripts/tests/test_site_brand.py -q
python scripts/validate_agent_workflow.py
```

Results: `27 passed`; agent workflow validation passed.

Browser checks used Selenium with installed Chrome in headless mode and `Emulation.setDeviceMetricsOverride` for exact viewport widths. Measurements were taken from `getBoundingClientRect()`, computed styles, DOM child counts, document scroll/client widths, ARIA state, and Chrome browser logs.

## Release decision

Approved for publication. No blocking findings or additional caveats were identified within the contract scope.
