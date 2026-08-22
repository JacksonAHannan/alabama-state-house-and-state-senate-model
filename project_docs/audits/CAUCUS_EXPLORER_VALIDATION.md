# Caucus explorer validation

**Task:** `VALIDATE-CAUCUS-EXPLORER-001`
**Validated:** 2026-08-21
**Verdict:** **PASS**

The public and standalone caucus explorers reproduce the validated clustering
payload, all declared controls and candidate-detail paths work, the Republican
instability caveat is prominent, and the page remains readable without overflow
or application errors at desktop and exact 497-pixel width.

## Source and payload consistency

I decoded the embedded `const DATA` object from both `docs/caucuses.html` and
`artifacts/site/caucuses.html`. Each is exactly equal to a fresh in-memory call
to `scripts.build_caucus_analysis_page.payload()`.

Both pages contain:

- 281 candidate-cycle members;
- five cluster profiles;
- two selected-model diagnostics;
- two sensitivity rows;
- 14 cluster-era rows;
- 15 cluster/outcome performance summaries; and
- 18 issue axes.

All 281 CMO values match the validated membership source after JSON
serialization to within `4.98e-11`. Federal and previous-presidential outcomes
match their source columns to within `5.00e-11`. The public and standalone
pages contain no unresolved payload placeholder.

## Interactive controls

I exercised the rendered page in headless Microsoft Edge at both a 1,425-pixel
desktop client width and an exact 497-pixel mobile client width.

- **Party:** switching from Democrats to Republicans changes the overview from
  117/two clusters to 164/three clusters, replaces the tabs and profiles, and
  displays the Republican warning.
- **Caucus:** selecting another tab changes the active tab, title, profile, and
  candidate table. The checked Democratic transition changed 76 rows to 41.
- **Issue:** changing gun access to abortion access altered 15 of 19 comparable
  candidate dot positions and 58 displayed table values; the dot population
  changed from 50 to 32 according to evidence availability.
- **Outcome:** changing CMO to raw federal overperformance changes dot vertical
  positions while retaining the selected issue and cluster.
- **Era:** selecting 2016 and later changed the checked cluster table from 41
  to 20 candidate-cycles and rerendered the scatter.

Exactly one cluster tab remains active after each change. No control retains a
stale title, count, or plot.

## Candidate detail and search

Scatter points are keyboard-focusable buttons with candidate-specific
`aria-label` text. Clicking a dot highlights exactly one point and populates the
candidate name, election/district, cluster, incumbency/winner flags, CMO, and up
to eight strongest observed issue positions.

Clicking a candidate table row populates the same detail panel. In the checked
case the selected `PETE WARD` row and detail name agreed. Entering that name in
the search control reduced the current table to one matching row. Search also
supports chamber and district text through the same filtered string.

## Republican caveat and interpretation

The Republican view places a highlighted warning immediately after its four
overview metrics and before the three cluster tabs. It states:

> Weak discrete structure. Republican labels change substantially under
> alternate imputation and within-era normalization. Use them as historical
> tendencies, not stable caucus membership.

The overview simultaneously displays the low 0.239 imputation-stability ARI.
The caveat is therefore visible before a reader encounters the substantive
cluster labels at both tested widths.

## Responsive layout, navigation, and browser integrity

At desktop and exact 497-pixel width:

- horizontal overflow is zero;
- party, issue, outcome, era, and search controls are visible;
- warning, tabs, dashboard, scatter axes, side panel, member table, and search
  stay inside the viewport;
- no application console error occurs; and
- the ideology link is visible in both navigation and footer.

The reciprocal `caucuses.html` link is present on the rebuilt ideology page.
The public themed page does not load a remote display font.

## Tests

Command run:

```text
python -m pytest scripts/tests/test_caucus_analysis_page.py scripts/tests/test_ideology_performance_page.py scripts/tests/test_site_brand.py -q
python scripts/validate_agent_workflow.py
```

Results:

- focused site/ideology/brand suite: **14 passed**;
- agent workflow validation: passed.

## Release decision

**PASS.** The caucus explorer satisfies the source, interaction, caution,
responsive, navigation, and focused-test requirements. No blocking or
nonblocking publication finding remains.
