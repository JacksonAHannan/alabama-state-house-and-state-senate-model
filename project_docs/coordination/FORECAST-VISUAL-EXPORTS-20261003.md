# Task contract: FORECAST-VISUAL-EXPORTS-20261003 forecast exports for the redesigned graphics

- Accountable role: `forecast_model`
- Owner: `/root`
- Status: `review`
- Objective: Add summary exports the redesigned forecast page needs, without changing any existing forecast value: (1) a joint distribution of the simulated statewide environment shift and Democratic modeled seats per chamber; (2) a polling-replay series that recomputes the headline seat distribution with the existing polling-average rule applied as of earlier dates, holding candidates and every other input at the current run; (3) an append-only run ledger of headline toplines.
- Product/layer and checklist IDs: 2026 forecast analytical exports; `roadmap-06`.
- Dependencies: current forecast inputs as they stand in the working tree; unblocks the environment-versus-seats chart and the forecast-over-time chart in `WEB-VISUAL-REDESIGN-20261003`.
- Non-goals: no change to predictions, probabilities, intervals, seat distributions, seed, draws, model specification, polling rule or inputs. The replay is a sensitivity series, not an archived forecast history, and must be labelled that way. No source refresh.
- Upstream snapshot: working tree on 2026-10-03: forecast build `08feb2c9669842846d3f` generated 2026-09-17 (uncommitted rerun reflecting the in-progress candidate-identity work), polling as of 2026-09-08.
- Read scope: forecast inputs declared in `data/processed/forecast_calibration/alabama_war_forecast_v1_manifest.json`; polling catalog and grade inputs read by `scripts/build_silver_bplus_polling_environment.py`.
- Write scope: `scripts/run_alabama_war_generic_forecast.py`; `scripts/build_forecast_polling_replay.py`; `scripts/build_silver_bplus_polling_environment.py` (expose the existing average rule as a function; outputs byte-identical); `scripts/tests/test_alabama_war_generic_forecast.py`; `scripts/tests/test_forecast_polling_replay.py`; `data/processed/forecast_calibration/alabama_war_forecast_v1_*`; `project_docs/model/ALABAMA_WAR_FORECAST_FIELD_CONTRACT.md`; `project_docs/model/ALABAMA_WAR_GENERIC_FORECAST_V1.md`; `project_docs/audits/ALABAMA_WAR_FORECAST_VALIDATION.md`.
- Warehouse mode: `read-only`.
- Inputs: the forecast's declared inputs; the generic-ballot poll catalog.
- Outputs: `alabama_war_forecast_v1_2026_environment_seat_joint.csv`, `alabama_war_forecast_v1_polling_replay.csv`, `alabama_war_forecast_v1_run_ledger.csv`, manifest entries and field-contract rows for each.
- Acceptance checks: before/after comparison shows every pre-existing export identical in value (scenarios, full uncertainty, modeled seats, forward predictions and metrics); the joint export's marginal over environment equals the existing modeled-seat distribution exactly; the replay's latest date reproduces the current headline seat distribution; focused tests pass.
- Review requirement: parent self-checks plus the redesign's independent validation pass.
- Publication authority: none. Owner chose a local build only on 2026-10-03.
- Recovery/replay: the forecast script rewrites its own bundle deterministically from fixed seed; the pre-change bundle is copied to the session scratchpad before rerunning so value identity can be checked.
- Handoff recipient: `web_product`.
- Known risks: the replay uses polls by field end date, not release date, so a few late-released polls appear earlier than readers saw them; the roster is today's for every replay date. Both limitations must be stated beside the chart.

## Handoff state (2026-10-03, blocked on owner permission)

- Done: `scripts/build_silver_bplus_polling_environment.py` exposes `load_topline_catalog()` and `topline_as_of()`; rerunning it reproduced both processed polling outputs byte for byte.
- Partially applied: `scripts/run_alabama_war_generic_forecast.py` gained `_war_training()` (cached training load), `scenario_frame_for()`, `simulate_headline()` (same draw order), `modeled_seat_counts()`, `environment_seat_joint()`, `fixed_seats()`, `seat_summary()`, and `predict_scenarios()` now returns seven values (adds the joint frame and per-draw seat counts).
- Not applied: the matching `main()` edit (unpack seven values, check the joint margin, write the joint export and run ledger, list both in the manifest, correct the stale "candidate history is false" sentences in the generated model card and validation note). The auto-mode permission classifier denied it as a shared-resource modification. **Do not run the forecast script in this state; `main()` will fail at unpacking.**
- Not started: `scripts/build_forecast_polling_replay.py`, tests, field-contract rows, the rerun and the before/after value comparison (pre-change bundle saved in the session scratchpad).
- Next safe action: with owner permission, apply the prepared `main()` edit (scratchpad `edit_forecast_main.py`), rerun the forecast in the foreground, and compare every pre-existing export with the saved bundle; or revert the partial edit.

