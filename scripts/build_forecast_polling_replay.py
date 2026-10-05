"""Replay the 2026 forecast's headline seat outlook under earlier polling averages.

The national environment is the Silver Bulletin generic-ballot average (owner decision
2026-10-05). On each weekly date the replay takes that tracker's published daily
average. That date's two-party margin moves the environment uniformly, through the same
shift the environment scenarios use. The roster, incumbency, candidate history,
structural model, error components and seed all stay at the current run.

The result is a sensitivity series, not an archived forecast history. The values come
from the tracker's current chart, which dates polls by fieldwork rather than by release
date and which the tracker may revise. The roster is today's for every date.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import run_alabama_war_generic_forecast as forecast

OUT = forecast.OUT
PREFIX = forecast.PREFIX
SERIES = forecast.ROOT / "data" / "processed" / "polling" / "silver_bulletin_generic_ballot_series.csv"
STEP_DAYS = 7
EARLIEST = pd.Timestamp("2026-01-01")


def load_series(path=SERIES) -> pd.Series:
    """Silver Bulletin's daily two-party Democratic margin, indexed by date."""
    frame = pd.read_csv(path, parse_dates=["date"])
    if frame.date.duplicated().any():
        raise ValueError("Generic-ballot series repeats a date")
    return frame.set_index("date").dem_two_party_margin.sort_index()


def replay_dates(series: pd.Series, current: pd.Timestamp, earliest: pd.Timestamp = EARLIEST) -> list[pd.Timestamp]:
    """Weekly dates ending at the current poll date, back to `earliest`, on dates the series covers."""
    dates = []
    date = current
    while date >= max(earliest, series.index.min()):
        if date in series.index:
            dates.append(date)
        date -= pd.Timedelta(days=STEP_DAYS)
    return sorted(dates)


def main() -> None:
    manifest = json.loads((OUT / f"{PREFIX}_manifest.json").read_text(encoding="utf-8"))
    scale = float(manifest["probability"]["scale"])
    current = forecast.prospective_features()
    adjustments = pd.read_csv(OUT / "alabama_forecast_candidate_history_race_adjustments.csv")
    component = pd.read_csv(OUT / "robust_forecast_v1_error_components.csv").iloc[0]
    fixed = forecast.fixed_seats(pd.read_csv(forecast.WAR / "2026_final_candidate_roster.csv"))
    published = pd.read_csv(OUT / f"{PREFIX}_2026_modeled_seats.csv")

    if set(current.environment_source) != {"silver_bulletin_generic_ballot_average"}:
        raise RuntimeError("The forecast environment is not the Silver Bulletin average; the replay would not match it")
    series = load_series()
    as_of = pd.Timestamp(str(current.poll_average_as_of.iloc[0]))
    current_margin = float(current.generic_ballot_environment_margin.iloc[0])
    if as_of not in series.index or abs(series.loc[as_of] - current_margin) > 1e-9:
        raise RuntimeError("The Silver Bulletin series does not reproduce the forecast's current generic-ballot margin")

    rows = []
    for date in replay_dates(series, as_of):
        margin = float(series.loc[date])
        shift = 0.0 if date == as_of else margin - current_margin
        frame, _, _ = forecast.scenario_frame_for(current, adjustments, scale, "polling_replay", shift, True)
        headline = frame.reset_index(drop=True)
        simulated, _ = forecast.simulate_headline(headline, component)
        counts = forecast.modeled_seat_counts(headline, simulated)
        if date == as_of:
            for chamber, chamber_counts in counts.items():
                values, frequencies = np.unique(chamber_counts, return_counts=True)
                expected = published[published.chamber.eq(chamber)].set_index("dem_modeled_seats").probability
                got = pd.Series(frequencies / forecast.SIMULATION_DRAWS, index=values)
                if not got.index.equals(expected.index) or not np.allclose(got.values, expected.values, rtol=0, atol=1e-12):
                    raise RuntimeError(f"Replay at the current poll date does not reproduce the published {chamber} seats")
        for chamber, chamber_counts in counts.items():
            rows.append({
                "as_of": date.date().isoformat(), "generic_ballot_margin": margin,
                "shift_from_current": shift, "forecast_build_id": manifest["build_id"],
                **forecast.seat_summary(chamber_counts, chamber, fixed),
            })
    replay = pd.DataFrame(rows)
    path = OUT / f"{PREFIX}_polling_replay.csv"
    replay.to_csv(path, index=False)
    replay_manifest = {
        "series": "polling_replay_sensitivity",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": forecast.git_commit(),
        "forecast_build_id": manifest["build_id"],
        "rule": "Silver Bulletin generic-ballot daily average (two-party margin) on each replay date",
        "environment_series": str(SERIES.relative_to(forecast.ROOT)).replace("\\", "/"),
        "environment_series_sha256": hashlib.sha256(SERIES.read_bytes()).hexdigest(),
        "step_days": STEP_DAYS, "earliest": EARLIEST.date().isoformat(),
        "dates": int(replay.as_of.nunique()), "first": replay.as_of.min(), "last": replay.as_of.max(),
        "held_constant": ["roster", "incumbency", "candidate_history", "structural_model", "error_components", "seed"],
        "limitations": [
            "Values are the tracker's daily average as shown in its current chart, which dates polls by fieldwork, not release date, and may be revised.",
            "The roster is the current roster for every date.",
        ],
        "output": {"path": str(path.relative_to(forecast.ROOT)).replace("\\", "/"), "rows": len(replay),
                   "sha256": hashlib.sha256(path.read_bytes()).hexdigest()},
    }
    (OUT / f"{PREFIX}_polling_replay_manifest.json").write_text(json.dumps(replay_manifest, indent=2) + "\n",
                                                               encoding="utf-8")
    print(f"polling replay: {replay_manifest['dates']} dates {replay_manifest['first']}..{replay_manifest['last']}")


if __name__ == "__main__":
    main()
