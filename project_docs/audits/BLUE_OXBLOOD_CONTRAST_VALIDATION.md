# Blue/Oxblood contrast validation

- Task: `VALIDATE-CONTRAST-001`
- Reviewer: `/root/blue_oxblood_validation` (`validation_release`)
- Candidate: remediated `WEB-CONTRAST-001`, 2026-08-21
- Decision: **PASS**

The remediated candidate passes the complete contrast, visual, responsive,
functional, deterministic-build, and automated-test gates. The four previously
blocking classes are corrected: inactive forecast controls use dark text,
selected CMO controls use white on oxblood, ideology badges use darker
foregrounds, and heatmap counts have an opaque light backing with dark text.

## Computed contrast audit

Headless Chrome evaluated every visible element containing direct text. The
audit composited each computed foreground over its effective opaque ancestor
background, calculated WCAG relative luminance, and required 4.5:1 for ordinary
text and 3:1 only for qualifying large text.

| Page | Desktop nodes | Desktop failures | Mobile nodes | Mobile failures |
|---|---:|---:|---:|---:|
| Forecast | 887 | 0 | 570 | 0 |
| Forecast methodology | 59 | 0 | 53 | 0 |
| CMO | 1,274 | 0 | 1,267 | 0 |
| CMO methodology | 105 | 0 | 105 | 0 |
| Ideology and performance | 334 | 0 | 334 | 0 |
| Legislator atlas | 277 | 0 | 270 | 0 |

All **12 page/viewport combinations have zero computed contrast failures**.
Visual inspection of twelve fresh screenshots at 1440x1000 and the exact 497 px
effective mobile width confirmed the corrected states are legible and coherent.
The mobile legislator overview retains an unused fourth summary grid cell; this
is an aesthetic, non-blocking observation.

## Responsive and functional gate

- All six pages had exact 497 px client and scroll widths on mobile: zero
  document-level horizontal overflow.
- No application-level severe console errors were recorded (favicon noise
  excluded).
- Every discovered internal HTML destination returned HTTP 200.
- The forecast rendered 105 real Leaflet district paths; Senate switching
  rendered 35 paths, and district selection worked.
- The CMO rendered 105 real SVG district paths; switching to 1994 Senate
  rendered 35 paths. Its cycle/chamber and metric controls were present.
- Four embedded scripts compiled with Node and no remote Google/display-font
  references were present.

## Rebuild and tests

- Workflow validator: passed.
- Complete wrapper rebuild succeeded and all six public-page hashes remained
  unchanged.
- Focused release tests: **37 passed** in 9.76 seconds.
- Full suite: **360 passed**, 11 warnings, in 93.02 seconds.
- `git diff --check`: no whitespace errors (line-ending notices only).

Stable page hashes:

| Page | SHA-256 |
|---|---|
| `index.html` | `F98DB3BE151274A9DCC29EF69467D39D877F5E7226325D3182B733C8952B335D` |
| `methodology.html` | `380FE7623B316F8199608617A6C560CD0C9CDFAD5C33B49BD8E4DD78BF2282D1` |
| `cmo.html` | `5B793892C6D45DB847CD0E9AB199FAF27C07B0D5E64C770B3CA704D3BDC752C9` |
| `cmo-methodology.html` | `7D26FB9C6816C4B1B7E6460010707E1B4E1984880CA5A6C2C0E7E7A4116AD7B8` |
| `ideology-performance.html` | `727CC5F8384322DA5260B3C53492770064E438DE8B29DADF85D00BA5278FE025` |
| `legislators.html` | `97211ED4F1A1A8833845EEE82592FCFF7538615B5D62C75133DB6E311B1CB459` |

## Exact commands

```powershell
python scripts/validate_agent_workflow.py
python scripts/build_blue_oxblood_site.py
python -m pytest scripts/tests/test_site_brand.py scripts/tests/test_forecast_dashboard.py scripts/tests/test_cmo_story_historical_cycles.py scripts/tests/test_ideology_performance_page.py scripts/tests/test_legislator_ideology_page.py scripts/tests/test_published_site_consistency.py -q
python -m pytest -q
python -m http.server 8765 --directory docs
git diff --check
```

Additional Python-from-stdin Selenium checks performed computed contrast,
effective-width/overflow, console, internal-link, map, and control assertions;
Python/BeautifulSoup plus `node --check` validated embedded scripts; Playwright
captured the twelve visual-inspection renders.

## Release decision

**PASS.** The contrast remediation is independently validated for release. No
model, payload, warehouse, or data finding blocks publication.

## Selected-race wiki-box follow-up

A narrow follow-up independently selected modeled 1994 House and Senate races
on `docs/cmo.html` at desktop and exact 497 px mobile widths. In all four
chamber/viewport combinations, the visible `.racebox-head` computed to oxblood
`#743b42` with white `#ffffff` text. The WCAG contrast ratio is **8.58:1**, above
the 4.5:1 AA requirement for ordinary text.

The selected headers were `1994 Alabama House District 33` and `1994 Alabama
Senate District 23`. Both viewports retained equal client and scroll widths
(1403 px desktop; exactly 497 px mobile), and Chrome reported no application-
level severe console errors. **Follow-up decision: PASS.**
