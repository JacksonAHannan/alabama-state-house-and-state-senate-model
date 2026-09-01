from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
WAR = ROOT / "data" / "processed" / "war"
CAL = ROOT / "data" / "processed" / "forecast_calibration"


def selected_headline_mae() -> float:
    manifest = json.loads(
        (CAL / "alabama_war_forecast_v1_manifest.json").read_text(encoding="utf-8")
    )
    metrics = pd.read_csv(CAL / "alabama_war_forecast_v1_forward_metrics.csv")
    selected = metrics.loc[
        metrics.specification.eq(manifest["selected_specification"]), "mae"
    ]
    assert len(selected) == 1
    mae = float(selected.iloc[0])
    assert abs(mae - float(manifest["diagnostics"]["selected_forward_mae"])) < 1e-12
    return mae


def test_publication_exports_match_current_model_outputs() -> None:
    current_pairs = [
        ("alabama_war_v1/candidate_cycle_war.csv", "alabama_war_v1_candidate_cycle_war.csv"),
        ("alabama_war_v1/race_war.csv", "alabama_war_v1_race_war.csv"),
        ("alabama_war_v1/coverage.csv", "alabama_war_v1_coverage.csv"),
        ("alabama_war_v1/manifest.json", "alabama_war_v1_manifest.json"),
    ]
    for source_name, public_name in current_pairs:
        assert (WAR / source_name).read_bytes() == (DOCS / "data" / public_name).read_bytes()

    forecast_names = [
        "alabama_war_forecast_v1_2026_scenarios.csv",
        "alabama_war_forecast_v1_2026_full_uncertainty.csv",
        "alabama_war_forecast_v1_2026_modeled_seats.csv",
        "alabama_war_forecast_v1_forward_predictions.csv",
        "alabama_war_forecast_v1_forward_metrics.csv",
        "alabama_war_forecast_v1_probability_families.csv",
        "alabama_war_forecast_v1_manifest.json",
        "robust_forecast_v1_error_components.csv",
    ]
    for name in forecast_names:
        assert (CAL / name).read_bytes() == (DOCS / "data" / name).read_bytes()


def test_public_pages_describe_current_runs() -> None:
    forecast = (DOCS / "index.html").read_text(encoding="utf-8")
    forecast_method = (DOCS / "methodology.html").read_text(encoding="utf-8")
    cmo = (DOCS / "cmo.html").read_text(encoding="utf-8")
    cmo_method = (DOCS / "cmo-methodology.html").read_text(encoding="utf-8")
    headline_mae = selected_headline_mae()

    assert "Forecast and polling-error scenarios" in forecast
    assert "Dem scenario" in forecast and "Rep scenario" in forecast
    assert "Student-t" in forecast_method
    assert "64 contested 2018 races" in forecast_method
    assert (
        f"records {headline_mae:.2f} points of MAE"
        in forecast_method
    )
    assert "candidate_history_used=false" in forecast_method
    assert "50,000 correlated simulations" in forecast_method
    for stale in (
        "Basic and Fundamentals+", "six-point normal", "20% of the CMO",
        "893 model-ready contests", "robust forecast build",
    ):
        assert stale not in forecast_method

    assert "Alabama WAR" in cmo
    assert "These are race residuals, not pooled career effects" in cmo
    assert "Fundamentals+" not in cmo
    assert "actual legislative-minus-ticket gap" in cmo
    assert "2018" in cmo_method and "2022" in cmo_method
    assert "1. Estimand" in cmo_method
    assert "No pooled individual candidate effect" in cmo_method
    assert "same-cycle fitted structural gap" in cmo_method
    assert "Fundamentals+" not in cmo_method
    for stale in (
        "arithmetic is unchanged", "The decomposition is separate from CMO",
        "CMO v6 preserves", "Direct CMO is unchanged from", "portable_temporal",
    ):
        assert stale not in cmo
        assert stale not in cmo_method


def test_public_cmo_and_forecast_row_counts() -> None:
    candidates = pd.read_csv(DOCS / "data" / "alabama_war_v1_candidate_cycle_war.csv")
    races = pd.read_csv(DOCS / "data" / "alabama_war_v1_race_war.csv")
    forecasts = pd.read_csv(DOCS / "data" / "alabama_war_forecast_v1_2026_scenarios.csv")
    assert len(candidates) == 194
    assert len(races) == 97
    assert candidates.candidate_cycle_war.notna().all()
    assert set(races.cycle) == {2018, 2022}
    assert set(forecasts.scenario) == {"headline", "environment_dem_favorable", "environment_rep_favorable"}
    assert forecasts.groupby("scenario").size().eq(48).all()