## Handoff state (2026-10-04, owner approved the edit and the rerun)

- Applied the prepared `main()` edit. The owner then explicitly approved rerunning the forecast after auto mode refused it.
- **Rerun.** Ran `run_alabama_war_generic_forecast.py` in the foreground; it produced build `ebf2d7e172b6f0e1a66a`.
  - Every pre-existing export is byte-identical to the saved pre-change bundle: scenarios, full uncertainty, modeled seats, forward predictions and metrics, historical panel, probability families.
  - The manifest differs only in four places: `build_id`, `generated_at_utc`, the field-contract input hash (the new "Graphics exports" section), and the two new outputs.
- **New outputs.**
  - `alabama_war_forecast_v1_2026_environment_seat_joint.csv` (202 rows). Its environment margin reproduces the modeled-seat distribution exactly; the run checks this and the test does too.
  - `alabama_war_forecast_v1_run_ledger.csv` (2 rows).
  - `alabama_war_forecast_v1_polling_replay.csv` and its manifest, from the new `scripts/build_forecast_polling_replay.py`.
- **Replay coverage.** The replay covers 9 weekly dates, 2026-07-14 to 2026-09-08. The quality-gated catalog holds 12 polls, the first ending 2026-06-22, and dates with fewer than 3 pollsters in the window are omitted. The current date reproduces the published distribution exactly; the replay refuses to run otherwise.
- **Tests.** `test_alabama_war_generic_forecast` 6, `test_forecast_polling_replay` 3, `test_silver_pollster_quality_gate` 1, `test_forecast_candidate_history` 7, `test_forecast_dashboard` 24: all pass with `-p no:cacheprovider`.
- **Page.** The forecast page charts both exports in the "If the polls are off" and "How the outlook moves with the polls" sections. The page refuses a replay that names a different build.
- **Open item.** Independent review comes with the redesign's validation pass. No publication.

## Handoff state (2026-10-05, national environment changed to Silver Bulletin)

- **Owner instruction.** "Rerun to update the national polling average", then: use the Silver Bulletin generic-ballot tracker. A Split Ticket average was asked for first, but none is published.
- **New adapter.** `scripts/build_silver_bulletin_generic_ballot_environment.py --fetch` registered snapshot `silver_bulletin_generic_ballot_average_retrieved_2026-10-05.csv`:
  - 627 daily rows from 2025-01-17 to 2026-10-05, sha256 `5a4f708b…`;
  - the source is the public Datawrapper chart `rfiFi/4347`;
  - its manifest is in `data/raw/polling/silver_bulletin_generic_ballot/`.
- **Environment.** D 50.06 / R 41.20, giving a two-party D+9.71 (raw D+8.86) as of 2026-10-05. The baseline prefers it and records `environment_source = silver_bulletin_generic_ballot_average`.
- **VoteHub refresh, run first that day.** It is preserved: both catalog snapshots, 2026-09-14 and 2026-10-05, are in `data/raw/polling/votehub_catalog_snapshots/` with a manifest. The working catalog was refreshed in place, as the established script does.
- **Forecast.** Rerun as build `ca64e43e988cc59c12bc`. Toplines are unchanged: House median 29 (80% range 29–30), Senate median 9.
- **Polling replay.** It now uses the tracker's daily series: 40 weekly dates from 2026-01-05 to 2026-10-05, D+5.6 to D+9.7. The House median stays at 29 throughout.
- **Page.** Provenance, methodology and replay copy now name Silver Bulletin.
- **Tests.**
  - `test_silver_bulletin_environment`: 3 new tests.
  - `test_forecast_polling_replay`: rewritten for the series; 3 tests.
  - With `test_alabama_war_generic_forecast` and `test_forecast_candidate_history`: 20 passed.
  - `test_forecast_dashboard` and related checks: 49 passed.
- **Documentation.** Section 9 of the policy audit records the decision, the conversion, the fallbacks and the shared-contract wording conflict.
