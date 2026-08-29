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
        (CAL / "post2016_headline_v1_manifest.json").read_text(encoding="utf-8")
    )
    metrics = pd.read_csv(CAL / "post2016_headline_v1_forward_metrics.csv")
    selected = metrics.loc[
        metrics.specification.eq(manifest["selected_specification"]), "mae"
    ]
    assert len(selected) == 1
    mae = float(selected.iloc[0])
    assert abs(mae - float(manifest["forward_validation"]["mae"])) < 1e-12
    return mae


def test_publication_exports_match_current_model_outputs() -> None:
    current_pairs = [
        ("cmo_v6_southern_candidates.csv", "cmo_v6_southern_candidates.csv"),
        ("cmo_v6_southern_races.csv", "cmo_v6_southern_races.csv"),
        ("cmo_v6_southern_quality.csv", "cmo_v6_southern_quality.csv"),
        ("cmo_v6_southern_validation.csv", "cmo_v6_southern_validation.csv"),
        ("cmo_v6_southern_manifest.json", "cmo_v6_southern_manifest.json"),
    ]
    for source_name, public_name in current_pairs:
        assert (WAR / source_name).read_bytes() == (DOCS / "data" / public_name).read_bytes()

    forecast_names = [
        "post2016_headline_v1_2026_scenarios.csv",
        "post2016_headline_v1_2026_full_uncertainty.csv",
        "post2016_headline_v1_2026_modeled_seats.csv",
        "post2016_headline_v1_forward_metrics.csv",
        "post2016_headline_v1_bootstrap.csv",
        "post2016_headline_v1_manifest.json",
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
    assert "59 contested races in 2018" in forecast_method
    assert (
        f"The headline specification records {headline_mae:.2f} points of mean absolute margin error"
        in forecast_method
    )
    assert "Headline: direct relative fundraising" in forecast_method
    assert "50,000 simulations" in forecast_method
    for stale in (
        "Basic and Fundamentals+", "six-point normal", "20% of the CMO",
        "893 model-ready contests", "Build <b>", "robust forecast build",
    ):
        assert stale not in forecast_method

    assert "Alabama Legislative Wins Above Replacement (WAR)" in cmo
    assert "WAR is the headline candidate-quality estimate" in cmo
    assert "Historical accuracy" in cmo
    assert "Fundamentals+" not in cmo
    assert "selected same-district ticket" in cmo
    assert "1994" in cmo_method and "2022" in cmo_method
    assert "What WAR estimates" in cmo_method
    assert "Wins Above Replacement (WAR)" in cmo_method
    assert "same-cycle federal ticket" in cmo_method
    assert "pair-differential-only" in cmo_method
    assert "Fundamentals+" not in cmo_method
    for stale in (
        "arithmetic is unchanged", "The decomposition is separate from CMO",
        "CMO v6 preserves", "Direct CMO is unchanged from", "portable_temporal",
    ):
        assert stale not in cmo
        assert stale not in cmo_method


def test_public_cmo_and_forecast_row_counts() -> None:
    candidates = pd.read_csv(DOCS / "data" / "cmo_v6_southern_candidates.csv")
    races = pd.read_csv(DOCS / "data" / "cmo_v6_southern_races.csv")
    forecasts = pd.read_csv(DOCS / "data" / "post2016_headline_v1_2026_scenarios.csv")
    assert len(candidates) == 1018
    assert len(races) == 509
    assert candidates.candidate_direct_cmo.notna().all()
    assert set(races.cycle) == {1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022}
    assert set(forecasts.scenario) == {"headline", "environment_dem_favorable", "environment_rep_favorable"}
    assert forecasts.groupby("scenario").size().eq(48).all()


def test_public_quality_map_is_race_differential_not_democratic_effect() -> None:
    page = (DOCS / "cmo.html").read_text(encoding="utf-8")
    payload = json.loads(re.search(r"const DATA=(\{.*?\});\n", page, re.S).group(1))
    races = pd.read_csv(DOCS / "data" / "cmo_v6_southern_races.csv")
    for row in races.itertuples():
        displayed = payload[f"{row.cycle}-{row.chamber}"]["demPair"][str(row.district)]
        assert abs(displayed - round(row.pooled_quality_differential, 2)) < 1e-9


def test_hd32_2022_uses_direct_cmo_v6_score() -> None:
    candidates = pd.read_csv(DOCS / "data" / "cmo_v6_southern_candidates.csv")
    races = pd.read_csv(DOCS / "data" / "cmo_v6_southern_races.csv")
    boyd = candidates.loc[
        (candidates.cycle == 2022)
        & candidates.chamber.eq("house")
        & candidates.district.eq(32)
        & candidates.canonical_party.eq("D")
    ].squeeze()
    race = races.loc[
        (races.cycle == 2022) & races.chamber.eq("house") & races.district.eq(32)
    ].squeeze()
    assert boyd.candidate_direct_cmo == race.direct_cmo
    assert race.selected_ticket_source == "same_cycle_federal"
    assert boyd.southern_quality_status == "uncertain"


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
