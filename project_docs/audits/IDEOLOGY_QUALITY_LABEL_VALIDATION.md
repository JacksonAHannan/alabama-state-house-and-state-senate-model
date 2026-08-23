# Ideology candidate-quality label validation

**Verdict: PASS**

Validated the current `WEB-IDEOLOGY-QUALITY-LABEL-001` release candidate against
`data/processed/war/cmo_v6_southern_candidates.csv`. The combined ideology and
caucus page consistently uses the v6 `candidate_quality_residual` as its third
performance measure and does not present that measure as CMO.

## Independent numerical reconciliation

I loaded the 274 public cluster members and outer-joined them to the v6 candidate
file on `canonical_candidate_id`.

- Public cluster IDs: 274 rows and 274 unique IDs.
- Exact v6 matches: 274/274; no public left-only row.
- The v6 file has 744 additional candidates outside this page's cluster sample.
- Maximum absolute page-versus-v6 value difference: `4.97e-11`, attributable to
  JSON decimal serialization.
- No `candidate_cmo` field survives in the public member payload.

For the 115 Democratic member rows, independent aggregation of the v6 values
produced:

| Bloc | n | Mean candidate-quality residual | SD |
|---|---:|---:|---:|
| Traditionalist-populist Democrats | 76 | +8.295638 | 20.165471 |
| Progressive-modern Democrats | 39 | -4.098104 | 14.982520 |

The independently calculated traditionalist-minus-progressive difference is
`+12.393743` points. The embedded headline payload reports the same counts,
means, standard errors, and a `+12.393743` difference (within serialization
precision).

The embedded payload in both `artifacts/site/ideology-performance.html` and
`docs/ideology-performance.html` also reconciles 274/274 to v6 with the same
maximum error. Two fresh in-memory builds were identical; the checked artifact
is text-identical to the current builder output (its byte-level difference is
only Windows newline translation when read/written through the repository).

## Label and behavior audit

Static inspection found:

- all three performance selectors label the field `Candidate quality residual`;
- the headline, candidate distribution, issue plot/tooltips, case cards,
  candidate detail, and table all read `candidate_quality_residual`;
- zero occurrences of the stale `candidate_cmo` identifier or selector;
- zero visible `Candidate CMO`, `CMO residual`, or `CMO score` phrases;
- methodology correctly defines the measure as Direct CMO minus the externally
  estimated Southern structural expectation and explicitly distinguishes it
  from Direct CMO and the career-pooled quality index;
- legitimate CMO navigation, CMO-methodology navigation, footer link, and the
  methodological reference to Direct CMO remain intact.

In headless Chrome I selected `candidate_quality_residual` in the headline,
distribution, and issue controls and selected a candidate from the table. The
headline rendered `+8.3`, `-4.1`, and `+12.4`; the candidate detail displayed the
same quality residual shown in its table row and the `CANDIDATE QUALITY
RESIDUAL` label. Controls and candidate selection worked without severe console
errors.

Viewport results (CSS-pixel device emulation):

| Requested width | Effective client width | Document scroll width | Overflow |
|---:|---:|---:|---:|
| 1280 | 1265 | 1265 | 0 |
| 497 | 482 | 482 | 0 |
| 390 | 375 | 375 | 0 |

## Commands run

```powershell
python -m pytest scripts/tests/test_ideology_performance_page.py -q
python scripts/validate_agent_workflow.py
```

Result: `9 passed`; workflow validation passed.

I also ran independent Python/pandas reconciliation scripts against the builder
payload, both embedded HTML payloads, and the v6 CSV, plus Selenium/Chrome checks
at 1280, exact 497, and exact 390 requested widths.

## Release recommendation

Approve this release candidate. Direct CMO, raw candidate-quality residual,
career-pooled candidate quality, and raw federal/presidential comparisons remain
clearly separated in the data contract and visible presentation.
