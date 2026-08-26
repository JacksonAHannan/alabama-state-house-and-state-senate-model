# WAR-first ideology headline validation

## Verdict

**PASS.** The current local `WEB-IDEOLOGY-WAR-HEADLINE-011` release candidate, including the completed `WEB-IDEOLOGY-WAR-A11Y-REPAIR-013` remediation, is approved for publication. The page leads with adjusted WAR comparisons, keeps raw ticket comparisons secondary, retains the stable internal schema, visibly credits Split Ticket, and passes the focused, JavaScript, desktop, and mobile gates.

Validated independently on 2026-08-26. Artifact SHA-256:
`74D66315684355098892DCB142999CA95F7E526B160460179EB9C90248F9C16E`.

## Build and tests

To honor the read-only artifact scope, I rebuilt the page in memory through the maintained `scripts.build_democratic_transition_page` entry point and compared the returned bytes with the staged artifact rather than rewriting it:

```powershell
python -c "from pathlib import Path; from scripts.build_democratic_transition_page import build; assert build() == Path('artifacts/site/ideology-performance.html').read_text(encoding='utf-8')"
python -m pytest scripts/tests/test_ideology_performance_page.py scripts/tests/test_caucus_analysis_page.py scripts/tests/test_cmo_story_historical_cycles.py scripts/tests/test_site_brand.py -q
python scripts/validate_agent_workflow.py
```

Results:

- In-memory rebuild exactly matched the 559,125-byte staged artifact.
- Focused suite: **24 passed**.
- Workflow validation: passed.
- Extracted inline JavaScript passed `node --check -`.

No builder, test, input, model output, staged artifact, or `docs/` file was modified during validation.

## Headline and terminology

- DOM section order is `performance`, `overview`, `transition`, `positions`, `distribution`, `time`, `issues`, `cases`, `candidate-explorer`, `continuous`, then `methods`.
- The first quantitative section is `WAR relative to progressive-modern candidates`.
- The two headline cards are:
  - Traditionalist-populist WAR: **+7.0**, approximate 95% interval **+2.2 to +11.8**, 42 observations and 5 common cycle/chamber contexts.
  - Bridge-coalition WAR: **+6.8**, approximate 95% interval **+2.8 to +10.7**, 93 observations and 10 common cycle/chamber contexts.
- The subsequent group summary labels its group means unadjusted and lists WAR before the separate raw federal and presidential comparisons.
- The following raw-ticket section is explicitly labeled `Adjusted raw ticket comparisons`; it is not presented as WAR.
- No public-facing `Candidate Quality Index` or `CQI` label remains in the staged HTML.
- `candidate_quality_index` remains the internal field used by the payload and JavaScript, as required for compatibility.
- Neither `candidate_cmo` nor `candidate_quality_residual` is carried in the public member records.

## Independent numerical cross-check

I independently merged the current cluster membership to `cmo_v5_candidates.csv` one-to-one by `canonical_candidate_id`, then reconstructed all six pairwise cycle/chamber fixed-effect contrasts with person-clustered sandwich uncertainty. The results match the staged payload to floating-point precision:

| Measure | Focal group | Difference vs progressive | Approx. 95% interval | n | People | Contexts |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| WAR | Traditionalist-populist | +6.981121 | +2.206395 to +11.755847 | 42 | 42 | 5 |
| WAR | Bridge coalition | +6.771903 | +2.811913 to +10.731894 | 93 | 91 | 10 |
| Raw vs federal | Traditionalist-populist | +8.010509 | -4.350565 to +20.371582 | 30 | 30 | 3 |
| Raw vs federal | Bridge coalition | +16.479478 | +5.554973 to +27.403984 | 85 | 83 | 9 |
| Raw vs president | Traditionalist-populist | +16.702808 | -3.769736 to +37.175352 | 36 | 36 | 5 |
| Raw vs president | Bridge coalition | +15.197475 | +2.301888 to +28.093062 | 87 | 85 | 10 |

The page does not overstate the two traditionalist raw-ticket intervals that cross zero.

## Attribution and interpretation

- The methods section visibly defines `WAR means Wins Above Replacement`.
- It credits and links `Split Ticket's WAR methodology` at `https://split-ticket.org/2025/08/15/deconstructing-war/`.
- The copy explains that this implementation is measured in margin points relative to replacement expectation rather than literal seats or wins.
- It states that election performance was attached after group construction and that adjusted comparisons use cycle/chamber fixed effects and person-clustered uncertainty.
- The limitations copy describes the analysis as descriptive and does not claim issue positions caused electoral performance.

## Schema compatibility

- `schemaVersion` remains **2**.
- Payload contains **311** member rows, all with finite `candidate_quality_index`.
- The three group identifiers are unchanged: traditionalist-populist, bridge-coalition, and progressive-modern Democrats.
- Six contrast rows retain the established `cycle_chamber_fixed_effects_person_clustered_se` method identifier.
- Existing CMO-story, caucus-analysis, and site-brand compatibility tests all pass.

## Browser and accessibility validation

Chrome 151 loaded the staged artifact at exact 1440px and 390px CSS viewport widths.

- `documentElement.scrollWidth == clientWidth` at both widths: 1440/1440 and 390/390.
- No severe console error occurred.
- Both WAR cards remain fully contained and readable. At 390px they stack into 364px-wide cards between x=13 and x=377.
- All 131 candidate-distribution buttons have accessible names.
- After the accessibility remediation, all **87/87** issue-chart buttons expose candidate, race, group, issue position, and selected performance measure; example: `Starkey, 1998 HOUSE-1, Bridge coalition, Gun access position +0.9, WAR -7.4`.
- All **131/131** similarity-map points expose candidate, race, group, and evidence-coverage names; example: `Black, 1998 HOUSE-3, Traditionalist-populist, 33 percent issue-dimension coverage`.
- All 131 keyboard-focusable candidate table rows have visible row text.
- `Enter` on a similarity-map point and on a candidate row updates the candidate detail panel.
- Outcome, era, issue, group, search, and trend controls render and update without application errors.
- Visual inspection found coherent blue/oxblood styling and no headline clipping at either tested width.

The initial candidate had unnamed issue-chart and constellation controls. That was a release blocker; it is resolved in the exact artifact identified above.

## Release recommendation

Proceed with `WEB-IDEOLOGY-WAR-PUBLISH-012`. No blocking numerical, semantic, attribution, compatibility, JavaScript, responsive, or accessibility defect remains in the validated local artifact.
