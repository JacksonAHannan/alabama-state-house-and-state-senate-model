# Merged Democratic transition page

Date: 2026-08-22
Task: `WEB-MERGED-DEMOCRATIC-TRANSITION-001`

## Outcome

The standalone ideology and caucus dashboards were consolidated into one public
research page. `ideology-performance.html` is the canonical page;
`caucuses.html` is retained as a redirect to its candidate-explorer section.

The page is organized around the historical question: whether the
traditionalist-populist Democratic bloc sustained greater electoral distance
from federal partisanship than the progressive-modern bloc.

## Source contracts

- Regression estimates and issue evidence are read from the validated absolute-
  ideology rebuild under `research/cmo_ideology/`.
- Cluster membership, profiles, performance summaries, and diagnostics are read
  from `research/cmo_ideology/democratic_clusters/`.
- No warehouse tables or model outputs are changed by the page builder.
- Election performance is attached after issue-only clustering and does not
  determine membership.

## Implemented views

1. Descriptive bloc means for CMO, federal-baseline overperformance, and
   previous-presidential overperformance, with group standard errors.
2. Cycle-by-cycle Democratic bloc composition from 1998 through 2022.
3. Ranked bloc-profile differences on the ten most distinguishing issue axes.
4. Candidate-level performance distributions with outcome and era controls.
5. Era-specific absolute Shor–McCarty slopes, including an explicit unestimated
   post-2016 result where the Democratic sample is insufficient.
6. Issue-level candidate explorer with pole-balance counts and limited-
   comparison warnings.
7. Upper-decile and median case observations for both Democratic blocs.
8. Two-dimensional all-issue similarity projection, candidate details, and a
   searchable candidate-cycle table.
9. Method and limitation notes separating descriptive bloc comparisons,
   regression estimates, and causal claims.

## Presentation decisions

- Traditionalist-populist Democrats use oxblood; progressive-modern Democrats
  use dark blue throughout.
- The prior three-dimensional view was removed.
- Republican clusters were removed from the primary interface because their
  discrete structure is less stable and they do not answer the page's central
  historical question.
- The single maximum performer is not used as a representative case. The page
  uses an observation nearest each bloc's 90th percentile and another nearest
  its median.
- Global navigation has one `Ideology & caucuses` entry. The shared theme step
  is idempotent and removes any older duplicate theme block before applying the
  current presentation layer.

## Checks completed before independent validation

- Workflow scope validation passed.
- Focused page tests: 11 passed.
- Browser runtime generated all seven transition rows, 102 default performance
  points, and 115 Democratic constellation points.
- Mobile emulation at 390 CSS pixels reported document width equal to viewport
  width. The wide candidate table remains intentionally contained in its own
  horizontal/vertical scroll region.
- Outcome, era, issue, candidate selection, and redirect interactions were
  exercised without JavaScript console errors.

## Publication gate

The release candidate received an independent PASS before publication. The
first post-publication review found that the forecast and forecast-methodology
headers omitted the merged ideology link. The shared navigation transformer was
updated and the site was rebuilt. All six substantive public-page headers now
contain exactly one `Ideology & caucuses` link and no header links to the former
standalone caucus page.

Final local checks after the navigation repair:

- Full repository test suite: 476 passed.
- Focused publication and page tests: 21 passed.
- Published browser checks: 115 Democratic table rows and 115 constellation
  points; no severe console errors; no document overflow at 390, 497, or 1440
  CSS pixels; legacy URL redirects to `#candidate-explorer`.
