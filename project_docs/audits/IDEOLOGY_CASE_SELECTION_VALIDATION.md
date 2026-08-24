# Ideology representative-case selection validation

**Verdict: PASS**

The current `WEB-IDEOLOGY-CASE-SELECTION-001` release candidate selects each
bloc's representative case by proximity to the full bloc median of the current
v6 `candidate_quality_residual`. The displayed cases, labels, and explanatory
copy agree with that rule.

## Independent selection reconstruction

I loaded cluster membership from
`research/cmo_ideology/democratic_clusters/democratic_candidate_cluster_membership.csv`,
discarded its prior residual column, and joined the current value from
`data/processed/war/cmo_v6_southern_candidates.csv` by
`canonical_candidate_id`. For each Democratic bloc I:

1. calculated the median across the complete quality-scored bloc;
2. limited card eligibility to rows having both a finite v6 quality residual and
   a finite federal comparison;
3. calculated each eligible row's absolute distance from the full-bloc median;
4. selected the unique minimum-distance row.

| Bloc | Full bloc n | Full-bloc median | Eligible n | Independent representative | Residual | Distance |
|---|---:|---:|---:|---|---:|---:|
| Traditionalist-populist Democrats | 76 | +8.948270 | 65 | Galliher, 1998 HD-30 | +8.916595 | 0.031675 |
| Progressive-modern Democrats | 39 | -2.876274 | 37 | McClammy, Thad, 2002 HD-76 | -2.876274 | 0.000000 |

Both independent selections exactly match the embedded `caseStudies` payload.
The traditionalist case is now Galliher. White (1998 HD-11) has a current
quality residual of -10.467434 and is not the median-proximity selection.

The other two cards remain explicitly selected by the separate upper-decile
federal-performance criterion: Hinton Hitchem and Hall. Thus the page does not
conflate the federal-performance example with the quality-residual
representative.

## Labels and rendering

Static and rendered inspection confirmed:

- exactly two cards carry `Near bloc median quality residual`;
- the section explains that the representative is the *eligible observation*
  nearest the bloc's median candidate-quality residual;
- the implementation comments and selection code make clear that the median is
  calculated over the complete quality-scored bloc while card eligibility also
  requires a federal value;
- all four cards display quality residual, federal comparison, and presidential
  comparison as distinct metrics;
- the four rendered names are Hinton Hitchem, Galliher, Hall, and McClammy,
  Thad, in the intended bloc ordering.

Headless Chrome results:

| Requested viewport | Effective client width | Scroll width | Cards/layout | Severe console errors |
|---:|---:|---:|---|---:|
| 1280 | 1265 | 1265 | 4 cards, two columns | 0 |
| 497 | 482 | 482 | 4 cards, one column | 0 |
| 390 | 375 | 375 | 4 cards, one column | 0 |

No horizontal overflow occurred at any checked width, and all selection labels
and metric values remained visible.

## Commands run

```powershell
python -m pytest scripts/tests/test_ideology_performance_page.py -q
python scripts/validate_agent_workflow.py
```

Result: `10 passed`; workflow validation passed. I also used independent
pandas calculations against the source CSVs and Selenium/Chrome rendering at
desktop, exact 497, and exact 390 requested widths.

## Release recommendation

Approve. The representative cards now match their stated v6 quality-residual
criterion, and the eligibility limitation is disclosed accurately.
