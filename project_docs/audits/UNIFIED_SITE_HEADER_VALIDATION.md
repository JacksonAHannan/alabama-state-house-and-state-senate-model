# Unified site-header validation

## Verdict

**PASS.** All six substantive public routes use the same shared header structure, identity lockup, portrait, and ten-link navigation. Active-route semantics, responsive behavior, and page interactions satisfy the release contract.

## Structural reconciliation

The following generated pages were inspected independently:

- `index.html`
- `cmo.html`
- `ideology-performance.html`
- `methodology.html`
- `cmo-methodology.html`
- `legislators.html`

After removing only the route-specific `aria-current="page"` attribute, the serialized header DOM was identical across all six pages (`1` unique normalized header).

Every header contains:

- exactly one `.site-portrait`;
- the wordmark `Jackson Hannan` and subtitle `Alabama legislative models`;
- exactly ten `.site-nav` links in the same order and with the same destinations: Forecast, CMO, Ideology & caucuses, Forecast methodology, CMO methodology, GitHub, Instagram, Substack, LinkedIn, and `@electionsjack`;
- no Candidate Atlas link, Candidate Atlas label, or `legislators.html` navigation destination.

Exactly one internal navigation link is marked current on each substantive route. Forecast, CMO, forecast methodology, and CMO methodology mark their corresponding links. Ideology and the legacy `legislators.html` compatibility route mark Ideology & caucuses. External links and the identity/home link are never marked current.

`caucuses.html` remains an intentional immediate/canonical redirect to `ideology-performance.html#candidate-explorer`; its lack of a shared header is consistent with the contract.

## Browser validation

Installed Chrome was exercised with CDP device-metric overrides at 1280, exact 497, and exact 390 CSS pixels.

Across all six substantive pages and all three widths:

- exactly one portrait element rendered with a non-empty embedded background image;
- portrait dimensions were 48×48px at desktop and 42×42px at both narrow widths;
- the document had zero horizontal overflow;
- the shared header dimensions and wrapping behavior were identical page-to-page;
- browser logs contained zero severe console/runtime errors.

Forecast interactions remained functional: all three scenario tabs could be selected and exactly one tab retained `aria-selected="true"` after each click.

The ideology page loaded 115 candidate points, six select controls, its search input, and its button controls. Exercising representative controls produced no runtime error.

## Tests

```powershell
python -m pytest scripts/tests/test_site_brand.py scripts/tests/test_published_site_consistency.py scripts/tests/test_forecast_dashboard.py scripts/tests/test_ideology_performance_page.py scripts/tests/test_legislator_ideology_page.py -q
python scripts/validate_agent_workflow.py
```

Current result: `43 passed`; workflow validation passed. This includes the added shared-header and legacy-atlas routing regressions (the owner-reported pre-existing focused subset is 40/40).

## Release decision

Approved for publication. No blocking finding or additional caveat was identified within the validation scope.
