# Southern WAR v3 retrain on refreshed Alabama context — 2026-09-11

Execution record for `SOUTHERN-V3-RETRAIN-REFRESHED-CONTEXT-20260911`
(umbrella: `coordination/CHECKLIST-EXECUTION-20260910.md`). Owner authorization
2026-09-11: retrain the approved Southern v3 run on the refreshed Alabama
context after the finding recorded in
[ALABAMA_TICKET_BASELINE_STALENESS_2026_09_11.json](ALABAMA_TICKET_BASELINE_STALENESS_2026_09_11.json).
This record documents the run; it does not approve it. Approval requires the
independent review named below and a new `SOUTHERN_V3_RELEASE_DECISION.json`.
No publication was performed.

## Why

The approved run `WAR-POST2016-V3-4AF79A70EAA8F39EBD49` computed Alabama
2018/2022 raw gaps against the same-cycle federal ticket baseline of the
2026-08-21 `historical_federal_district_baseline` build, which predates the
accepted September precinct-identity repairs (`warehouse-03`) and the
certified-canvass integration. Regenerating that baseline from the repaired
warehouse with unchanged code and byte-identical modern precinct weights moved
131/139 (2018) and 128/140 (2022) district baselines (median 0.19 / 0.05 pp,
max 13.4 / 8.8 pp) through allocated two-party totals; statewide allocated
totals are identical, so this is a redistribution across districts consistent
with the identity re-mapping.

## Chain executed (serial, each an existing builder)

| Step | Command | Result |
|---|---|---|
| Morgan adjudication | `scripts/repair_morgan_1994_fractional_cell.py --apply …` | `RUN-C0A15A7AB6A6403991BB5FE5143BACFF` (owner option A; review PASS) |
| Geographic weights | `scripts/build_canonical_geographic_weights.py` | CSV; 2010/2018/2022 identical to accepted 08-26 file |
| 1994 baseline marts | `scripts/build_1994_cmo_baseline.py` | `RUN-22C8E3AE51C34579A6BCD9A49EF8C700` |
| Federal baselines | `scripts/build_historical_federal_baselines.py` | `RUN-70A750C82BEC43D686E5F4B1FE13461C`; code fix: 1994 precinct keys read as text |
| Compat features | `scripts/build_canonical_cmo_features.py`, `scripts/rebuild_cmo_candidate_quality_v5.py` | 509 races / 1,018 candidates unchanged |
| Southern panel | `scripts/build_southern_war_panel_v1.py` | 28,307 rows; only Alabama rows changed (191 baselines, 7 legislative margins); 27,187 non-AL rows identical |
| Preparation target | `scripts/load_southern_war_preparation_warehouse.py` | `RUN-504CE4C4DF904D88A5A40D268F3FCEAB`; 4,582 outcomes, 4,280 strict, 116 slices; training frame identical except 89 AL baselines (max 8.77 pp) |
| Archive approved run | copy to `data/processed/war/post2016_southern_war_v3_archive/WAR-POST2016-V3-4AF79A70EAA8F39EBD49/` | 14 files; hashes equal the approved manifest |
| Retrain | `scripts/retrain_post2016_southern_war_v3.py` | **`WAR-POST2016-V3-A937708D4E0A5232D3F5`** |
| Tests | `test_post2016_southern_war_v3.py` (15), `test_southern_war_preparation_warehouse.py` (9) | pass |
| Sensitivity | `scripts/audit_southern_v3_context_sensitivity.py` | parity passed; median SE 0.759, stable party 0.630 (prior run: 0.759 / 0.630) |

Backups taken before each warehouse-writing step:
`pre-morgan-1994-adjudication-2026-09-10.sqlite`,
`pre-1994-federal-mart-rebuild-2026-09-10.sqlite`,
`pre-southern-preparation-refresh-2026-09-11.sqlite` (each `quick_check` ok).

## New run versus approved run

`artifacts/war/alabama_dependency_rebuild_20260910/v3_retrain_delta.json`:

- Specification unchanged: `decaying_lag`, alpha 100; lag added-value gate still
  passes (forward MAE 4.796 vs 4.805; no-lag 5.100 vs 5.110).
- Input hash differences: the warehouse file only. Code hash differences:
  `scripts/retrain_post2016_southern_war_v3.py` (the `sha256` helper now streams
  the 5.8 GB file instead of reading it into memory; no numerical code changed).
