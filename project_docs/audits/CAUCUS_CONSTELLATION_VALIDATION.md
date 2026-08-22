# Caucus constellation validation

**Task:** `VALIDATE-CAUCUS-CONSTELLATION-001`
**Validated:** 2026-08-21
**Verdict:** **PASS**

The all-issue constellation deterministically reproduces the clustering issue
space, displays every classified candidate-cycle with correct cluster and
evidence encodings, updates envelopes and centroids by party and era, supports
mouse and keyboard detail interaction, and retains the rotatable three-issue
view without responsive or browser regressions.

## Independent coordinate reproduction

I independently rebuilt the party-specific projection from the validated
membership and profile files, without calling the production coordinate
function:

1. select every issue column present in the party's cluster profiles;
2. standardize observed candidate positions;
3. apply distance-weighted seven-neighbor imputation;
4. standardize the completed matrix;
5. run metric two-dimensional MDS with the declared seed and parameters;
6. center, deterministically orient, and scale each axis to [-1, 1]; and
7. calculate observed-dimension coverage before imputation.

The result reconciles all 117 Democratic points across 17 dimensions and all
164 Republican points across 13 dimensions. Maximum absolute differences from
the embedded coordinates and coverage are below `5.0e-11`, the expected JSON
serialization tolerance. Independently reproduced stress values equal the
payload values: 14,017.1000 for Democrats and 21,477.7205 for Republicans.

Both `docs/caucuses.html` and `artifacts/site/caucuses.html` embed payloads
exactly equal to a fresh source payload.

## Point and evidence encoding

At both tested widths, all 117 Democratic candidate-cycles and all 164
Republican candidate-cycles render in the all-era view. For every Democratic
point I independently checked:

- screen x = `380 + constellation_x × 315`;
- screen y = `260 − constellation_y × 210`;
- radius = `3.5 + 6.5 × observed coverage`;
- opacity = `0.32 + 0.65 × observed coverage`; and
- fill color = the party palette entry for the validated cluster ID.

Maximum error across position, radius, opacity, and color is zero. The visible
key labels smaller/fainter points as less evidence and larger/stronger points as
more evidence. Accessible labels report candidate, cluster, and rounded issue
coverage.

## Envelopes and centroids

I independently recomputed cluster screen centroids and covariance-based
ellipses using the filtered rendered points. In the Democratic all-era view,
both centroids and both envelopes match every SVG coordinate/radius exactly.

Dynamic coverage also reconciles:

| View | Members | Centroids | Envelopes | Dimensions |
|---|---:|---:|---:|---:|
| Democratic, all eras | 117 | 2 | 2 | 17 |
| Republican, all eras | 164 | 3 | 3 | 13 |
| Republican, 2016+ | 32 | 2 | 2 | 13 |

The 2016+ Republican filter correctly omits the cluster with no candidate-cycle
in that era rather than leaving a stale envelope or centroid.

## Interaction and view tabs

The constellation is the default selected tab, with the three-issue panel
hidden and correct `aria-selected` state. Switching to the three-issue tab hides
the constellation and exposes the retained 3D chart. Dragging changes its
checked candidate coordinate from `(384.04, 177.83)` to `(345.14, 310.52)`;
reset restores the exact initial coordinate. Switching back restores the
constellation and tab state.

Constellation hover displays candidate name, validated cluster, cycle/race,
coverage, and CMO. Mouse click populates matching candidate detail and leaves
one focused point. A separate point activated with Enter likewise populates the
matching detail and leaves one focus marker. Points are focusable and implement
both Enter and Space activation.

Party and era changes rerender points, colors, legend, coverage, centroids, and
envelopes without stale elements.

## Projection and repetition disclosure

The page states that the map uses all issue dimensions used to fit the selected
party, nearby points represent more similar overall records, and the two display
dimensions are not individual issues. The page consistently calls observations
candidate-cycles rather than unique people, displays evidence coverage, and
retains the Republican imputation-instability warning before its cluster labels.

## Responsive and browser integrity

I inspected the page in headless Microsoft Edge at a 1,425-pixel desktop client
width and exact 497-pixel mobile client width. At both widths:

- document horizontal overflow is zero;
- the constellation wrapper remains wholly within the viewport;
- view tabs, evidence key, coverage text, labels, and SVG remain visible;
- all interaction paths above work; and
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

**PASS.** The constellation satisfies the deterministic-source, full-coverage,
evidence-encoding, envelope, centroid, interaction, retained-3D, caution, and
responsive requirements. No blocking or nonblocking release finding remains.
