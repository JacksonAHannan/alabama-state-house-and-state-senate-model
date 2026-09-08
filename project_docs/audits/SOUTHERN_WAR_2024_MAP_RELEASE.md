# Southern WAR: 2024 coverage and Alabama explorer layout

Scope: extend the existing descriptive Southern v3 publication through 2024;
reuse the Alabama historical map layout. No forecast or research-only v4 model
was promoted, and no original election return was modified.

## 2026-09-08 release: certified Alabama lineage and independent approval

- Upstream v3 run `WAR-POST2016-V3-4AF79A70EAA8F39EBD49`, independently approved for
  descriptive historical use (`SOUTHERN_V3_INDEPENDENT_REVIEW_2026_09_08.md`;
  decision `SOUTHERN_V3_RELEASE_DECISION.json`). Historical data run
  `WAR-SOUTH-HIST-V1-45EC0B380AAEA007C2DF` on warehouse run
  `RUN-92AB8DE353AC47D6AECE3D7767C29FCD`: 116 slices, 4,280 strict races, 8,560
  orientations, 620 labeled 2016 backcasts, 302 reason-coded exclusions (151
  Virginia baseline, 151 experimental incumbency), two explicit empty slices.
- The unresolved source-file linkage noted below is closed: every strict race now
  carries a registered scalar source file. Alabama 2018 and 2022 races take the
  certified State Canvassing Board canvass through the reviewed canonical bridge,
  with 21 canonical totals corrected and Alabama third-party totals supplied from the
  certified sets (`ALABAMA_CERTIFIED_CANONICAL_REPAIR_2026_09_08.md`).
- New per-state release limitations: `state_release_coverage.csv` (hashed manifest
  output, published as `docs/data/southern_historical_war_v1_state_release_coverage.csv`)
  and the methodology section "State coverage and release limitations" with exact run
  IDs and machine-readable QA links; the map builder reconciles the file against the
  payload before writing.
- Map payload SHA-256 `825624e2a3f039141e5681859bd66f5f9f2823cf5f80eea93e8f8472c3d1f6e6`;
  join audit: 0 unmatched races, 0 duplicate keys, 0 invalid geometries, exact D/R vote
  conservation. `scripts/run_southern_war_browser_checks.mjs` (Playwright 1.63,
  Chromium 151) passed at 1258x900 and 390x844: all 116 slices, keyboard order,
  empty-slice explanation, no horizontal overflow, no console, page or request errors.
  11 map tests, 7 historical tests and 5 release-gate tests passed.
- Published on user authorization in commit `d4497d7` to `origin/master`
  (GitHub Pages serves `docs/`); the publication commit is the rollback reference.

The sections below record the 2026-09-05 release and are retained as history.

## Release

- Historical data run: `WAR-SOUTH-HIST-V1-D3EC2AC2CC508300EA1C`.
- 116 scheduled state/year/chamber maps, 9,644 district outlines, 4,280 strict
  D/R races and 8,560 candidate orientations.
- Added 770 eligible races from 2024 and 90 from 2023. The expanded scope adds
  20 election/chamber slices for 2024 and six for 2023.
- Alabama remains on its actual 2018/2022 regular schedule; no fictional 2024
  Alabama legislative election is added. Odd-year and staggered schedules are
  preserved. Two slices have no strict scored races and retain explicit empty states.
- Modern residuals, observed D/R votes, legislative margins and ticket baselines
  reconcile to the existing published v3 source. The 2016 backcast remains separately
  labeled. Fundraising is an optional display overlay, not a WAR input.

## Sources and map join

