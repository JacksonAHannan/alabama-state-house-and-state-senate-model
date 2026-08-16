"""Download and summarize VoteHub's 2026 generic-ballot polling feed."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "polling"
API = "https://api.votehub.com/polls"
WINDOW_WEIGHTS = {7: 0.30, 14: 0.50, 21: 0.20}
POPULATION_WEIGHTS = {"lv": 1.0, "rv": 0.75, "a": 0.5}


def party_pct(answers: list[dict], party: str) -> float:
    aliases = {"dem": {"dem", "democrat", "democratic"},
               "rep": {"rep", "republican", "gop"}}[party]
    for answer in answers or []:
        if str(answer.get("choice", "")).strip().lower() in aliases:
            return float(answer["pct"])
    return np.nan


def normalize(polls: list[dict]) -> pd.DataFrame:
    rows = []
    for poll in polls:
        dem, rep = party_pct(poll.get("answers", []), "dem"), party_pct(poll.get("answers", []), "rep")
        rows.append({
            "poll_id": poll.get("id"), "pollster": poll.get("pollster"),
            "sponsors": " | ".join(poll.get("sponsors") or []),
            "start_date": poll.get("start_date"), "end_date": poll.get("end_date"),
            "created_at": poll.get("created_at"), "sample_size": poll.get("sample_size"),
            "population": str(poll.get("population") or "").lower(),
            "internal": bool(poll.get("internal")), "partisan": poll.get("partisan"),
            "subject": poll.get("subject"), "dem_pct": dem, "rep_pct": rep,
            "dem_margin_raw": dem - rep,
            "dem_margin_two_party": 100 * (dem - rep) / (dem + rep) if dem + rep > 0 else np.nan,
            "url": poll.get("url"),
        })
    frame = pd.DataFrame(rows)
    frame["end_date"] = pd.to_datetime(frame.end_date)
    return frame.sort_values(["end_date", "pollster", "poll_id"]).reset_index(drop=True)


def window_average(frame: pd.DataFrame, days: int, as_of: pd.Timestamp) -> tuple[float, int]:
    start = as_of - pd.Timedelta(days=days - 1)
    eligible = frame[(frame.end_date.between(start, as_of)) & ~frame.internal & frame.partisan.isna()].copy()
    eligible = eligible.dropna(subset=["dem_margin_two_party"])
    # One release per pollster/sponsor in each window prevents prolific series dominating.
    eligible = eligible.sort_values(["end_date", "population"]).drop_duplicates(
        ["pollster", "sponsors"], keep="last")
    weights = eligible.population.map(POPULATION_WEIGHTS).fillna(0.5)
    if eligible.empty or weights.sum() == 0:
        return np.nan, 0
    return float(np.average(eligible.dem_margin_two_party, weights=weights)), len(eligible)


def summarize(frame: pd.DataFrame, fetched_on: date) -> pd.DataFrame:
    as_of = frame.end_date.max()
    values = {days: window_average(frame, days, as_of) for days in WINDOW_WEIGHTS}
    available = [(days, avg, count) for days, (avg, count) in values.items() if pd.notna(avg)]
    weight_total = sum(WINDOW_WEIGHTS[d] for d, _, _ in available)
    average = sum(WINDOW_WEIGHTS[d] * avg for d, avg, _ in available) / weight_total
    return pd.DataFrame([{
        "poll_average_as_of": as_of.date().isoformat(), "downloaded_on": fetched_on.isoformat(),
        "staleness_days": (pd.Timestamp(fetched_on) - as_of).days,
        "generic_ballot_dem_margin_two_party": average,
        **{f"average_{d}d": values[d][0] for d in WINDOW_WEIGHTS},
        **{f"pollsters_{d}d": values[d][1] for d in WINDOW_WEIGHTS},
        "method": "30pct_7d_50pct_14d_20pct_21d_latest_pollster_sponsor_population_weighted",
        "source": API, "license": "CC BY 4.0 / VoteHub",
    }])


def main() -> None:
    response = requests.get(API, params={"poll_type": "generic-ballot"}, timeout=60)
    response.raise_for_status()
    payload = response.json()
    polls = payload["polls"] if isinstance(payload, dict) else payload
    frame = normalize(polls)
    if frame.empty:
        raise RuntimeError("VoteHub returned no generic-ballot polls")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "votehub_generic_ballot_raw.json").write_text(json.dumps(polls, indent=2), encoding="utf-8")
    frame.to_csv(OUT / "votehub_generic_ballot_polls.csv", index=False)
    summary = summarize(frame, date.today())
    summary.to_csv(OUT / "votehub_generic_ballot_snapshot.csv", index=False)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
