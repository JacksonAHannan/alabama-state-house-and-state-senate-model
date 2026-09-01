# Alabama WAR forecast validation

Build `4a24f61e28a3d5987062` generated `2026-09-01T02:45:13.849126+00:00`.

- Alabama retrospective coverage: 97 races (2018 and 2022).
- Forward test: 33 2022 races after training on 2018 only.
- Generic structural candidate MAE: 9.490; generic-ballot baseline MAE: 7.073.
- Structural promotion gate: failed; selected specification: `generic_ballot_baseline`.
- Prospective coverage: 48 D-R races in each scenario.
- Candidate WAR is zero, candidate history is false, finance is false, and the forecast identity reconciles within floating-point tolerance.
- Limitation: Alabama supplies only one direct forward cycle, so calibration and structural estimates remain sample-limited.

## Release validation

- `python scripts/validate_agent_workflow.py`: passed.
- Focused WAR, forecast, dashboard, publication, and branding suite: 42 passed.
- Full repository suite: 647 passed and one unrelated failure in `test_canonical_historical_finance.py`; the fixture expects 352 complete historical-finance races while the current canonical input produces 353.
- Public site rebuilt through `scripts/build_blue_oxblood_site.py`; the shared navigation labels the route `Alabama WAR` on every themed public page.