The existing source acquisition command now covers the complete 2016–2024
schedule. The 26 added ZIPs come from the official Census cartographic-boundary
archive, verified against the [Census download index](https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html)
and [2024 archive](https://www2.census.gov/geo/tiger/GENZ2024/shp/).
Previous ZIPs remain immutable; their registered hashes and retrieval dates are
preserved. `southern_legislative_geography_manifest.csv` records every URL, hash,
retrieval timestamp, geographic vintage, terms and authoritative display scope.
The existing raw-directory name is retained for path compatibility.

`docs/data/southern_war_map_join_audit.csv` contains one row per scheduled slice:
unique geometry/result keys, no unmatched scored race, no invalid delivered
geometry, and exact Democratic and Republican vote conservation through the join.
District outlines without a score remain distinct from WAR zero.

Display simplification at 1,800 meters produced invalid holes or island shells
for 22 otherwise-valid features across 16 slices. Those features now retain
their valid unsimplified projected source outline, with counts recorded in the
join audit. No vote allocation, boundary-vintage substitution, or source edit
is performed by this fallback. Display geometry is EPSG:5070, fitted to the
same 640-by-700 viewport as Alabama.

469 eligible legacy rows lack a source-file ID in the existing warehouse
interface. Their provider remains visible; the missing linkage is explicitly
labeled unresolved, not invented or certified by this release.

## Shared presentation

`dashboard/war_explorer.css` is extracted from the Alabama page. A characterization
test proves the Alabama template renders identically after extraction. The
Southern page uses the same shared site theme, map columns, panel spacing,
typography, racebox styles and symmetric +/-30-point map scale.

Selecting a district by map click, keyboard, district selector or race-table row
opens its race wikibox on the right. Changes of state, election or chamber clear
the prior selection. No district is automatically chosen because of its WAR.
Unscored districts explain their status without inventing results.

The wikibox displays both major-party candidates, observed votes and two-party
shares, incumbent flags, major-party winner, election date/stage and ticket
comparison. Baseline vote counts are explicitly turnout-normalized illustrations;
third-party votes are reported separately from the two-party denominator.
On narrow screens the detail stacks below the map and the table scrolls
horizontally to keep vote totals intact. Reduced motion and keyboard focus are
supported.

## Verification

- Baseline targeted suite before implementation: 10 passed.
- Alabama characterization test passed before and after CSS extraction.
- Final targeted release, geometry, source parity, layout, catalog and expanded
  context-manifest suite: 16 passed.
- Browser regression script: `scripts/tests/southern_war_browser_checks.js`.
  All 116 slices passed at 1440px, 900px and 320px during development, including
  empty states, selection, keyboard focus, filter retention and detail placement.
- Browser-computed desktop columns, panel padding, map-title font and wikibox
  heading font match the Alabama reference. Screenshots reviewed at desktop and
  mobile widths; mobile vote-number wrapping was corrected after visual inspection.
- Full repository suite completed in 1,480.01 seconds: 726 passed, one failed,
  12 warnings. Its sole failure was an older context-manifest test that still
  required 90 geometry slices. Updated that test to require all 116 exact
  scheduled keys, without changing the separately stored historical warehouse
  geometry or its assertions. The corrected test passed on the final failed-test
  rerun. No second full-suite run is claimed.
- All six publication input hashes match the current builder, template, shared
  style, theme, model manifest and geometry manifest. `git diff --check` passed
  for the changed implementation files.

## Reproduction

```powershell
python scripts/acquire_southern_legislative_geography.py --offline
python scripts/build_southern_historical_war_v1.py
python scripts/build_southern_war_map.py
python -m pytest scripts/tests/test_southern_historical_war_v1.py scripts/tests/test_southern_war_map.py scripts/tests/test_war_explorer_style.py scripts/tests/test_historical_war_story_page.py scripts/tests/test_data_catalog.py -q
```

For browser checks, serve `docs/` locally and open `southern-war.html`. Wait for
`#map .district` before evaluating the browser regression script (the payload
loads asynchronously). Evaluate at 1440px, 900px and 320px viewport widths.

The map builder applies the existing Blue/Oxblood theme itself, so a scoped
rebuild does not require rebuilding unrelated forecasts or ideology products.
The payload records builder, template, shared CSS, theme, model-manifest and
geometry-manifest hashes. The data catalog includes the release and map lineage.

The configured external design library was unavailable. The existing Alabama
page was the authoritative visual reference, as requested. Ponytail favored
sharing existing styling and using already-published 2024 residuals over adding
another design system or model implementation.
