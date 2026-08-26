# WAR historical page release validation

## Decision

**BLOCK.** The WAR-first historical page, corrected HD-32 context, methodology, interaction behavior, accessibility, and focused tests all pass. Release is blocked by one visible cross-page naming inconsistency: `docs/index.html` still links to `cmo.html` with the label **Historical CMO model**, even though that destination is now the WAR-first historical model.

Validated independently on 2026-08-26 under `VALIDATE-WEB-WAR-PAGE-019`.

## Blocking finding

Current public markup contains:

```html
<a href="cmo.html">Historical CMO model</a>
```

This is a headline navigation/cross-link label for the overall historical model, not one of the explicitly supporting observed-CMO displays. It conflicts with the approved WAR-first naming contract and must be changed at its source and rebuilt before publication.

A visible-label sweep across `docs/*.html` found no other public `CQI`, `Candidate Quality Index`, `CMO model`, or `CMO methodology` label. The remaining CMO labels are appropriately scoped to the distinct observed measure, including the supporting CMO map/table column and the methodology section `CMO as the observed input`.

## WAR presentation checks

The historical page itself passes the naming contract:

- `<title>`: `Alabama Legislative Wins Above Replacement (WAR)`.
- H1: `Alabama Legislative WAR`.
- Shared primary navigation labels the route `WAR` and marks it current.
- The default active map mode is WAR and the page initializes `mapMode='quality'`.
- The first candidate table performance column is `WAR`; CMO follows as a separate column.
- Selecting Barbara Bigsby Boyd in 2010 HD-32 produces a headline of `+4.5 Candidate WAR`.
- Switching to the CMO map mode changes that same selected-candidate headline to `+30.3 CMO`; switching back restores `+4.5 Candidate WAR`.
- Methodology H1 is `WAR methodology`; section 1 is `What WAR estimates`.
- No public `CQI` or `Candidate Quality Index` copy appears in `cmo.html` or `cmo-methodology.html`.
- Split Ticket naming credit is present.

CMO remains correctly distinguished. The methodology states that CMO is the candidate-oriented legislative margin minus the selected same-district ticket margin, is directly auditable, and remains published alongside WAR as the observed performance being decomposed.

## HD-32 independent reconstruction

The corrected presidential feature row contains:

- Obama allocated votes: `11,826.996150`
- McCain allocated votes: `7,240.657863`
- Source complete: true

Independent arithmetic gives:

```text
2008 Democratic presidential margin
= 100 * (11,826.996150 - 7,240.657863)
        / (11,826.996150 + 7,240.657863)
= +24.052976 points

2010 Barbara Bigsby Boyd legislative margin
= 100 * (7,238 - 2,903) / (7,238 + 2,903)
= +42.747264 points

Raw presidential overperformance
= 42.747264 - 24.052976
= +18.694287 points
```

These values reconcile across:

- `2010_district_presidential_features.csv`
- `canonical_cmo_features.csv`
- processed and public `cmo_v6_southern_candidates.csv`
- processed and public `cmo_v6_southern_races.csv`
- the embedded `docs/cmo.html` payload

The embedded baseline identifies `2008 President`, Barack Obama, John McCain, and Democratic +24.05. The candidate row reports prior presidential margin +24.05 and presidential comparison +18.69. In-browser selection of the `2008 President` context renders Obama 62.0%, McCain 38.0%, and D+24.1 at the race's normalized two-party turnout.

Direct CMO remains +30.263799 and is therefore demonstrably not being overwritten by the corrected presidential comparison.

## Browser and accessibility checks

Chrome 151 was run at exact 1440px desktop and 390px mobile CSS viewport widths.

- `cmo.html`: `scrollWidth == clientWidth` at both widths; zero severe console errors; zero unnamed visible controls.
- `cmo-methodology.html`: same results at both widths.
- All candidate search/filter controls expose accessible names.
- The selected Boyd row exposes `Open BARBARA BIGSBY BOYD, 2010 House District 32, WAR +4.5`.
- Keyboard activation opens the detail panel.
- WAR/CMO map-mode keyboard activation updates active state and the candidate headline.
- Presidential-context keyboard activation displays the correct candidate names and margin.
- Desktop and mobile visual inspection found no clipped map controls, map, headline, result table, or methodology copy.

## Tests

```powershell
python scripts/validate_agent_workflow.py
python -m pytest scripts/tests/test_cmo_story_historical_cycles.py scripts/tests/test_site_brand.py scripts/tests/test_published_site_consistency.py -q
```

Results:

- Workflow validation passed.
- Focused suite: **19 passed**.

## Required remediation

Change the forecast-page cross-link at its generator/source from `Historical CMO model` to a WAR-consistent label such as `Historical WAR model`, rebuild the public pages, and request a narrow post-repair validation. No other blocker was found in the contracted scope.
