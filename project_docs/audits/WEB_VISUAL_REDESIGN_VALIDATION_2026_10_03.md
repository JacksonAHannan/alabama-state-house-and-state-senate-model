# Maps and graphics redesign: local candidate validation, 2026-10-03

Task: `WEB-VISUAL-REDESIGN-20261003` (checklist `roadmap-05`). Scope: the presentation
layer of the forecast, Alabama WAR, Southern WAR, ideology and methodology pages,
built as local candidates only. Nothing under `docs/` was written; nothing was committed.

## Input snapshot

Working tree on 2026-10-03: HEAD `178d6f48` plus uncommitted work that this task
preserved and built on (candidate-identity module, forecast rerun of 2026-09-17,
rebuilt historical and career WAR, rebuilt caucus run). Forecast build
`08feb2c9669842846d3f`; Southern payload from run `WAR-SOUTH-HIST-V1-6D84680E7B757B057AF1`;
seats run `AL-SEATS-V1-44C73422B2A2A12D733C`.

## What changed

- **Basemap.** The CARTO raster basemap now returns "API KEY REQUIRED" watermark tiles
  on the live site. It is replaced by a self-drawn context layer (county lines and city
  labels from registered Census files, `scripts/site_geography.py`). The page no longer
  depends on any remote tile, script or font.
- **One map component** (`dashboard/site_map.js`) for the forecast and both WAR pages:
  - EPSG:5070 equal-area projection (the old WAR maps plotted raw longitude and were
    about 19% too wide);
  - Map and Tiles views, with equal-area tile layouts per districting plan;
  - zoom to the selected district, and metro zoom presets;
  - one keyboard tab stop with arrow-key movement;
  - linked hover with the other charts and the table.
- **Shared tokens** (`dashboard/site_components.css`): one type scale with chart text
  of 10px or larger; party, rating and WAR palettes; selected states and table headers
  in ink rather than oxblood.
- **Forecast page:**
  - natural-frequency toplines, with ">99.9%" in place of "100.0%";
  - seat strips with majority and median marks;
  - a 9-band legend with the cut-offs printed and a neutral toss-up;
  - full-strength fills that match the legend;
  - a seat-outcome square chart;
  - a search combobox that covers districts, candidates and cities;
  - a 100-dot outcome chart and a component waterfall in each district panel;
  - a competitive-seats dot chart;
  - a table with probability bars and interval strips;
  - a seats-won-since-1994 chart with unknown seats hatched;
  - a bottom-sheet district panel on phones.
- **Alabama WAR page:**
  - purple–orange residual scale (owner decision) with legend wording "Democrat or
    Republican ran ahead";
  - election timeline with a play button, and a strip of each cycle's median race WAR;
  - a dot chart of every race for the selected cycle;
  - a residual waterfall;
  - the race box and baseline tabs, kept;
  - a ranked career chart with a table fallback;
  - title-case display of names printed in capitals;
  - a clean template replacing the regex patch chain over the retired CMO template.
- **Southern WAR page:**
  - "The South at a glance": one small map per state for the chosen election and chamber;
  - the state explorer rebuilt on the shared map, with Tiles, waterfall and race dot chart;
  - the `--artifact-only` flag added.
- **Ideology page:**
  - five-color group palette chosen to be separable under simulated deuteranopia and
    protanopia, with a distinct mark shape per group;
  - issue rows oriented with the liberal pole on the left, using the renderer's existing
    `LIBERAL_POLE` convention, with both poles labelled;
  - WAR-by-group chart with axis ticks, non-overlapping dots and labelled means;
  - new two-issue scatter with on-demand group outlines and drag-to-select into the
    members table;
  - per-person issue positions in the member detail, which were previously empty;
  - page shell aligned with the rest of the site.
- **Methodology pages:**
  - forecast pipeline diagram;
  - 2022 holdout chart of predicted against actual margin, whose MAE is checked against
    the manifest at build time;
  - WAR identity diagram on both WAR methodology pages.
- **Copy corrected to match the model:**
  - The forecast detail panel and WAR timelines had said candidate history was not used.
  - The historical WAR methodology said the forecast sets candidate WAR to zero.

