# Caucus three-dimensional view validation

**Task:** `VALIDATE-CAUCUS-3D-001`
**Validated:** 2026-08-21
**Verdict:** **PASS**

The three-dimensional caucus view derives its axes from the declared profile
range rule, plots complete-case candidates and source profile centroids exactly,
discloses sparse coverage, supports rotation/reset and candidate selection, and
renders without overflow or browser errors at desktop and exact 497-pixel width.

## Axis derivation

I independently calculated the range of every cluster-profile issue mean within
each party. The three largest ranges are exactly the embedded and rendered axes:

| Party | Axis | Profile range |
|---|---|---:|
| Democratic | Abortion access | 1.617 |
| Democratic | Marriage equality | 1.200 |
| Democratic | Anti-discrimination | 1.158 |
| Republican | Labor or management | 2.000 |
| Republican | Ethics and transparency | 1.909 |
| Republican | Gun purchase rules | 1.760 |

The next-largest Democratic and Republican ranges are respectively 1.083 and
1.733, confirming that the chosen axes are the strict top three rather than a
manually selected subset.

Both `docs/caucuses.html` and `artifacts/site/caucuses.html` embed payloads
exactly equal to a fresh `payload()` call, including these distinguishing-axis
arrays.

## Candidate and centroid fidelity

For each party I filtered source members to complete cases on its three axes and
recomputed the initial yaw/pitch projection independently. I also projected each
source cluster-profile centroid. Comparing those coordinates to every rendered
SVG circle produced zero maximum nearest-coordinate error:

| Party | Complete candidates | Centroids | Maximum coordinate error |
|---|---:|---:|---:|
| Democratic | 16 | 2 | 0.0 |
| Republican | 2 | 3 | 0.0 |

The source centroid values are preserved exactly in the payload. Centroids are
rendered as larger outlined points and labeled C1/C2 or C1/C2/C3; they are not
substituted for candidate observations.

## Coverage and sparse-case disclosure

The visible coverage line reports `16 complete candidate-cycles · 2 cluster
centroids` for Democrats and `2 complete candidate-cycles · 3 cluster
centroids` for Republicans. The Republican subtitle explicitly adds:

> Individual complete-case coverage is sparse; the large outlined points are
> the cluster profile means.

Changing Republicans to the 2016-and-later era updates the view to one complete
candidate-cycle while retaining the three profile centroids. Source counts by
era reconcile to 14/1/1 for Democrats and 0/1/1 for Republicans.

## Browser interactions

I tested the public page in headless Microsoft Edge at a 1,425-pixel desktop
client width and an exact 497-pixel mobile client width.

- Dragging the SVG changed the checked candidate coordinate from
  `(384.04, 177.83)` to `(346.99, 311.55)` at both widths.
- Reset restored the exact initial `(384.04, 177.83)` coordinate.
- Hovering a candidate displayed its name, cluster, and all three axis values.
- Clicking it populated the existing candidate detail panel, left exactly one
  focused 3D point, and agreed with its accessible candidate label.
- Switching party changed all three axis labels, candidate/centroid counts,
  legend, and sparse-coverage explanation.
- Switching era changed the candidate point population and coverage line.

All candidate points have `tabindex=0`, a source-derived `aria-label`, and
Enter/Space activation logic.

## Responsive and browser integrity

At desktop and exact 497-pixel width:

- document horizontal overflow is zero;
- the 3D wrapper, SVG, tools, coverage line, and reset button remain inside the
  viewport;
- the mobile tool row stacks without clipping;
- all axis labels and coverage text render; and
- no application console error occurs.

## Tests

Commands run:

```text
python -m pytest scripts/tests/test_caucus_analysis_page.py scripts/tests/test_site_brand.py -q
python scripts/validate_agent_workflow.py
```

Results:

- focused page/brand suite: **7 passed**;
- agent workflow validation: passed.

## Release decision

**PASS.** The 3D view satisfies the source, axis, complete-case, centroid,
coverage, interaction, accessibility, and responsive requirements. No blocking
or nonblocking release finding remains.
