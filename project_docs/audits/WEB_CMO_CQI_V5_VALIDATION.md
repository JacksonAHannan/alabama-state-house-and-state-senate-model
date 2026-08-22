# CMO/CQI v5 web publication validation

**Task:** `VALIDATE-WEB-CMO-CQI-V5-001`
**Validated:** 2026-08-21
**Verdict:** **PASS**

The public CMO explorer, standalone artifact, methodology page, and downloadable
exports agree with the validated v5 model. Direct CMO is the default
descriptive measure; Candidate Quality is separate, uncertainty-labeled, and
mapped as the Democratic-minus-Republican race differential.

## Publication and payload fidelity

All eight `docs/data/cmo_v5_*.csv` files byte-match their approved
`data/processed/war` counterparts, including the current provenance manifest.
The public and standalone embedded payloads are identical and parse as 16
cycle/chamber sections containing 1,018 candidate rows.

I reconciled every embedded candidate by cycle, chamber, district, and party.
The following payload fields match v5 after the builder's documented two-decimal
rounding:

- direct CMO;
- CQI, lower bound, and upper bound;
- intrinsic sensitivity;
- pre-election estimate and prior appearances;
- full-panel appearances and reliability; and
- evidence status.

Every default map value matches race `direct_cmo`. Every quality-map value now
matches race `candidate_quality_differential = q_D - q_R`; it does not use the
Democratic candidate effect alone. There were zero discrepancies across all
509 races.

## Explorer behavior

The browser initially activates CMO and labels it `CMO, observed margin
points`. The other three controls remain functional:

- Candidate Quality differential, D minus R;
- raw overperformance versus governor; and
- raw overperformance versus the previous presidential margin.

Switching modes rerenders the map and updates accessible district labels and
the subtitle. Candidate ranking defaults to direct CMO. The table separately
shows CQI/status, its interval, state-ticket comparison, federal-ticket
comparison, prior-presidential comparison, selected baseline margin, actual
margin, and votes.

Selected-candidate detail shows the required CQI estimate, interval, status,
reliability, appearances, intrinsic sensitivity, and strictly prior-cycle
pre-election estimate. It also retains the race wikibox, selected ticket and
office context, observed alternative comparisons, source quality, and resolved
history.

## Mike Curtis regression

Both candidate rows and the rendered detail agree with v5:

| Race | CMO | CQI | Interval | Status | Pre-election |
|---|---:|---:|---:|---|---:|
| 2010 House 2 | +19.53 | +3.63 | -12.46 to +19.71 | uncertain | 0.00, no prior race |
| 2014 Senate 1 | +10.53 | +3.63 | -12.46 to +19.71 | uncertain | +5.76, one prior appearance |

The 2014 detail additionally reports 67% reliability and two full-panel
appearances. The public explanation gives Curtis credit for observed CMO while
keeping CQI separate and uncertain.

## Methodology and legacy audit

The methodology page correctly states:

- direct candidate-oriented ticket arithmetic and D/R zero-sum orientation;
- 509 races and 1,018 candidate-cycle rows from 1994–2022;
- same-cycle federal selection with documented state-ticket fallback;
- cycle/chamber/source replacement centering;
- predetermined structural features without current-federal lag reuse;
- forward-cycle ridge-penalty selection;
- retrospective full-panel CQI versus prior-cycle-only pre-election CQI;
- retained-incumbency total CQI and the three-point intrinsic sensitivity;
- mandatory singleton `pair_differential_only` uncertainty; and
- hashed operative inputs and explicit limitations.

Visible content and links in the explorer, methodology, and standalone artifact
contain no v4 download link, `cmo_v4` label, WAR-style residual claim,
structural-expectation headline, campaign-effort decomposition, or career-pooled
headline artifact. All download links point to v5 products.

## Browser, readability, and navigation

I inspected `cmo.html` and `cmo-methodology.html` in headless Microsoft Edge at
desktop and an exact 497-pixel effective client width. Both pages had
`scrollWidth == clientWidth`, so there was no horizontal overflow. The CMO page
used dark text on white/light surfaces and white navigation text on the dark
blue masthead; the shared light-blue/oxblood design, table hierarchy, controls,
and selected detail remained readable at both widths.

The generated HTML parsed, the embedded JSON parsed, and page scripts
initialized all controls and maps without an application error. The sole
console entry was the unrelated missing `favicon.ico` network 404. All 20
unique internal links checked across the two pages returned HTTP 200, and the
current-page navigation state was correct.

## Commands run

```text
python -m pytest scripts/tests/test_cmo_story_historical_cycles.py scripts/tests/test_published_site_consistency.py scripts/tests/test_site_brand.py -q
python -m pytest scripts/tests/test_cmo_candidate_quality_v5.py scripts/tests/test_cmo_story_historical_cycles.py scripts/tests/test_published_site_consistency.py scripts/tests/test_site_brand.py -q
python -m http.server 8765 --directory docs
python scripts/validate_agent_workflow.py
```

Results:

- focused site suite: **13 passed**;
- combined model/publication suite: **20 passed**;
- workflow validation: passed;
- byte, payload, methodology, browser, responsive, and link audits: passed.

## Release decision

**PASS.** The CMO/CQI v5 web release satisfies the publication contract. No
blocking or non-blocking finding remains.
