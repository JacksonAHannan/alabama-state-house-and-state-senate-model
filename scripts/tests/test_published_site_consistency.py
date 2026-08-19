from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
WAR = ROOT / "data" / "processed" / "war"


def test_publication_exports_match_current_model_outputs() -> None:
    pairs = [
        ("preliminary_cmo_candidates.csv", "preliminary_cmo_candidates.csv"),
        ("preliminary_cmo_races.csv", "preliminary_cmo_races.csv"),
        ("next_forecast_tournament_2026.csv", "next_forecast_tournament_2026.csv"),
        ("next_forecast_tournament_summary.csv", "next_forecast_tournament_summary.csv"),
        ("next_forecast_tournament_cycle_metrics.csv", "next_forecast_tournament_cycle_metrics.csv"),
    ]
    for source_name, public_name in pairs:
        assert (WAR / source_name).read_bytes() == (DOCS / "data" / public_name).read_bytes()


def test_public_pages_describe_current_runs() -> None:
    forecast = (DOCS / "index.html").read_text(encoding="utf-8")
    forecast_method = (DOCS / "methodology.html").read_text(encoding="utf-8")
    cmo = (DOCS / "cmo.html").read_text(encoding="utf-8")
    cmo_method = (DOCS / "cmo-methodology.html").read_text(encoding="utf-8")

    assert "poll-adjusted presidential baseline plus 20% of CMO expected performance" in forecast
    assert "applies the full CMO expected-performance adjustment" in forecast
    assert "50,000 deterministic-seed simulations" in forecast_method
    assert "two after 2016" in forecast_method
    assert "poll-adjusted presidential baseline + 100%" in forecast_method
    assert "Alabama Candidate Margin Overperformance" in cmo
    assert "Build updated August 17, 2026" in cmo
    assert "Canonical fundraising" in cmo
    assert "Spending complete · FTM" not in cmo
    assert "8 cycles:" in cmo_method
    assert "<b>509</b> contested" in cmo_method
    assert "352 of 509 races (69.2%)" in cmo_method


def test_public_cmo_and_forecast_row_counts() -> None:
    candidates = pd.read_csv(DOCS / "data" / "preliminary_cmo_candidates.csv")
    races = pd.read_csv(DOCS / "data" / "preliminary_cmo_races.csv")
    forecasts = pd.read_csv(DOCS / "data" / "next_forecast_tournament_2026.csv")
    assert len(candidates) == 1018
    assert len(races) == 509
    assert candidates.candidate_cmo_total_oof.notna().all()
    assert set(races.cycle) == {1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022}
    assert forecasts.groupby("specification").size().eq(47).all()
