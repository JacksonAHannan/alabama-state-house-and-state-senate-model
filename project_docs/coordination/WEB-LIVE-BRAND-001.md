# Task contract: WEB-LIVE-BRAND-001 Blue/Oxblood production redesign

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Apply the approved Blue/Oxblood visual system and utilitarian copy hierarchy to every public site builder while preserving all existing data, maps, selectors, tables, deep links, and interactive behavior.
- Non-goals: No model estimation, warehouse mutation, geographic change, payload schema change, or alteration of published probabilities and CMO values.
- Upstream snapshot: Current working public builders and approved `WEB-BRAND-001` Blue/Oxblood direction as of 2026-08-21.
- Read scope: `docs/`; `dashboard/`; public-page builders; `artifacts/site/`; user portrait at `C:/Users/User/Desktop/images.jfif`.
- Write scope: `dashboard/blue_oxblood_theme.css`; `scripts/site_brand.py`; `scripts/build_blue_oxblood_site.py`; `scripts/build_ideology_thesis_page.py`; `scripts/build_legislator_ideology_page.py`; `scripts/tests/test_site_brand.py`; `artifacts/blue_oxblood_site/`; `docs/`; this contract and its active-task row.
- Warehouse mode: read-only.
- Inputs: Existing builder payloads, maps, JavaScript, CSS, and current approved model outputs.
- Outputs: Rebuilt release-candidate and public HTML pages with an embedded portrait, shared palette/typography, utilitarian titles, and unchanged functional contracts.
- Acceptance checks: Workflow validation; focused builder and site-brand tests; full public-site build; JavaScript compilation for all generated pages; browser console and responsive smoke tests; interaction checks for forecast map/chamber/model/district controls and CMO map/chamber/cycle/district controls; internal-link and artifact scan; no remote display-font imports; no placeholder maps; no data or probability diffs beyond markup/style copy; independent `validation_release` approval before push.
- Handoff recipient: `validation_release`.
- Known risks: Large self-contained HTML payloads, builder-specific class names, Leaflet initialization timing, generated-output drift, and accidental replacement of semantic party colors.

## Handoff

- Added a shared `dashboard/blue_oxblood_theme.css` production layer with the
  portrait embedded at build time, powder-blue page ground, oxblood structural
  accents, conventional installed fonts, and unchanged semantic party colors.
- Added `scripts/site_brand.py`; its transformation removes remote display-font
  imports, applies utilitarian copy replacements, adds `@electionsjack`, and
  asserts that embedded JavaScript and payload blocks remain byte-for-byte
  unchanged.
- Added `scripts/build_blue_oxblood_site.py`, which runs the forecast, CMO, and
  legislator builders, promotes the reviewed absolute-ideology candidate, and
  themes all six public pages. Themed copies and responsive screenshots are in
  `artifacts/blue_oxblood_site/`.
- Preserved and browser-tested the actual Leaflet forecast map, State
  House/Senate selector, district finder, map modes, and district details. Also
  preserved and tested the CMO SVG district map, all 16 cycle/chamber buttons,
  district selection, map modes, rankings, and candidate detail.
- Troubleshot two visual regressions found in the first render: nested CMO and
  atlas mastheads clipped the portrait, and featured status cells had invalid
  contrast. Both are corrected.
- Validation completed by implementer: 28 focused tests passed; JavaScript on
  all six pages compiled; desktop and 430px browser smoke tests passed with no
  console errors other than the intentionally ignored missing favicon; workflow
  and diff checks passed.
- Existing unrelated validation failure: the legislator-atlas test expects four
  Vote Smart profiles while the current source payload now contains five. The
  redesign does not change that payload or test.
- Release status: not committed or pushed. Repository rules require independent
  `validation_release` approval before publication, and the implementing agent
  cannot approve its own release.
