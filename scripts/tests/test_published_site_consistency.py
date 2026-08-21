from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
WAR = ROOT / "data" / "processed" / "war"


def test_publication_exports_match_current_model_outputs() -> None:
    pairs = [
        ("cmo_v2_candidates.csv", "cmo_v2_candidates.csv"),
        ("cmo_v2_races.csv", "cmo_v2_races.csv"),
        ("cmo_v2_diagnostics.csv", "cmo_v2_diagnostics.csv"),
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
    assert "P(D win) = Φ(expected Democratic margin / 6.0)" in forecast_method
    assert "1,188 contested legislative races" in forecast_method
    assert "two after 2016" in forecast_method
    assert "poll-adjusted presidential baseline + 100%" in forecast_method
    assert "Alabama Candidate Margin Overperformance" in cmo
    assert "Build updated August 21, 2026" in cmo
    assert "Candidate-variable-free context" in cmo
    assert "Fundamentals+" not in cmo
    assert "Predictive residual" in cmo
    assert "8 cycles:" in cmo_method
    assert "<b>509</b> contested" in cmo_method
    assert "Four separate measures" in cmo_method
    assert "Source-aware political baseline" in cmo_method
    assert "Fundamentals+" not in cmo_method


def test_public_cmo_and_forecast_row_counts() -> None:
    candidates = pd.read_csv(DOCS / "data" / "cmo_v2_candidates.csv")
    races = pd.read_csv(DOCS / "data" / "cmo_v2_races.csv")
    forecasts = pd.read_csv(DOCS / "data" / "next_forecast_tournament_2026.csv")
    assert len(candidates) == 1018
    assert len(races) == 509
    assert candidates.candidate_context_cmo.notna().all()
    assert set(races.cycle) == {1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022}
    assert forecasts.groupby("specification").size().eq(48).all()


def test_hd32_2022_uses_fresh_cmo_v2_score() -> None:
    candidates = pd.read_csv(DOCS / "data" / "cmo_v2_candidates.csv")
    races = pd.read_csv(DOCS / "data" / "cmo_v2_races.csv")
    boyd = candidates.loc[
        (candidates.cycle == 2022)
        & candidates.chamber.eq("house")
        & candidates.district.eq(32)
        & candidates.canonical_party.eq("D")
    ].squeeze()
    race = races.loc[
        (races.cycle == 2022) & races.chamber.eq("house") & races.district.eq(32)
    ].squeeze()

    assert -5 < boyd.candidate_context_cmo < -4
    assert boyd.candidate_context_cmo == race.context_cmo
    assert race.baseline_source_v2 == "state_ticket_70_federal_30"


def test_public_probability_export_matches_current_model_output() -> None:
    source = ROOT / "data" / "processed" / "forecast_calibration" / "production_probability_2026.csv"
    assert source.read_bytes() == (DOCS / "data" / "production_probability_2026.csv").read_bytes()
