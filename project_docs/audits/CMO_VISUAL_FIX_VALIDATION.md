# CMO visual-fix validation

## Verdict

**PASS.** The score marker is separated from all scale labels, the race and baseline wikibox treatments meet readable contrast, the narrow detail panel no longer widens the document, and CMO interactions/data remain intact.

## Marker and label geometry

Installed Chrome was run with CDP device-metric overrides at 1280, exact 497, and exact 390 CSS-pixel widths. Three observed candidates were selected to exercise the full score scale:

- Jeffers, 1998 House District 86: 0.4th percentile
- Smith, 1998 House District 10: 49.6th percentile
- Carothers, 1998 House District 86: 99.6th percentile

For every candidate and viewport, the marker rectangle had zero intersection area with each of the `Lowest`, `Median`, and `Highest` label rectangles. The minimum vertical gap from the marker bottom to label top was 4 CSS pixels in all nine measurements. Thus both endpoint markers and the near-median marker remain visibly separate from their corresponding labels.

The detail panel also retained zero document overflow after each extreme candidate selection. At exact 390px, the remediated release reports `scrollWidth == clientWidth == 375`; the earlier min-content expansion is absent. A two-row career timeline likewise leaves document overflow at zero at all widths.

## Contrast

Computed foreground/background checks on selected-candidate detail views produced:

- `.racebox-head`: white on oxblood `rgb(116,59,66)`, contrast ratio 8.58:1.
- `.baseline-wikibox-head`: white on the same oxblood surface, contrast ratio 8.58:1.
- `.racebox-sub`: dark `rgb(33,27,27)` on pale rose `rgb(245,233,232)`, contrast ratio 14.31:1.

An effective-background scan of all visible elements found zero near-white foregrounds whose first opaque backing surface was light. The header treatments therefore exceed WCAG AA contrast for normal text, and no white-on-light-blue regression remains.

## Interaction and runtime checks

At all three widths:

- Selecting the 2022 Senate control left exactly one cycle/chamber control active.
- All four map modes—CMO, residual quality differential, governor comparison, and previous-presidential comparison—activated individually and updated their descriptions.
- Enter on a focusable mapped district with a winner opened the candidate detail.
- A resolved two-observation candidate timeline rendered both observations; its native buttons remained keyboard operable.
- Race and baseline wikibox content rendered for selected candidates.
- Horizontal document overflow remained zero.
- Chrome logged zero severe console/runtime errors.

The embedded payload and scripts parsed and initialized successfully. Existing focused consistency checks confirm the page retains current CMO controls, timeline behavior, and generated-data contracts.

## Commands and tests

```powershell
python -m pytest scripts/tests/test_cmo_story_historical_cycles.py scripts/tests/test_site_brand.py scripts/tests/test_published_site_consistency.py -q
python scripts/validate_agent_workflow.py
```

Result: `16 passed`; agent workflow validation passed.

Browser measurements were independently collected from `getBoundingClientRect()`, computed styles, effective ancestor backgrounds, DOM state, keyboard events, document scroll/client widths, and Chrome browser logs.

## Release decision

Approved for publication. No blocking findings remain.
