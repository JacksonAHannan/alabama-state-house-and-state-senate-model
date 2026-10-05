"""The national environment is the Silver Bulletin average, converted to a two-party margin."""
import csv
import hashlib
from pathlib import Path

import pandas as pd
import pytest

import build_silver_bulletin_generic_ballot_environment as silver

ROOT = Path(__file__).resolve().parents[2]
POLLING = ROOT / "data/processed/polling"


def test_two_party_conversion_and_validation(tmp_path):
    path = tmp_path / "chart.csv"
    path.write_text("modeldate,dem,rep,dem_lo,dem_hi,rep_lo,rep_hi\n"
                    "1/2/2026,48,42,0,0,0,0\n1/1/2026,47,43,0,0,0,0\n", encoding="utf-8")
    series = silver.parse_series(path)
    assert list(series.date.dt.day) == [1, 2]
    assert series.dem_raw_margin.tolist() == [4, 6]
    assert series.dem_two_party_margin.round(6).tolist() == [round(400 / 90, 6), round(600 / 90, 6)]
    bad = tmp_path / "bad.csv"
    bad.write_text("modeldate,dem,rep,dem_lo,dem_hi,rep_lo,rep_hi\n1/1/2026,48,42,0,0,0,0\n1/1/2026,47,43,0,0,0,0\n",
                   encoding="utf-8")
    with pytest.raises(ValueError, match="repeats"):
        silver.parse_series(bad)


def test_environment_matches_the_latest_registered_snapshot():
    rows = list(csv.DictReader(silver.MANIFEST.open(encoding="utf-8")))
    latest = max(rows, key=lambda r: r["retrieved_at_utc"])
    snapshot = silver.RAW / latest["file"]
    assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == latest["sha256"]
    assert {"source_page", "dataset_url", "retrieved_at_utc", "terms"} <= set(latest)
    series = silver.parse_series(snapshot)
    environment = pd.read_csv(POLLING / "silver_bulletin_generic_ballot_environment.csv").iloc[0]
    assert environment.as_of == series.date.max().date().isoformat()
    assert abs(environment.dem_two_party_margin - series.dem_two_party_margin.iloc[-1]) < 1e-12
    assert environment.snapshot_file == latest["file"]


def test_baseline_uses_the_silver_bulletin_environment():
    environment = pd.read_csv(POLLING / "silver_bulletin_generic_ballot_environment.csv").iloc[0]
    baseline = pd.read_csv(ROOT / "data/processed/war/2026_poll_adjusted_baseline.csv")
    assert set(baseline.environment_source) == {"silver_bulletin_generic_ballot_average"}
    assert (baseline.votehub_2026_dem_margin - environment.dem_two_party_margin).abs().max() < 1e-12
    assert (baseline.national_dem_swing_2024_2026 - (environment.dem_two_party_margin + 1.48)).abs().max() < 1e-9
    assert set(baseline.poll_average_as_of) == {environment.as_of}
