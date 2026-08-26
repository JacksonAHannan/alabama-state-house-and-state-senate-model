# WEB WAR repair validation

## Verdict

**APPROVE.** The sole blocker from `VALIDATE-WEB-WAR-PAGE-019` is resolved. The repaired forecast source and all three generated forecast artifacts use **Historical WAR model** and contain no **Historical CMO model** label. The previously approved HD-32 arithmetic and WAR/CMO separation remain intact.

## Exact checks

### Source and generated wording

An exact string-count audit returned `WAR=1` and `CMO=0` for each of:

- `scripts/build_2026_forecast_dashboard.py`
- `docs/index.html`
- `artifacts/site/alabama-2026-legislative-forecast.html`
- `artifacts/blue_oxblood_site/index.html`

A scan of every top-level `docs/*.html` file found no occurrence of `Historical CMO model`. The forecast page exposes the repaired link to `cmo.html` as `HISTORICAL WAR MODEL` after CSS text transformation.

### Workflow and focused tests

```powershell
python scripts/validate_agent_workflow.py
python -m pytest scripts/tests/test_cmo_story_historical_cycles.py scripts/tests/test_site_brand.py scripts/tests/test_published_site_consistency.py -q
```

Results:

- Agent workflow validation passed.
- `19 passed in 11.07s`.

### Browser smoke

Headless Chrome 151 loaded the generated pages directly from `docs/`.

- Forecast at 1440px and 390px: repaired `HISTORICAL WAR MODEL` link visible, zero horizontal overflow, zero severe console entries.
- Historical page: title remains `Alabama Legislative Wins Above Replacement (WAR)`; no `Candidate Quality Index` text; zero horizontal overflow and zero severe console entries.
- Barbara Bigsby Boyd, 2010 HD-32: keyboard selection worked; default headline remained `+4.5 CANDIDATE WAR`; switching to CMO displayed `+30.3`; switching back restored `+4.5 CANDIDATE WAR`.
- At 390px, the `2008 President` context displayed Barack Obama, John McCain, and `D+24.1`, with zero overflow and zero severe console entries.

These observations preserve the prior independent reconciliation of Obama `D+24.052976`, Boyd presidential overperformance `+18.694287`, Direct CMO `+30.263799`, and WAR approximately `+4.5`. The repair changed nomenclature only and did not collapse the distinct observed CMO measure into WAR.

## Release recommendation

Approve the repaired candidate for publication. No blocking or non-blocking regression was found in the contracted scope.
