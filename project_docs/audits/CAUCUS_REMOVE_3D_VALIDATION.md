# Caucus 3D removal validation

**Task:** `VALIDATE-CAUCUS-REMOVE-3D-001`
**Validated:** 2026-08-21
**Verdict:** **PASS**

The public and staged caucus pages contain no remaining 3D markup, copy,
styles, controls, state, or handlers. The former residual `legend3d` class is
now the purpose-specific `constellation-legend`, and the constellation retains
its interactions, evidence encoding, and responsive behavior.

## Complete-removal checks

Static checks of `docs/caucuses.html` and the staged Blue/Oxblood artifact found
zero instances of the structured legacy tokens `legend3d`, `three-d`,
`threeD`, `render3D`, `axes3d`, `project3d`, `Three-dimensional`, and
`reset3d`. There is no drag-to-rotate copy, yaw/pitch/drag state, reset control,
3D SVG, 3D coverage element, or 3D event handler.

At desktop and exact 497-pixel effective client widths, the rendered DOM had
zero IDs or classes matching structured `3d`/three-dimensional patterns.
`#legendConstellation` now has only the class `constellation-legend`.
Incidental `3d` character sequences inside the embedded profile-image data URI
were excluded because they are binary payload text, not markup, copy, style, or
executable behavior.

## Constellation regression checks

In headless Microsoft Edge:

- the Democratic all-era view rendered 117 candidate-cycle points across 17
  dimensions;
- changing party rendered 164 Republican points across 13 dimensions;
- pointer hover displayed candidate, grouping, race, coverage, and CMO;
- keyboard Enter updated the candidate detail panel;
- prior click and era-filter regression checks remained covered by the focused
  page suite and the earlier narrow audit;
- evidence coverage continues to control point radius and opacity;
- party changes update constellation points, labels, coverage, and the
  Republican instability warning; and
- desktop and exact 497-pixel effective client widths had no horizontal
  overflow.

No application JavaScript error occurred. The only console entry was the
unrelated missing `favicon.ico` network 404.

## Commands run

```text
python -m pytest scripts/tests/test_caucus_analysis_page.py scripts/tests/test_site_brand.py -q
python -m http.server 8765 --directory docs
python scripts/validate_agent_workflow.py
```

Results:

- focused suite: **7 passed**;
- agent workflow validation: passed;
- generated/live-DOM 3D removal: passed;
- constellation browser and exact-width regression checks: passed.

## Release decision

**PASS.** The constellation-only caucus release satisfies the contract. No
blocking or non-blocking finding remains from this audit.
