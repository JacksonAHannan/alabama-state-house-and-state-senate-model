# Alabama 2026 forecast graphics exports

Field rules for the summary exports the forecast page charts. They are kept apart from
`ALABAMA_WAR_FORECAST_FIELD_CONTRACT.md` because that contract is a declared input of the
published Alabama WAR v1 run, and editing it would invalidate that run. The exports summarize
the published simulation; they add no model input and change no existing forecast value.

- `alabama_war_forecast_v1_2026_environment_seat_joint.csv` has one row per chamber,
  environment bin and modeled Democratic seat count. Its fields are `chamber`,
  `environment_shift_low`, `environment_shift_high`, `dem_modeled_seats`, `draw_count`,
  `probability` and `draws`. The environment shift is each draw's national plus
  statewide error in Democratic margin points, the part of the draw that moves every
  district together. Bins are 1 point wide, closed on the low edge. Summing `draw_count`
  over environment bins must reproduce the modeled-seat distribution exactly. The run
  refuses to write otherwise.
- `alabama_war_forecast_v1_run_ledger.csv` is append-only, with one row per chamber for
  each distinct forecast result. Its fields are `build_id`, `generated_at_utc`,
  `git_commit`, `selected_specification`, `poll_average_as_of`, `generic_ballot_margin`,
  and the chamber topline. The topline fields are `chamber`, `chamber_seats`,
  `majority_threshold`, `fixed_dem_seats`, `fixed_rep_seats`, `dem_seats_mean`,
  `dem_seats_median`, `dem_seats_p10`, `dem_seats_p90`, `prob_dem_majority` and
  `draws`. Seat totals include the fixed single-major-party seats. Quantiles use the
  page's rule: the smallest total whose cumulative share reaches q. A rerun that
  reproduces an existing result keeps that result's first timestamp.
- `alabama_war_forecast_v1_polling_replay.csv` is written by
  `scripts/build_forecast_polling_replay.py`.
  - On weekly dates from 2026-01-01, it takes the Silver Bulletin generic-ballot daily
    average (two-party margin) from `silver_bulletin_generic_ballot_series.csv`. This is
    the same source as the forecast environment, by owner decision 2026-10-05.
  - Each date's margin moves the environment uniformly, through the same mechanism as the
    environment scenarios.
  - Every other input stays at the current run: roster, incumbency, candidate history,
    structural model, error components and seed.
  - Each row carries the chamber topline fields above, plus `as_of`,
    `generic_ballot_margin`, `shift_from_current` and `forecast_build_id`.
  - The row at the current poll date must reproduce the published seat distribution
    exactly. The replay also refuses to run if the forecast environment is not the
    Silver Bulletin average.
  - This is a sensitivity series, not an archived forecast history.
  - The values come from the tracker's current chart. That chart dates polls by
    fieldwork, not release date, and the tracker may revise it. The roster is today's for
    every date.
  - Any chart of the replay must say all of this.