- Race deltas over 3,660 races: `raw_gap` changed for exactly the 89 Alabama
  races (max 8.77 pp; no non-Alabama change); the pooled structural fit moved
  `fitted_structural_expected_gap` for 1,786 races (non-Alabama ≤ 0.451 pp,
  Alabama ≤ 3.72 pp) and `war` accordingly (non-Alabama ≤ 0.451 pp, Alabama ≤
  5.06 pp).
- Finance sensitivity and structural-selection metrics move in the third
  decimal only (see the delta file).

## Test change

`scripts/tests/test_post2016_southern_war_v3.py::verify_report` no longer pins
the *live* scripts to the archived 8BB52074 run's code hashes; it still asserts
the archived manifest's code identity equals the documentation-only
disposition. The live pin was incidental: any legitimate code change under a
new run manifest broke it.

## Not established

Independent scientific review of the new run; the release decision; downstream
Southern historical/map rebuilds and any publication; the Alabama chain.

## Review and downstream rebuilds (2026-09-11)

Independent review
[SOUTHERN_V3_INDEPENDENT_REVIEW_2026_09_11.md](SOUTHERN_V3_INDEPENDENT_REVIEW_2026_09_11.md)
(SHA256 `5e4459f981e6c2565c1d7e1e4212f40c1cbe0c35422d94d0c297b92ead384b14`):
**APPROVED FOR DESCRIPTIVE HISTORICAL USE**, superseding
`WAR-POST2016-V3-4AF79A70EAA8F39EBD49` for the Southern historical WAR route. The
reviewer reproduced all ten checks (24/24 declared files, archive 13/13, the
3,660-row deltas, training-frame provenance against the pre-refresh backup,
baseline correctness including equal statewide allocated totals, specification
argmin, sensitivity parity 6.5e-14, code/test diffs, regenerated docs).
Findings acted on: six `war_party` label changes recorded in
`v3_retrain_delta.json` (AL 2018 HD47 +3.75 → −0.00 is the only non-trivial
one; the other five are near-zero crossings); the release decision was
re-bound without a live `accepted_input_revisions` block (the superseded run's
block and decision record are preserved under `supersedes`, and at
`SOUTHERN_V3_RELEASE_DECISION.4AF79A70.superseded.json`).

| Product | Run | Result |
|---|---|---|
| `alabama_war_v1` | `AL-WAR-V1-495AE74F46366F17B414` | 97 races from the approved run; gate passed |
| `alabama_historical_war_v1` | `AL-HIST-WAR-V1-E1C4794EB7A3EF8149E4` | 509 / 1,018 / 412 backcast / 97 modern; lag-context-missing 21 → 18; identities exact; raw gaps agree with `alabama_war_v1` 97/97 |
| Historical story page | `artifacts/site/alabama-legislative-cmo.html`, `cmo-methodology.html` | rendered with the new `--artifact-only` switch; `docs/cmo.html` untouched |
| Ideology page | `artifacts/site/ideology-performance.html` | gate passed; local candidate only |
| Forecast bundle | build `828f6df6a19a5e7a39bf` | `war_training_warehouse_run_id = RUN-504CE4C4…`; 48 modeled seats × 3 scenarios; selected forward MAE 7.651 vs baseline 7.072 (owner-selected structural spec retained, advisory comparison still unfavorable) |
| Forecast page | `artifacts/site/alabama-2026-legislative-forecast.html`, `forecast-methodology.html` | `--artifact-only`; `docs/index.html` untouched |
| Southern historical | `WAR-SOUTH-HIST-V1-E9D974108A87C957FE52` | 4,280 scored, 620 backcast, 302 excluded, 116 slices (2 empty), status validated; 50 Southern tests pass |
| Southern map | not run | `build_southern_war_map.py` writes `docs/southern-war.html`; awaits publication authority |

Historical Alabama WAR versus the prior export (`git HEAD`): WAR changed for
all 509 races (backcast refit), median 0.42 pp; baseline-driven outliers 2014
HD52/HD56 (+33 pp; 2014 federal contested coverage ≈ 0.55, so those baselines
hinge on few contested US-House seats) and 2002 HD26 (+13.5 pp; Marshall
County collision, `warehouse-05`). These must appear in the Alabama validation
card (`alabama-11`) before publication.

Tests reading published `docs/` pages (`test_grimsley_2018_is_exact_published_race_residual`,
`test_methodology_has_no_legacy_forecast_claims`) fail until republication;
they compare the stale public pages with the new data and were not weakened.
