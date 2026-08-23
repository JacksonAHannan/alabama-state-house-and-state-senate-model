# Published merged Democratic transition validation

Date: 2026-08-22
**Final verdict: PASS.**

The themed merged ideology/caucus publication satisfies the final public release gate. The prior navigation omission on the forecast and forecast-methodology pages is corrected.

## Commands

```powershell
python -m pytest scripts/tests/test_published_site_consistency.py scripts/tests/test_ideology_performance_page.py scripts/tests/test_caucus_analysis_page.py scripts/tests/test_site_brand.py -q
# 21 passed

python scripts/validate_agent_workflow.py
# Agent workflow validation passed.
```

The implementation owner also reports the complete repository suite passing 476 tests; this narrow independent rerun reproduced the contracted 21-test publication gate.

## Navigation

Each public site navigation contains exactly one link labeled `Ideology & caucuses` targeting `ideology-performance.html`, and zero links to standalone `caucuses.html`:

- `docs/index.html`
- `docs/methodology.html`
- `docs/cmo.html`
- `docs/cmo-methodology.html`
- `docs/ideology-performance.html`
- `docs/legislators.html`

The compatibility page `docs/caucuses.html` correctly redirects to `ideology-performance.html#candidate-explorer` through both refresh and JavaScript. Chrome reaches the target fragment without a severe console error.

## Published payload and browser results

The public payload contains 274 current cluster members, including 115 Democrats. The merged page renders 115 Democratic candidate rows and 115 constellation points at every tested width.

| Viewport | Rows | Points | Document overflow | Severe console errors |
|---:|---:|---:|---:|---:|
| Desktop | 115 | 115 | 0px | 0 |
| Exact 497px | 115 | 115 | 0px | 0 |
| Exact 390px | 115 | 115 | 0px | 0 |

Published consistency, merged-page behavior, shared-theme transformation, navigation, redirect, responsive layout, and browser runtime all pass. No publication blocker remains.