## Checks run (all on the local candidates)

| Check | Result |
|---|---|
| Payload invariance vs published `docs/index.html` | Races, seat distributions, models and meta identical; added `geometry`, `context`, `seatHistory`, `outcomeOffsets`, `probability`; only the build-date `asOf` fields differ (set to today's date by existing builder behavior) |
| Payload invariance vs published `docs/cmo.html` | All 16 sections identical apart from `paths` → `plan` |
| Southern payload vs published | Every slice's races and district set identical; tiles, labels and outlines added (`test_candidate_payload_adds_tiles_and_outlines_without_changing_races`) |
| Page-level horizontal overflow, 8 pages × 390/768/1440 px (rechecked after review fixes) | 0 everywhere (the previous 56 px overflow on the WAR page at 390 px is fixed); wide methodology diagrams scroll inside their own figure |
| Console errors, same 24 loads | None |
| Skip links | Exactly one per page (the theme pass now removes a template's own skip link before adding its own) |
| axe WCAG 2 A/AA, 14 page states (including districts open, Senate tiles, Texas detail, methodology pages) | 0 violations, after darkening the ideology teal to `#167a6c`, choosing label color by contrast and fixing the pipeline-diagram text the theme had recolored |
| Rendered chart text | 11 px or larger at 390, 768 and 1440 px; one exception, the seat-history axis at 390 px, measures 10.9 px |
| Keyboard | Forecast and WAR maps expose one tab stop with no outline clash (selection stroke instead); arrows move; Enter opens; Escape closes and returns focus to the map, row or dot that opened the panel; Southern dot chart opens on Enter; ideology scatter has one tab stop, arrow keys and Enter; WAR timeline responds to arrow keys |
| Focused tests (final run, `-p no:cacheprovider`, no testmon deselection) | `test_site_geography` 5, `test_site_brand` 10, `test_war_explorer_style` 2, `test_forecast_dashboard` 24, `test_historical_war_story_page` 7, `test_southern_war_map` 13, `test_product_stale_input_gates` 19, `test_published_site_consistency` 6, `test_alabama_war_generic_forecast` 4, `test_silver_pollster_quality_gate` 1, `test_forecast_candidate_history` 7, `test_alabama_seats_by_cycle` 16: 114 passed, 0 failed |
| `scripts/validate_agent_workflow.py` | Passed |
| `test_democratic_caucus_page` on the working tree | 4 pass; 6 fail or error because the working-tree caucus run is `descriptive_groupings_labels_pending_owner_review` and the release gate refuses it. That predates this task. The same 9 payload and template tests pass when pointed at the last approved (HEAD) run. |

Tests that pinned the retired implementation (Leaflet and CARTO URLs, remote fonts, the
CMO template hash, old legend strings, the "candidate history not used" copy) were replaced
by checks of the new behavior. Data-contract tests were kept.

## Open items and limits

- **Forecast exports blocked** (`FORECAST-VISUAL-EXPORTS-20261003`). *Resolved 2026-10-04; see "Owner follow-ups".* The auto-mode
  classifier denied the forecast script's `main()` edit, so the polling-replay
  "forecast over time" and "environment versus seats" charts are not built. The script
  is half-edited and must not be run until the owner decides.
- **Ideology candidate.** *Resolved 2026-10-04: the owner approved names for the two-group solution; the page now renders the approved run.* Rendering waited for owner approval of the rebuilt caucus
  labels. The preview stage holds a QA render of the approved HEAD run.
- **1994 source finding** *(repaired 2026-10-05 under `ALABAMA-1994-PARTY-LABELS-20261004`; see that audit)* from `ALABAMA-SEATS-BY-CYCLE-20261003`: 1994 canonical party
  labels come from ballot-order inference and conflict with Klarner in 19 districts. This
  likely affects 1994 historical WAR orientation and needs a source adjudication.
- **Theme override layer.** It remains for the methodology and landing pages, which keep
  older CSS; 2 dead rules were pruned (109 `!important` declarations remain).
- **Payload sizes** (themed preview pages against the published pages).
  - Forecast page: 0.84 MB (was 1.15 MB).
  - WAR page: 4.28 MB (was 3.67 MB; 2.6 MB of that is the unchanged race payload).
  - Southern payload: 8.74 MB (was 7.61 MB).
- **WAR legacy copy.** `build_war_story_page.py` also writes
  `artifacts/site/alabama-legislative-war-legacy.html`, an identical copy of the
  candidate. This is existing builder behavior and the task left it unchanged.
- **"2022 result" map mode not added.** *Resolved 2026-10-04; see "Owner follow-ups".* The forecast table already shows prior results. A
  map mode would color 2026 districts by 2022 outcomes, which is only valid if the 2025
  remedial lines match the 2022 plan for the districts shown. The geometry comparison was
  inconclusive, so the mode was left out rather than risk the plan substitution that
  AGENTS.md forbids. The existing prior-result column raises the same question and should
  be checked under a source task.
- **Not tested:** screen readers and physical devices.

## Independent review and fixes

A separate reviewer audited the candidates in a browser and against the contracts. Every
finding was fixed and rechecked. The checks table above reflects the state after these
fixes.

- **Blockers.**
  - The forecast scenario waterfall drew the scenario's environment shift inside the
    baseline step, which left the scenario step empty. The shift is now removed from the
    earlier running totals, so it appears on its own step and the steps still end at
    the scenario margin.
  - Enter on a Southern dot-chart mark called `click()` on an SVG circle, which does
    nothing. It now opens the district.
  - The forecast rating chip failed text contrast on some ratings. It now uses ink text
    with a color swatch.
- **Should-fix.**
  - The WAR percentile bar used the party-direction gradient for a candidate-oriented
    percentile. It is now neutral.
  - Focus outlines clashed with map strokes.
  - Closing a panel lost focus. It now returns to the origin.
  - Charts were drawn at a fixed width and scaled down. They are now sized to their
    container, which keeps text at its stated size.
  - Halo widths did not scale with zoom.
  - The scatter was mouse-only.
  - The inactive map layer was exposed to assistive technology. It is now `aria-hidden`.
  - Tile labels had low contrast.
  - The forecast table lacked a note about margins clipped at ±40.
  - The seat-history chart lacked a link to its reconciliation file.
- **Minor.**
  - Label overlaps in profiles, waterfalls and the drift strip.
  - Legend grouping roles.
  - Plurals ("1 seat").
  - Missing captions, and text below 11 px.
  - A district with no contested race now says so instead of showing the cycle overview.
  - Names printed in capitals are shown in title case.
  - Chamber-card chrome.
  - Duplicate skip links.
  - Tooltips stayed open after tap.
  - Seat-strip marks intercepted pointer events.
  - "GSU" stub names in the candidate display.

## Owner follow-ups, 2026-10-04

- **District selection.** Clicking a map district in Brave drew a large rounded focus ring around the district's bounding box, scaled by the map zoom (owner screenshot).
  - The map shapes now suppress outlines in every focus state, not only `:focus-visible`, with the rule `svg [tabindex]:focus`.
  - Keyboard focus still shows as the shape's stroke.
  - A selected district keeps full color under a white-haloed ink outline with a soft shadow. Other districts fade to 50%, and the highlight filter's 22% dimming still takes precedence.
  - This applies to all three map pages.
  - The ideology scatter marks also lacked a keyboard focus indicator. They now get an ink stroke.
- **Hatching never drew on the map view.** The hatch overlay was a `<use>` of each district path, and the path's own fill overrides a `<use>` fill. The overlay is now a copied path, created when first needed and dimmed with its district. Stripe spacing stays constant on screen at every zoom.
  - The forecast's "incumbent's party trails" hatch therefore never showed on the map. No district currently trails, so nothing published was wrong.
- **"2022 result" map mode added.**
  - `scripts/audit_2022_2026_plan_equivalence.py` writes `data/processed/elections/alabama_2022_2026_plan_equivalence_v1/`. Its findings:
    - The Census 2022 block equivalency file and the warehouse 2024-election block assignment agree on every block for all 140 districts.
    - The page's TIGER 2025 polygons overlap the 2021 enacted shapefile with an IoU of at least 0.99774 (HD20).
    - 105/105 House and 35/35 Senate districts are equivalent.
    - SD25 and SD26 are conditional on the reinstated 2021 Senate plan governing 2026. A 2025 remedial plan was lifted on 2026-05-29; its geometry is not in the repository.
  - A read-only investigation also tested block internal points and representative points, and ran a negative control against the pre-2021 plan. These checks are not reproduced by the script. The few differing blocks are TIGER-vintage artifacts: they include HD20/22 (4 people), HD98/102 (8 people) and SD17/20, where one block is split.
  - The renderer refuses to build if the audit does not hash-match the geometry it draws.
  - The mode colors 2022 two-party margins on the forecast's margin scale. Seats unopposed by the other major party are hatched in the winner's solid color, and a non-equivalent district would be gray.
  - Only 25 House and 8 Senate districts had a 2022 D-vs-R contest.
  - **Contradictions found:** `project_docs/model/MODEL_READINESS.md` says the 2026 Senate uses the remedial plan. That is stale: the TIGER 2025 manifest, the roster reversion and the 2026-05-29 ruling all point to the 2021 plan. `2026_FORECAST_READINESS.md` calls a representative-point check a "centroid" check; the counts it quotes are reproduced.
- **Forecast charts added.** These sit on the new exports from `FORECAST-VISUAL-EXPORTS-20261003`, build `ebf2d7e172b6f0e1a66a`. Every earlier forecast export is byte-identical.
  - **"If the polls are off".** Simulations grouped by the shared statewide polling miss, shown as median and middle-80% seats against the majority line, with a histogram of how often each miss occurs.
    - The House median moves only from 29 to 30 across misses of up to 8 points either way.
    - No simulated environment makes a Democratic majority the median outcome in either chamber.
  - **"How the outlook moves with the polls".** A weekly replay of today's model under each week's polling average.
    - It covers only 2026-07-14 to 2026-09-08: the quality-gated catalog holds 12 polls, the first ending 2026-06-22.
    - The page states that this is not a record of past forecasts, that polls are dated by field end date rather than release date, and that the roster is today's for every date.
- **Ideology page.**
  - The owner named the two groups "Progressive Democrats" and "Traditional Democrats".
  - The labels from the five-group solution approved on 2026-09-15 are kept in `data/manual/ideology/backups/`.
  - After the 1994 repair, the caucus run `AL-DEM-CAUCUS-V1-50163B73E5B72BC8A0F9` still selects two groups, now of 55 and 186 people, and the page renders it. It no longer needs the QA render of the HEAD run.
- **1994 repair effects visible on the pages.**
  - The seats chart shows 1994 as House 74 D / 31 R and Senate 23 D / 12 R, with no unknown seats.
  - The WAR page shows the corrected 1994 universe.
  - House 1 1994 appears through the no-score panel, which states that its WAR is withheld by adjudication.
- **Checks.**
  - Final focused run after all rebuilds (2026-10-05). Each of 29 test files was run on its own with `-p no:cacheprovider`.
    - All pass except `test_published_site_consistency::test_publication_exports_match_current_model_outputs`.
    - That test fails as expected, because the published `docs/data` historical WAR files lag the repaired outputs until republication.
  - Earlier focused tests in this round:
    - `test_plan_equivalence_2022_2026`: 5 passed.
    - `test_forecast_polling_replay` with `test_forecast_dashboard`: 27 passed.
    - The forecast and model tests listed in the forecast-exports handoff: 21 passed.
    - The site page tests: 67 passed.
  - Browser:
    - No console errors on the forecast, WAR and Southern pages after the changes.
    - The 2022 mode hatches exactly the 80 unopposed House seats and clears the hatching when switching back.
  - axe:
    - The 2022 mode has no WCAG A/AA violations.
    - One best-practice `region` finding is pre-existing: the forecast hero sits outside `<main>` on the published page too. It was left unchanged.
