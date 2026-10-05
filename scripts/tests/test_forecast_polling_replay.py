"""The polling replay re-applies the published average rule; it is not a forecast archive."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

import build_forecast_polling_replay as replay
import build_silver_bplus_polling_environment as polling

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/processed/forecast_calibration"
PREFIX = "alabama_war_forecast_v1"


def test_topline_rule_reproduces_the_published_environment():
    catalog, _ = polling.load_topline_catalog()
    published = pd.read_csv(ROOT / "data/processed/polling/votehub_silver_bplus_topline_environment.csv").iloc[0]
    topline = polling.topline_as_of(catalog, published.as_of)
    assert abs(topline["dem_two_party_margin"] - published.dem_two_party_margin) < 1e-9
    assert topline["pollsters"] == published.pollsters


def test_replay_dates_step_weekly_back_over_the_series():
    series = pd.Series(1.0, index=pd.date_range("2025-12-01", "2026-03-01", freq="D"))
    dates = replay.replay_dates(series, pd.Timestamp("2026-03-01"))
    assert dates[-1] == pd.Timestamp("2026-03-01")
    assert all((later - earlier).days == 7 for earlier, later in zip(dates, dates[1:]))
    assert dates[0] >= replay.EARLIEST
    gappy = series.drop(pd.Timestamp("2026-02-22"))
    assert pd.Timestamp("2026-02-22") not in replay.replay_dates(gappy, pd.Timestamp("2026-03-01"))


def test_replay_follows_the_silver_bulletin_environment():
    rows = pd.read_csv(OUT / f"{PREFIX}_polling_replay.csv")
    series = replay.load_series()
    margins = rows.drop_duplicates("as_of").set_index("as_of").generic_ballot_margin
    for as_of, margin in margins.items():
        assert abs(series.loc[pd.Timestamp(as_of)] - margin) < 1e-9
    baseline = pd.read_csv(ROOT / "data/processed/war/2026_poll_adjusted_baseline.csv")
    assert set(baseline.environment_source) == {"silver_bulletin_generic_ballot_average"}
    assert margins.index.max() == baseline.poll_average_as_of.iloc[0]


def test_replay_names_the_current_run_and_ends_at_the_published_outlook():
    manifest = json.loads((OUT / f"{PREFIX}_manifest.json").read_text(encoding="utf-8"))
    replay_manifest = json.loads((OUT / f"{PREFIX}_polling_replay_manifest.json").read_text(encoding="utf-8"))
    rows = pd.read_csv(OUT / f"{PREFIX}_polling_replay.csv")
    ledger = pd.read_csv(OUT / f"{PREFIX}_run_ledger.csv")
    assert replay_manifest["forecast_build_id"] == manifest["build_id"]
    assert rows.forecast_build_id.eq(manifest["build_id"]).all()
    assert not rows.duplicated(["as_of", "chamber"]).any()
    latest = rows[rows.as_of.eq(rows.as_of.max())].set_index("chamber")
    assert latest.shift_from_current.eq(0).all()
    current = ledger[ledger.build_id.eq(manifest["build_id"])].drop_duplicates("chamber", keep="last").set_index("chamber")
    for column in ("dem_seats_median", "dem_seats_p10", "dem_seats_p90", "prob_dem_majority", "fixed_dem_seats"):
        np.testing.assert_allclose(latest[column].sort_index(), current[column].sort_index(), rtol=0, atol=1e-12)
    assert "release date" in " ".join(replay_manifest["limitations"])
