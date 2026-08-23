# Forecast explorer validation

## Verdict

**PASS.** The chamber paths, race overview, district profiles, component comparison, and candidate CMO timelines reconcile to the current validated inputs without changing forecast arithmetic. Desktop, mobile, and keyboard gates pass after the scenario-tab focus remediation.

## Numerical reconciliation

### Forecast and component arithmetic

- Rebuilt the dashboard payload with the production `build_payload()` entry point and compared all 48 modeled races under all three scenarios to `post2016_headline_v1_2026_scenarios.csv`.
- Scenario margins and probabilities match the promoted source within the six-decimal public-display rounding tolerance (maximum difference below `5e-7`).
- Every five-step component chain closes exactly: the final running margin equals the displayed scenario margin for every chamber, district, and scenario.
- The explorer therefore changes presentation only; the promoted model's margins, probabilities, intervals, fixed-seat treatment, and scenario definitions are unchanged.

### Chamber paths and control probabilities

All six chamber/scenario distributions sum to one within floating-point tolerance. Independently reproducing fixed seats, majority thresholds, probability-ranked modeled routes, and distribution-tail control probabilities produced the displayed results:

- House: 20 fixed Democratic and 52 fixed Republican seats; 53 required; Democratic route needs all 33 modeled wins and Republican route needs one. The threshold race is HD-16 under each scenario.
- Senate: 6 fixed Democratic and 14 fixed Republican seats; 18 required; Democratic route needs 12 modeled wins and Republican route needs four. The threshold race is SD-6 under each scenario.
- Democratic control probability is below 0.1% and Republican control probability displays as 100.0% in all six views, consistent with the underlying distributions and the page's documented rounding.
- Race-watch counts are 33 House and 15 Senate contested forecasts. The watch lists and threshold buttons update when chamber or scenario changes.

## Source joins and missingness

### District profiles

All 140 district profiles were independently joined back to their current sources by `(chamber, district)`:

- 2022 legislative results exactly reproduce Democratic/Republican vote sums, two-party margins, and available candidate display names from `canonical_cmo_candidates.csv`.
- Uncontested/one-party 2022 races retain unavailable two-party margins as null rather than manufacturing a value; 107 such profile margins remain missing.
- Nonwhite, college-graduate, and white-college shares exactly match `2026_sld_demographics.csv`.
- Black, white non-Hispanic, and total CVAP values exactly match `rdh_2024_sld_cvap.csv`.
- Regional summaries exactly reproduce the current 2026 region-feature source and its five-percent display threshold.
- All demographic source cells used here are present; the loader's null-preserving conversion was also checked directly rather than equating missing values with zero.

The public source ledger links to existing copied files for district demographics, regional geography, canonical 2022 context, and CMO history. Every displayed provenance download target exists under `docs/data/`.

### Candidate timelines

- Candidate histories are sourced only from `cmo_v6_southern_candidates.csv`, restricted to cycles through 2022.
- The current roster contains 37 candidates with timelines, totaling 53 observations. Every observation matches the source cycle, chamber, district, party, direct-CMO score, incumbency flag, and winner flag.
- Normalized name/party groups spanning multiple `candidate_effect_id` values are now suppressed. No ambiguous group powers a public timeline.
- Candidate Atlas copy and navigation remain absent from the generated public HTML.

## Browser and accessibility validation

Installed Chrome was exercised at 1280, exact 497, and exact 390 CSS-pixel widths.

- All three scenarios and both chambers rendered and updated the majority paths, control probabilities, tipping seats, and watch lists.
- A modeled district with history (HD-4) rendered one profile, five component rows, three scenario comparison cards, and its CMO timeline at every width.
- A two-observation history (SD-1) rendered both career rows correctly.
- Native path/watch buttons and table rows open district details; Enter on a focused table row updates the selected district.
- ArrowRight on the Headline tab selects and focuses the newly rendered Democratic scenario tab at every width. `aria-selected` and `document.activeElement` agree after rerender.
- Horizontal overflow is zero, including with a modeled detail/timeline open.
- Chrome logs contain zero severe console/runtime errors.

## Commands and tests

```powershell
python -m pytest scripts/tests/test_forecast_dashboard.py scripts/tests/test_published_site_consistency.py scripts/tests/test_site_brand.py scripts/tests/test_cmo_story_historical_cycles.py -q
python scripts/validate_agent_workflow.py
```

Final result: `37 passed`; agent workflow validation passed.

Additional independent Python checks rebuilt and reconciled the payload against the forecast, canonical election, demographic, CVAP, regional, and CMO-v6 sources. Selenium/Chrome-CDP checks exercised all chamber/scenario combinations and exact responsive widths.

## Release decision

Approved for publication. No blocking findings remain.
