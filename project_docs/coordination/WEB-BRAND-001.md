# Task contract: WEB-BRAND-001 branded site design directions

- Accountable role: `web_product`
- Owner: `/root`
- Status: `complete`
- Objective: Audit the public presentation patterns used by State Navigate, The Argument, and Silver Bulletin, then create multiple original visual directions for every public Alabama-model page using Jackson Hannan's portrait and `electionsjack` identity.
- Acceptance checks: A self-contained design gallery covers forecast, CMO, ideology, candidate atlas, and methodology page types in at least three selectable visual directions; the portrait is embedded rather than copied into raw data; each direction has a distinct typography, spacing, color, navigation, and data-display grammar; layouts remain usable at desktop and mobile widths; references are documented as inspiration rather than copied; the current `docs/` publication remains unchanged pending selection and independent validation.
- Read scope: current `docs/` pages; `dashboard/` styles; public pages on `statenavigate.org`, `theargumentmag.com`, and `natesilver.net`; user-supplied portrait at `C:/Users/User/Desktop/images.jfif`.
- Write scope: `scripts/build_site_design_mockups.py`; `artifacts/site/design-directions.html`; `project_docs/design/EDITORIAL_BRAND_DIRECTIONS.md`; this contract and its active-task row.
- Upstream inputs: current public site content and frozen publication payloads; user-supplied social identity `electionsjack`.
- Expected outputs: one interactive multi-page/multi-direction mockup gallery and a design-system recommendation document.
- Warehouse mode: read-only.
- Non-goals: No model changes, data re-estimation, raw-source mutation, or `docs/` publication.
- Handoff recipient: user direction, then `validation_release` before publication.

## Handoff

- Added `scripts/build_site_design_mockups.py`, which embeds the supplied
  portrait and builds a self-contained gallery without copying it into raw data.
- Added three selectable visual systems—Field Notes, Election Ledger, and Night
  Desk—and five page-specific templates—forecast, CMO, ideology, candidate
  atlas, and methodology. Theme and page selections have stable query-string
  state.
- Added `project_docs/design/EDITORIAL_BRAND_DIRECTIONS.md` with the reference
  audit, shared anti-trope rules, page grammar, and recommendation.
- Generated `artifacts/site/design-directions.html`; JavaScript syntax and the
  embedded-portrait/page/theme contract passed, desktop and narrow renders were
  inspected, and agent-workflow validation passed.
- Recommended direction: Field Notes as the shared base, Election Ledger density
  for forecast controls and tables, and Night Desk only as an optional election-
  night treatment.
- Revised all page titles, subheads, section headings, captions, and metadata to
  use literal product names, scope statements, variable definitions, and result
  labels. Thesis language and promotional/editorial headlines were removed from
  the presentation layer.
- Reworked the palette study around the light blue in the supplied portrait:
  powder blue with oxblood, gray blue with copper and charcoal, and deep slate
  with copper. Electoral party colors remain separate semantic chart colors.
- Restored the CMO product structure in the mockup: map, district selection,
  House/Senate tabs, cycle selector, candidate detail rail, and candidate-cycle
  plot. The production redesign is explicitly constrained to preserve all
  existing interactive controls and geography.
- Removed the remote fashion/display-font stack. Mockups now use conventional
  installed web faces: Arial/Helvetica for headings and interface text, Georgia
  for limited display values and long-form passages, and Consolas/Courier for
  metadata. Headline scale and spacing were reduced.
- Publication status: the live `docs/` site was not modified. The gallery is a
  design-selection artifact; the chosen system still needs to be applied to the
  production builders and independently validated.