def test_public_war_page_uses_candidate_cycle_residuals() -> None:
    page = (DOCS / "cmo.html").read_text(encoding="utf-8")
    payload = json.loads(re.search(r"const DATA=(\[.*?\]);", page, re.S).group(1))
    candidates = pd.read_csv(DOCS / "data" / "alabama_war_v1_candidate_cycle_war.csv")
    grimsley = next(row for row in payload if row["candidate"] == "Dexter Grimsley")
    source = candidates[candidates.candidate_name.eq("Dexter Grimsley")].squeeze()
    assert abs(grimsley["war"] - source.candidate_cycle_war) < 1e-10


def test_grimsley_public_war_is_corrected_race_residual() -> None:
    candidates = pd.read_csv(DOCS / "data" / "alabama_war_v1_candidate_cycle_war.csv")
    grimsley = candidates[candidates.candidate_name.eq("Dexter Grimsley")].squeeze()
    assert abs(grimsley.candidate_cycle_war - 13.295433950839808) < 1e-10
    assert grimsley.score_identification == "race_differential_party_orientation"


def test_public_ideology_and_caucus_routes_are_merged() -> None:
    ideology = (DOCS / "ideology-performance.html").read_text(encoding="utf-8")
    caucus = (DOCS / "caucuses.html").read_text(encoding="utf-8")
    section_order = [
        ideology.index(f'<section id="{section}"')
        for section in (
            "performance", "overview", "transition", "positions",
            "distribution", "time", "issues", "cases",
            "candidate-explorer", "continuous", "methods",
        )
    ]
    assert section_order == sorted(section_order)
    assert "WAR relative to progressive-modern candidates" in ideology
    assert "Adjusted raw ticket comparisons" in ideology
    assert ideology.index("WAR relative to progressive-modern candidates") < ideology.index(
        "Adjusted raw ticket comparisons"
    )
    for group in (
        "Traditionalist-populist Democrats",
        "Bridge-coalition Democrats",
        "Progressive-modern Democrats",
    ):
        assert group in ideology
    payload = json.loads(re.search(r"const DATA=(\{.*?\});\n", ideology, re.S).group(1))
    assert payload["schemaVersion"] == 2
    assert payload["groups"] == [
        "Traditionalist-populist Democrats",
        "Bridge-coalition Democrats",
        "Progressive-modern Democrats",
    ]
    assert all(row["candidate_quality_index"] is not None for row in payload["members"])
    assert all("candidate_cmo" not in row for row in payload["members"])
    assert all("candidate_quality_residual" not in row for row in payload["members"])
    assert "WAR means Wins Above Replacement" in ideology
    assert "Split Ticket's WAR methodology" in ideology
    assert "https://split-ticket.org/2025/08/15/deconstructing-war/" in ideology
    assert "Candidate Quality Index" not in ideology
    assert "CQI" not in ideology
    assert "Candidate Atlas" not in ideology
    assert "legislators.html" not in ideology
    assert "Alabama Democratic groupings, 1998–2022" in ideology
    assert 'id="transitionChart"' in ideology
    assert 'id="candidate-explorer"' in ideology
    assert "render3D" not in ideology
    assert 'id="threeD"' not in ideology
    assert "three-d-wrap" not in ideology
    assert 'ideology-performance.html#candidate-explorer' in caucus
    assert "location.replace" in caucus


def test_public_pages_avoid_internal_release_vocabulary() -> None:
    stale_phrases = (
        "arithmetic is unchanged",
        "the decomposition is separate from cmo",
        "cmo v6 preserves",
        "direct cmo is unchanged from",
        "validated robust forecast build",
        "owner_selected_public_headline",
        "common-population forward tournament",
        "portable_temporal",
        "canonical modern finance input",
        "geographic pipeline where documented",
    )
    for page in DOCS.glob("*.html"):
        text = page.read_text(encoding="utf-8").lower()
        for phrase in stale_phrases:
            assert phrase not in text, f"{phrase!r} remains in {page.name}"
