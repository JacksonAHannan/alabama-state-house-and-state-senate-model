# Ideology headline context validation

## Verdict

**PASS.** The corrected ideology headline is arithmetically faithful to the named inputs, restricts identification to election contexts containing both Democratic blocs, reports person-clustered uncertainty, and renders without a responsive or accessibility regression.

Validated independently on 2026-08-24 against the `WEB-IDEOLOGY-HEADLINE-CONTEXT-001` review candidate.

## Independent reconstruction

I read `democratic_candidate_cluster_membership.csv`, replaced its superseded quality field by a validated one-to-one join to `cmo_v5_candidates.csv` on `canonical_candidate_id`, and independently fit each specification without calling the page builder's contrast helper.

For each outcome I:

1. retained Democratic rows assigned to one of the two displayed blocs with a finite outcome;
2. formed `cycle-chamber` strata;
3. retained only strata where the traditionalist indicator took both 0 and 1;
4. regressed the outcome on the traditionalist indicator plus cycle/chamber fixed effects;
5. computed a finite-sample-corrected sandwich covariance clustered by nonblank `person_id`, falling back to `canonical_candidate_id` only where person identity was unavailable.

The independent results match the staged and published payloads to floating-point precision:

| Outcome | Difference | Clustered SE | Approx. 95% interval | n | People | Strata |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Candidate Quality Index | +4.502813 | 2.103186 | +0.380567 to +8.625058 | 107 | 103 | 10 |
| Raw vs. federal baseline | +11.214963 | 6.172518 | -0.883173 to +23.313099 | 93 | 90 | 9 |
| Raw vs. previous president | +19.406419 | 6.187329 | +7.279255 to +31.533584 | 101 | 97 | 10 |

The CQI and presidential comparisons use these ten overlap cells: 1998 House/Senate, 2002 House/Senate, 2006 House/Senate, and the 2010, 2014, 2018, and 2022 Houses. The federal comparison excludes 2006 Senate because it does not have two-bloc finite support, leaving nine cells. No non-overlap cell enters a fitted estimate.

The staged artifact and `docs/ideology-performance.html` contain identical headline records, including the method identifier `cycle_chamber_fixed_effects_person_clustered_se`. All standard errors and interval endpoints are finite. The lower people counts relative to rows confirm repeat appearances are grouped rather than treated as independent observations.

## Copy and payload audit

- The headline says the estimates compare candidates within the same election year and chamber.
- The support note explicitly says only cycle-and-chamber cells containing both blocs are used.
- The direction is clearly labeled traditionalist-populist minus progressive-modern.
- The result is described as an adjusted descriptive contrast, not a causal effect.
- The former `Traditionalist-populist mean`, `Progressive-modern mean`, and `Performance relative to three expectations` headline copy is absent from both staged and published HTML.
- Headline payload rows contain a single adjusted `difference`, uncertainty, support counts, and method. They do not contain the old `traditionalist_mean` or `progressive_mean` fields.
- Raw candidate observations remain available in the separate exploratory displays; they are not mislabeled as the adjusted headline estimand.

## Tests

```powershell
python -m pytest scripts/tests/test_ideology_performance_page.py -q
python scripts/validate_agent_workflow.py
```

Results:

- **13 passed**.
- Agent workflow validation passed.

## Browser validation

Chrome 151 was run against the published page at exact 1440px desktop and 390px mobile CSS widths.

- `documentElement.scrollWidth == clientWidth` at both widths (1440/1440 and 390/390).
- No substantive severe console messages occurred.
- Desktop headline bounds were left 184px, right 1256px, width 1072px.
- Mobile headline bounds were left 15px, right 375px, width 360px.
- All three forest tracks and their interval/value copy stayed within those bounds.
- At 390px the three cards stack cleanly; no interval, label, count, or comparison-set note is clipped.
- Each forest track exposes a descriptive `role="img"` accessible name containing the outcome, estimate, and interval.
- The candidate search input is associated with its visible `Search candidates` label; no displayed interactive element was unnamed.
- Visual inspection found readable blue/oxblood contrast and coherent desktop/mobile hierarchy.

## Release recommendation

Approve the current ideology headline candidate for publication. No blocking arithmetic, support, uncertainty, copy, rendering, accessibility, or test issue remains within scope.
