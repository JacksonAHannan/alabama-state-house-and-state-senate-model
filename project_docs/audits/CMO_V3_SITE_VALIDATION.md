# CMO v3 site propagation validation

- Task: `VALIDATE-CMO-V3-SITE-001`
- Reviewer: `/root/blue_oxblood_validation`
- Candidate: final remediated `IDEO-CMO-V3-001` and `WEB-CMO-V3-001`
- Decision: **PASS**

CMO v3 is consistently propagated through the ideology analysis, CMO
dashboard, methodology, public downloads, and visible explanatory copy.

## Final visible-copy revalidation

The three prior publication blockers are resolved in the freshly rebuilt
pages:

- `docs/ideology-performance.html #measure .prose` now defines CMO as the
  observed legislative margin minus a source-aware same-district ticket margin
  and explicitly says no candidate-variable regression changes the score.
- The adjacent `#measure .formula` now subtracts `Source-aware ticket margin`,
  described as same-district state and specified federal context.
- `#absoluteOutcome option[value="candidate_cmo"]` now reads
  `Direct ticket CMO`.
- `docs/cmo.html .explorer-top .note` now says the relative map uses
  `direct-CMO percentiles`.

The selected-race wiki-box also uses `actual versus ticket baseline`, `Ticket
baseline`, and `Ticket baseline margin`. No `model baseline` or `Expected
baseline` label remains in the rendered page.

A rendered-page scan found no `Context CMO`, `context-CMO`, `ideology-blind
expectation`, or candidate-variable-free regularized-expectation claim in the
CMO or ideology pages.

## Numerical reconciliation

- All 1,018 ideology-analysis `candidate_cmo` values reconcile by stable
  `canonical_candidate_id` to v3 `candidate_headline_cmo`; maximum CSV parse
  difference is `3.55e-15`.
- All 1,018 embedded CMO dashboard candidate values reconcile by unique
  cycle/chamber/district/party to v3 rounded to the displayed two decimals.
- All 407 public Shor-point and 4,290 public issue-evidence observations were
  previously reconciled by stable ID, for 4,697 public ideology observations.
- Morrow, 1998 House District 18 Democratic candidate, remains
  `+0.5103129673` in v3 and `+0.51` in the dashboard.

## Methodology and downloads

The rendered methodology defines direct CMO correctly, labels regression
context as pathology-audit-only, and links only v3 artifacts. The published
candidate, race, baseline-tournament, pathology-audit, and provenance CSVs were
previously verified byte-identical to their processed sources. The manifest
contains input, code, configuration, output, and deterministic run records.

Non-blocking maintenance only: the CMO builder still contains dead legacy v2
template strings that are replaced before rendering. They do not appear in the
public pages, but removing them would reduce future regression risk.

## Tests

```text
34 passed in 4.06s
Agent workflow validation passed.
```

Commands:

```powershell
python -m pytest scripts/tests/test_cmo_direct_estimand.py tests/test_absolute_ideology_rebuild.py scripts/tests/test_cmo_story_historical_cycles.py scripts/tests/test_ideology_performance_page.py scripts/tests/test_published_site_consistency.py scripts/tests/test_site_brand.py -q
python scripts/validate_agent_workflow.py
```

## Release decision

**PASS.** No obsolete context-CMO headline claim or old numerical payload
remains in the staged publication. The v3 CMO and ideology pages are cleared for
publication.
