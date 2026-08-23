# Merged Democratic transition page validation

Date: 2026-08-22
Release candidate: `artifacts/site/ideology-performance.html` rebuilt 2026-08-22 20:15
**Verdict: PASS for publication.**

## Commands

```powershell
python -m pytest scripts/tests/test_ideology_performance_page.py scripts/tests/test_caucus_analysis_page.py -q
# 11 passed

python scripts/validate_agent_workflow.py
# Agent workflow validation passed.
```

I also ran the merged payload directly against the cluster CSVs and exercised the artifact with Selenium/Chrome at desktop width and CDP-emulated exact 497px and 390px CSS viewports. Browser checks changed every select control, selected a candidate from the table, selected a candidate point with Enter, inspected the compatibility redirect, measured document/table widths, and collected severe console messages.

## Source and analytical fidelity

- The research payload contains 274 unique current cluster members: 115 Democrats and 159 Republicans. The public Democratic constellation and table each render all 115 Democratic observations.
- The seven displayed cycle totals independently reproduce from `democratic_candidate_cluster_membership.csv`:

| Cycle | Traditionalist-populist | Progressive-modern | Total |
|---:|---:|---:|---:|
| 1998 | 26 | 3 | 29 |
| 2002 | 12 | 7 | 19 |
| 2006 | 17 | 4 | 21 |
| 2010 | 7 | 1 | 8 |
| 2014 | 10 | 4 | 14 |
| 2018 | 3 | 18 | 21 |
| 2022 | 1 | 2 | 3 |

- Headline means, standard errors, sample sizes, and differences exactly reproduce `democratic_cluster_summary.csv`:

| Measure | Traditionalist mean (n) | Progressive mean (n) | Difference |
|---|---:|---:|---:|
| CMO | +1.2977 (76) | -7.2919 (39) | +8.5896 |
| Raw vs. federal | +25.8282 (65) | +5.9851 (37) | +19.8432 |
| Raw vs. previous president | +25.9882 (74) | +1.4830 (35) | +24.5052 |

- Performance is attached after outcome-blind clustering, and the page labels these contrasts as descriptive rather than causal.
- The current 477,023-byte artifact embeds the full 274-member research contract while rendering the 115-member Democratic analytical view.

## Interface and compatibility checks

- Headline outcome, distribution outcome/era, and issue/era controls update their corresponding views.
- Candidate table selection and keyboard activation of constellation points update candidate details.
- The constellation renders 115 accessible candidate points and the table renders 115 Democratic rows.
- `artifacts/site/caucuses.html` contains both refresh and JavaScript redirects to `ideology-performance.html#candidate-explorer`; Chrome reaches that fragment successfully.
- Neither release artifact contains the former three-dimensional handlers, markup, or standalone `Legislative caucus explorer` interface.
- Static dependency inspection found no upstream read from `docs/`. `build_blue_oxblood_site.py` references `docs/` only as the downstream publication destination.

## Responsive and runtime checks

| Viewport | Document overflow | Candidate table | Severe console errors |
|---:|---:|---|---:|
| Desktop 1280px | 0px | contained | 0 |
| Exact 497px | 0px | contained | 0 |
| Exact 390px | 0px | intentionally scrollable inside its container | 0 |

At 390px the table viewport is 360px and its 396px content width remains locally contained; it does not widen the document.

## Pre-publication caveat

The broader `test_published_site_consistency.py` gate currently has one expected failure because `docs/ideology-performance.html` still contains the prior published page. This contract explicitly validates the release candidate before publication. The focused candidate tests pass, and publication should now copy/theme the approved artifact and redirect into `docs/`, after which the published-site gate must be rerun.

No release-candidate blocker remains.
