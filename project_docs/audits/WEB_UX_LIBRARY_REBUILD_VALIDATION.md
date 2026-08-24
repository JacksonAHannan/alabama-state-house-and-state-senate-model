# WEB UX library rebuild validation

## Verdict

**PASS.** The current `WEB-UX-LIBRARY-REBUILD-001` release candidate is fit for publication. I independently rebuilt the site, tested the six substantive public pages, and reran the browser gate after both release-blocking accessibility/responsive findings were remediated at generator level.

Validated on 2026-08-24 with Chrome 151 in headless browser sessions at exact CSS viewport widths of 1440, 768, and 390 pixels.

## Commands

```powershell
python scripts/build_blue_oxblood_site.py
python -m pytest scripts/tests/test_forecast_dashboard.py scripts/tests/test_cmo_story_historical_cycles.py scripts/tests/test_ideology_performance_page.py scripts/tests/test_published_site_consistency.py scripts/tests/test_site_brand.py scripts/tests/test_legislator_ideology_page.py -q
python scripts/validate_agent_workflow.py
```

I also used Selenium/Chrome against `http://localhost:8765` to measure `innerWidth`, `documentElement.clientWidth`, `documentElement.scrollWidth`, element rectangles, accessible names, focus/selection state, and browser console output on:

- `index.html`
- `cmo.html`
- `ideology-performance.html`
- `methods.html`
- `methodology.html`
- `cmo-methodology.html`

## Rebuild and tests

- Two consecutive complete rebuilds produced byte-identical copies of all six generated publication files. Final SHA-256 values were:
  - `index.html`: `ED26FBA84EC5D74DEC94FA189E0FF96C37B9BECC37AA2E9380CDC93E202531F7`
  - `cmo.html`: `2515967F1A77C732DF239F8A3A47296C42BFB83E49B2787F0B9135841152C142`
  - `ideology-performance.html`: `2555FFED39FB2C14175E26C0A46BA069C08F5893FBDE0FE2F3E97FBF32188882`
  - `methodology.html`: `CF7CC1694095DD5DFAF2DC7A041E2853D6B1459A6280629B523302C900D66D70`
  - `cmo-methodology.html`: `1F417B9209A78BA934AFB01B2E4757FDF8D2B13802D5CB4A8EDDF583CFC9DFF2`
  - `legislators.html`: `48DE592EC05CAB4E3F787A4776F40CA0229F4DB4E55B0F832339F8568A7935CC`
- Focused suite: **56 passed**.
- Agent workflow validation: **passed**.
- Before the final cosmetic remediations, the staged and published forecast, CMO, and ideology embedded payloads were independently compared and were exact matches. Subsequent changes were confined to generated accessibility/responsive presentation.

## Browser and responsive findings

- Every tested page had `scrollWidth == clientWidth` at exact 1440, 768, and 390 pixel CSS viewports.
- No substantive `SEVERE` browser-console entries appeared. A local-server-only missing `favicon.ico` request appeared intermittently and is not an application failure.
- Desktop, tablet, and mobile visual inspections showed coherent hierarchy, readable controls, intact maps/plots, and no clipped page content.
- The initial 390-pixel ideology distribution labels extended 11 pixels left of the viewport. After remediation, both labels are fully contained: `Traditionalist-populist` measured left/right `36/138.125` and `Progressive-modern` measured `36/134.047` in the exact 390-pixel viewport.
- Visible-text contrast inspection found no WCAG AA failures. The lowest observed ratios remained above the applicable threshold (approximately 4.54 on forecast, 4.74 on CMO, and 5.27 on ideology).

## Accessibility and interaction findings

- Forecast scenario tabs retain keyboard behavior: `ArrowRight` moved both focus and `aria-selected` to `environment_dem_favorable`.
- Forecast chamber and map-mode controls, and the Leaflet district keyboard selection, remained functional.
- The initial CMO candidate filters and table rows lacked sufficient accessible names. After remediation:
  - search/scope/party/outcome controls expose explicit labels;
  - all 84 focusable candidate rows expose `role="button"` and an informative dynamic label (for example, `Open Richard Lindsey, 2010 House District 39, CMO +64.0`);
  - `Enter` opens candidate detail;
  - the close control is labeled `Close candidate details` and closes by keyboard.
- CMO cycle, chamber, and map-mode controls continued to update selected state and candidate details.
- Ideology performance dots expose candidate/race/measure labels, and keyboard activation updates the live detail region. The constellation candidate selection and filters also remained functional in the wider interaction pass.
- No displayed interactive element lacked an accessible name. Closed mobile contents links were correctly excluded as hidden; their source text is present.

## Navigation and terminology

- The shared navigation consistently exposes Forecast, CMO, Ideology & caucuses, and Methodology/Methods routing with the appropriate current-page state.
- `Candidate Atlas` is absent from current public content and navigation.
- `legislators.html` redirects to `ideology-performance.html#issues`; `caucuses.html` redirects to `ideology-performance.html#candidate-explorer`.
- Searches found no stale `Fundamentals+`, `Basic model`, `historical_cmo`, `Alabama Election Labs`, or old candidate-quality-residual headline language in the six current pages.
- Current terminology distinguishes Direct CMO, Southern-prior residuals, Candidate Quality Index, and raw federal/presidential comparisons.

## Release recommendation

Approve the current deterministic build for publication. No blocking accessibility, responsive-layout, console, navigation, terminology, or test defect remains within the contracted scope.
