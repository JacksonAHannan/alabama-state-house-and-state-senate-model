# Blue/Oxblood release validation

- Task: `VALIDATE-BLUE-OXBLOOD-001`
- Reviewer: `/root/blue_oxblood_validation` (`validation_release`)
- Candidate: final remediated `WEB-LIVE-BRAND-001`, 2026-08-21
- Final decision: **PASS**

The independent release gate passes. The Blue/Oxblood site rebuild is
deterministic, the full test suite passes, all six pages fit the exact 497 px
effective mobile client width without document-level overflow, and the real
forecast and CMO maps and controls function without application console errors.

## Remediation verification

- Vote Smart copy, payload, and test consistently report five time-valid
  profiles.
- The CMO mobile status grid is contained.
- `.validation-grid > * { min-width:0 }` contains the CMO validation tables in
  their local horizontal scrollers.
- The constrained mobile era grid and `.era-row > * { min-width:0 }` prevent
  ideology-era values from expanding the document.

At the exact effective mobile client width requested for revalidation:

| Page | `scrollWidth` | `clientWidth` | Overflow |
|---|---:|---:|---:|
| `index.html` | 497 px | 497 px | 0 px |
| `methodology.html` | 497 px | 497 px | 0 px |
| `cmo.html` | 497 px | 497 px | 0 px |
| `cmo-methodology.html` | 497 px | 497 px | 0 px |
| `ideology-performance.html` | 497 px | 497 px | 0 px |
| `legislators.html` | 497 px | 497 px | 0 px |

All six pages also had zero document-level overflow at the 1403 px desktop
client width.

## Rebuild and automated validation

- Workflow validation: passed.
- Complete Blue/Oxblood build: passed.
- Rebuild reproducibility: all six page hashes were unchanged by a subsequent
  complete rebuild.
- Focused/relevant suite: **36 passed** in 9.45 seconds.
- Full suite: **359 passed**, 11 non-blocking warnings, in 91.11 seconds.
- Every JavaScript block on all six pages compiled with Node.
- No Google Fonts or other remote display-font references remain.
- Branding transformation preservation tests passed; embedded scripts and model
  payloads were not modified by the theme transformation.

Final page SHA-256 values:

| Page | SHA-256 |
|---|---|
| `index.html` | `99D1F23E2903E1F9794C82A66C240F3769F8317096ABFE5B537D6B8547520409` |
| `methodology.html` | `A4B49DB63DBE98046A4DA93EF8D8184C4CE2A085DEAD3339B40B9FE3106D94D8` |
| `cmo.html` | `74F192312CEAF72BC1333591058F4EDE47060FA36DCE31EE48B2F2E39386CFA9` |
| `cmo-methodology.html` | `7F4D533D7698363D57AB60B65A65C2341A55ECED561EA9C86BE527CA38A76E40` |
| `ideology-performance.html` | `C8AC9870A3F9F944D9C9D3111617EE5A7B47A41E3488053C26E6F0B3E6663717` |
| `legislators.html` | `D55111E97A62B2D12EDF7E5D8F8AAAA5696A97280694CFFCE83928124A9B552F` |

## Browser and functional validation

Selenium used installed headless Chrome against a local HTTP server at requested
window sizes 1440×1000 and 430×900. Chrome's effective content widths were 1403
and 497 px.

- All six pages loaded with the Blue/Oxblood theme and embedded portrait.
- No application-level severe browser-console messages were recorded; missing
  favicon noise was excluded.
- Every discovered internal HTML destination returned HTTP 200.
- Forecast Leaflet map rendered 105 real district paths.
- Forecast House/Senate switch, district finder, district detail, rating mode,
  and close/reset behavior passed.
- CMO SVG rendered 105 real district paths and all 16 cycle/chamber controls.
- CMO cycle/chamber switching, absolute mode, and district detail passed.
- No placeholder map language or placeholder geography was found.

## Exact commands

```powershell
python scripts/validate_agent_workflow.py

python scripts/build_blue_oxblood_site.py

python -m pytest scripts/tests/test_site_brand.py scripts/tests/test_forecast_dashboard.py scripts/tests/test_cmo_story_historical_cycles.py scripts/tests/test_ideology_performance_page.py scripts/tests/test_legislator_ideology_page.py scripts/tests/test_published_site_consistency.py -q

python -m pytest -q

node -e "const fs=require('fs');const h=fs.readFileSync(process.argv[1],'utf8');for(const m of h.matchAll(/<script(?:\\s[^>]*)?>([\\s\\S]*?)<\\/script>/gi))new Function(m[1]);" <PAGE>

python -m http.server 8765 --directory docs
```

## Release decision

**PASS. The final Blue/Oxblood candidate is approved for commit and publication.**
No model, warehouse, payload, or data change is required.

## Reproducibility addendum

After approval, the wrapper was improved to invoke
`build_ideology_thesis_page.py` directly before copying and theming its artifact.
Independent narrow verification ran the complete wrapper twice. Both runs
produced the same six hashes listed above, which also match the pre-change
approved output. A fresh Selenium audit again measured `scrollWidth=497` and
`clientWidth=497` for every public page at the exact effective mobile width.
The direct ideology build therefore introduces no output drift or responsive
regression. **The PASS decision stands.**
