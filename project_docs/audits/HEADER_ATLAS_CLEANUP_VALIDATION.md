# Header and Candidate Atlas cleanup validation

## Verdict

**PASS.** The forecast masthead has one compact portrait/name/subtitle lockup, and the Ideology & Caucuses header and footer no longer contain Candidate Atlas copy or links. Navigation, forecast controls, page scripts, and responsive layouts remain functional.

## Independent browser evidence

Chrome was run headlessly with CDP device-metric overrides at 1280, exact 497, and exact 390 CSS-pixel viewport widths.

### Forecast masthead

- Exactly one portrait-bearing pseudo-element rendered on `docs/index.html` at every width.
- The portrait measured 48×48px on desktop and 42×42px at both mobile widths.
- The portrait is attached to the `.brand` identity grid containing exactly `Jackson Hannan` and `Alabama legislative forecast`, placing it beside the two-line identity text rather than as a separate masthead block.
- The identity lockup measured 50px tall on desktop and 44px on mobile. Desktop mast height was 91px, the same compact overall height as the CMO masthead. Mobile height increased only as navigation wrapped (135px at 497 and 154px at 390), not because of an extra portrait or identity row.

### Ideology page cleanup

- Header/footer text contains no `Candidate Atlas` string, case-insensitively.
- Header/footer links contain zero `legislators.html` targets.
- The remaining local navigation targets (`index.html`, `cmo.html`, `ideology-performance.html`, and `cmo-methodology.html`) exist, and the footer retains only the intended CMO link.

### Runtime and responsiveness

- Document horizontal overflow was zero on forecast, ideology, and comparison CMO pages at all three widths.
- Chrome reported zero severe console/runtime errors on all checked pages.
- Forecast rendered its three current scenario tabs. Clicking Headline, Dem scenario, and Rep scenario left exactly one tab selected each time and updated the page without errors.
- The ideology page loaded its full interactive payload without a script exception; focused interaction/page tests also passed.

## Source and test checks

The theme defines the forecast identity portrait once through `.brand:before`, with the compact 48px/42px responsive sizing. The current ideology builder contains neither a Candidate Atlas navigation item nor a Candidate Atlas footer link.

Commands:

```powershell
python -m pytest scripts/tests/test_forecast_dashboard.py scripts/tests/test_ideology_performance_page.py scripts/tests/test_caucus_analysis_page.py scripts/tests/test_published_site_consistency.py scripts/tests/test_site_brand.py -q
python scripts/validate_agent_workflow.py
```

Results: `38 passed`; agent workflow validation passed.

## Release decision

Approved for publication. No blocking findings were found within the contracted scope.
