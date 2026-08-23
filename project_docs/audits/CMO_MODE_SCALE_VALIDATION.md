# CMO mode-scale validation

## Verdict

**PASS.** All four map modes use their intended measure, scale, palette, legend, tooltip language, and selected-candidate headline. Mode switching preserves candidate identity and party orientation, unavailable values remain unavailable, and responsive/runtime gates pass.

## Mode configuration and map rendering

The independent browser audit reproduced the following configuration from the rendered page:

| Mode | Scale and palette | Legend |
|---|---|---|
| CMO | Linear, symmetric ±30; red → neutral → blue | R +30, R +15, Even, D +15, D +30 |
| Residual quality differential | Linear, symmetric ±20; gold → cream → teal | R +20, R +10, Even, D +10, D +20 |
| Raw vs. governor | Linear, symmetric ±30; red → neutral → blue | R +30, R +15, Even, D +15, D +30 |
| Raw vs. previous president | Linear, symmetric ±30; red → neutral → blue | R +30, R +15, Even, D +15, D +30 |

For selected 1994 House District 86, actual SVG fills matched independently invoked mode-color calculations in all modes. Values beyond the cap clipped visually without changing the displayed raw headline value. Carothers' CMO/governor/presidential fills clipped to blue `#3d77a8`; residual quality rendered a distinct teal `#3f8a86`. The map and candidate scale gradients both changed to the gold/cream/teal quality palette and returned to the red/neutral/blue palette for the other measures.

Exactly one mode button remained active after every switch. Map subtitles, accessible map labels, tooltip wording, and five legend ticks changed with the selected measure.

## Selected-candidate synchronization and orientation

A contested Democratic/Republican pair in the same race was selected from the current payload and switched through all modes without reselecting the candidate:

- Carothers (D): CMO +64.9; residual quality +17.5; governor +43.5; previous president +53.5.
- Shuemake (R): CMO -64.9; residual quality -17.5; governor -43.5; previous president -53.5.

These values exactly reproduce the underlying race values with the intended candidate-party orientation. Republican headlines are the sign inverse of the Democratic race-oriented map value rather than retaining a stale Democratic sign. The selected district remains highlighted through mode changes.

Headline labels change with the measure and recompute the percentile from the active cycle/chamber candidate distribution. The remediated ordinal formatter now renders `2nd percentile` and `5th percentile` correctly, including at all tested responsive widths.

## Missingness

The current payload contains 42 candidates whose previous-presidential district comparison is unavailable. Selecting McClammy in 1994 House District 76 and then switching to the presidential mode produced:

- headline value `Unavailable`;
- no percentile scale/marker;
- neutral-gray district fill `#deded9`;
- an accessible map label that does not invent a benchmark value.

The current payload has no candidate-level missing governor comparison, so a live governor `Unavailable` candidate case does not exist to exercise. Governor and presidential modes use the same null-preserving `candidateMetric`/`color` branch; inspection confirms neither converts null to zero.

## Responsive interaction and runtime

Chrome was tested at 1280, exact 497, and exact 390 CSS-pixel widths.

- All four modes updated the legend, palette, map, and already-selected headline at each width.
- Cycle/chamber switching cleared stale candidate selection and left one control pressed.
- Enter on a focusable mapped district opened its detail.
- A resolved two-race timeline rendered both observations and remained functional.
- Horizontal document overflow was zero at every width.
- No application JavaScript/runtime errors occurred. The local HTTP server emitted one non-application 404 for an unsolicited `/favicon.ico` request on its first load; this does not affect the page or published assets.

## Tests

```powershell
python -m pytest scripts/tests/test_cmo_story_historical_cycles.py scripts/tests/test_site_brand.py scripts/tests/test_published_site_consistency.py -q
python scripts/validate_agent_workflow.py
```

Result: `16 passed`; agent workflow validation passed.

Browser checks used the rebuilt candidate at `http://localhost:8765/cmo.html`, computed payload values, rendered fills/gradients, DOM state, keyboard events, exact viewport dimensions, and browser logs.

## Release decision

Approved for publication. No blocking findings remain.
