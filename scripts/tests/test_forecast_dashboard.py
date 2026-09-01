import json
import re
from pathlib import Path

from bs4 import BeautifulSoup
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "artifacts" / "site" / "alabama-2026-legislative-forecast.html"
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


def page_and_payload():
    text = PAGE.read_text(encoding="utf-8")
    match = re.search(r"const DATA=(.*?);\(\(\) =>", text, re.S)
    assert match
    return text, json.loads(match.group(1))


def test_dashboard_contains_both_chambers_and_cmo_typography():
    text, data = page_and_payload()
    assert "Libre+Franklin" in text
    assert "--navy:#14253d" in text
    assert len(data["house"]["races"]) == 105
    assert len(data["senate"]["races"]) == 35
    assert data["house"]["seatDistribution"]
    assert data["senate"]["seatDistribution"]


def test_dashboard_has_accessible_controls_and_fallbacks():
    soup = BeautifulSoup(PAGE.read_text(encoding="utf-8"), "html.parser")
    assert soup.select_one("#detail[aria-live='polite']")
    assert soup.select_one("#map[role='group']")
    assert soup.select_one("button[data-chamber='house'][aria-pressed]")
    assert soup.select_one("button[data-mode='probability'][aria-pressed]")
    assert soup.select_one("#districtSelect")
    assert soup.select_one("#download")


def test_scenario_tab_arrow_navigation_restores_focus_after_rerender():
    text = PAGE.read_text(encoding="utf-8")
    assert 'selectModel(tabs[n].dataset.model);requestAnimationFrame' in text
    assert 'document.querySelector(`[data-model="${state.model}"]`)?.focus()' in text


def test_dashboard_explains_headline_and_scenarios():
    text = PAGE.read_text(encoding="utf-8")
    assert "Headline" in text
    assert "Dem scenario" in text
    assert "Rep scenario" in text
    assert "Candidate history and fundraising are not forecast inputs" in text
    assert "Student-t" in text
    assert "50,000 simulations" in text
    assert "Shared national, statewide, and chamber" in text
    assert "six-point normal calibration" not in text


def test_model_switcher_and_default_decomposition_are_complete():
    text, data = page_and_payload()
    assert data["meta"]["model"] == "headline"
    manifest = json.loads((ROOT / "data" / "processed" / "forecast_calibration" / "alabama_war_forecast_v1_manifest.json").read_text(encoding="utf-8"))
    assert data["meta"]["version"] == manifest["build_id"]
    assert len(data["models"]) == 3
    assert sum(model["default"] for model in data["models"]) == 1
    assert 'id="modelTabs"' in text
    race = next(r for r in data["house"]["races"] if r["status"] == "modeled")
    assert set(race["models"]) == {model["id"] for model in data["models"]}
    default = race["models"]["headline"]
    assert default["steps"]
    assert len(data["contributionVariables"]) == len(default["steps"])
    assert abs(default["steps"][-1][2] - default["margin"]) < 1e-8
    assert 'const PUBLIC_MODEL=DATA.meta.model' in text
    assert 'cmo_expectation__blend20' not in text


def test_comparison_ui_provenance_and_mobile_table_contract():
    text, data = page_and_payload()
    assert all(model.get("status") and model.get("description") for model in data["models"])
    assert len(data["provenance"]) >= 6
    assert "Models disagree on winner" in text
    assert "Forecast components" in text
    assert "Path to a majority" in text
    assert "Seats to watch" in text
    assert "Data sources and freshness" in text
    assert "Finance scenario</th>" not in text
    assert "difference_from_headline" in text
    assert "URLSearchParams(location.search)" in text
    assert 'aria-controls="workspace"' in text


def test_chamber_paths_and_competitive_overview_are_scenario_aware():
    text, data = page_and_payload()
    assert 'id="majorityPath"' in text
    assert 'id="raceWatch"' in text
    assert "function renderMajorityPath()" in text
    assert "function renderRaceWatch()" in text
    assert "data-jump-district" in text
    for chamber, total in (("house", 105), ("senate", 35)):
        majority = total // 2 + 1
        for model in data["models"]:
            distribution = data[chamber]["modelSeatDistributions"][model["id"]]
            assert abs(sum(row["probability"] for row in distribution) - 1) < 1e-8
            assert all(0 <= row["demSeats"] <= total for row in distribution)
            control = sum(row["probability"] for row in distribution if row["demSeats"] >= majority)
            assert 0 <= control <= 1


def test_district_profiles_use_current_context_and_preserve_missingness():
    _, data = page_and_payload()
    races = [race for chamber in ("house", "senate") for race in data[chamber]["races"]]
    assert len(races) == 140
    assert all(race["profile"] for race in races)
    assert all(race["pres24"] is not None for race in races)
    assert all(race["profile"]["priorResult"] for race in races)
    assert all(race["profile"]["blackCvapShare"] is not None for race in races)
    assert all(race["profile"]["collegeShare"] is not None for race in races)
    assert any(race["profile"]["regions"] for race in races)


def test_component_rows_reconcile_and_scenarios_compare_like_for_like():
    text, data = page_and_payload()
    assert "componentComparisonHtml" in text
    assert "The headline evaluates a generic Democrat against a generic Republican" in text
    for chamber in ("house", "senate"):
        for race in (row for row in data[chamber]["races"] if row["status"] == "modeled"):
            for model in data["models"]:
                values = race["models"][model["id"]]
                assert abs(values["steps"][-1][2] - values["margin"]) < 1e-8


def test_candidate_war_timelines_are_display_only():
    text, data = page_and_payload()
    candidates = [candidate for chamber in ("house", "senate") for race in data[chamber]["races"] for candidate in race["candidates"]]
    with_history = [candidate for candidate in candidates if candidate["warHistory"]]
    assert with_history
    assert "does not use prior WAR" in text
    assert "Candidate Atlas" not in text
    source = pd.read_csv(ROOT / "data" / "processed" / "war" / "alabama_war_v1" / "candidate_cycle_war.csv")
    example = with_history[0]
    for observation in example["warHistory"]:
        match = source[
            source.cycle.eq(observation["cycle"])
            & source.chamber.eq({"house": "lower", "senate": "upper"}[observation["chamber"]])
            & source.district.eq(observation["district"])
            & source.canonical_party.eq(example["party"])
        ]
        assert len(match) == 1
        assert abs(match.iloc[0].candidate_cycle_war - observation["war"]) < 1e-10


def test_personal_branding_and_profile_links():
    text = PAGE.read_text(encoding="utf-8")
    assert "Jackson Hannan" in text
    for url in [
        "https://github.com/JacksonAHannan",
        "https://www.instagram.com/topsoilintraining/",
        "https://substack.com/@jacksonhannan",
        "https://www.linkedin.com/in/jackson-hannan",
    ]:
        assert url in text


def test_uncertainty_axis_has_correct_party_direction():
    css = (ROOT / "dashboard" / "forecast_dashboard.css").read_text(encoding="utf-8")
    assert "linear-gradient(90deg,var(--red),#eee 50%,var(--blue))" in css


def test_live_probabilities_use_selected_generic_candidate_calibration():
    _, data = page_and_payload()
    hd21 = next(r for r in data["house"]["races"] if r["district"] == 21)
    headline = hd21["models"]["headline"]
    scenarios = pd.read_csv(CAL / "alabama_war_forecast_v1_2026_scenarios.csv")
    source = scenarios[
        scenarios.scenario.eq("headline") & scenarios.chamber.eq("house") & scenarios.district.eq(21)
    ].squeeze()
    assert abs(headline["demProbability"] - source.dem_win_probability) < 1e-6
    assert headline["high80"] > headline["low80"]


def test_sd25_is_a_contested_modeled_senate_race():
    _, data = page_and_payload()
    sd25 = next(r for r in data["senate"]["races"] if r["district"] == 25)
    assert sd25["status"] == "modeled"
    assert {(c["name"], c["party"]) for c in sd25["candidates"]} == {
        ("Phadra Carson Foster", "D"),
        ("Will Barfoot", "R"),
    }
    assert sd25["demProbability"] is not None
    assert all(r["status"] != "unmodeled" for r in data["senate"]["races"])


def test_map_starts_statewide_and_zooms_to_selected_district():
    text = PAGE.read_text(encoding="utf-8")
    assert 'if(state.selected&&!race(state.chamber,state.selected))state.selected=null' in text
    assert 'state.chamber=c;state.selected=null;syncUrl()' in text
    assert 'function updateMapViewport()' in text
    assert 'forecastMap.fitBounds(statewideBounds' in text
    assert 'forecastMap.fitBounds(selectedBounds' in text
    assert 'Statewide view</option>' in text
    assert 'else clearDistrict()' in text
    assert 'Select a district' in text


def test_map_colors_follow_current_probability_and_rating_bands():
    text = PAGE.read_text(encoding="utf-8")
    assert 'const RATING_COLORS=' in text
    assert 'const probabilityColor=p=>RATING_COLORS[ratingForProbability(p)]' in text
    assert 'if(state.mode==="rating") return RATING_COLORS[effectiveRating(r)]' in text
    assert 'if(state.mode==="probability") return probabilityColor(r.demProbability)' in text
    assert 'r.demProbability*200-100' not in text


def test_rating_thresholds_match_published_probability_bands():
    text, data = page_and_payload()
    assert 'q<.60?"Toss-up":q<.80?`Lean ${lead}`:q<.95?`Likely ${lead}`:q<.98?`Very likely ${lead}`:`Solid ${lead}`' in text
    assert "Very likely D" in text
    assert "Very likely R" in text
    assert "D 40–60%" in text
    assert "D 95–98%" in text
    ratings = {r["rating"] for chamber in ("house", "senate") for r in data[chamber]["races"]}
    assert ratings <= {
        "Not modeled", "Toss-up", "Lean D", "Lean R", "Likely D", "Likely R",
        "Very likely D", "Very likely R", "Solid D", "Solid R",
    }


def test_map_uses_leaflet_basemap_and_close_control():
    text, data = page_and_payload()
    css = (ROOT / "dashboard" / "forecast_dashboard.css").read_text(encoding="utf-8")
    for chamber in ("house", "senate"):
        assert all(p["geometry"]["type"] in {"Polygon", "MultiPolygon"} for p in data[chamber]["paths"])
    assert 'leaflet@1.9.4/dist/leaflet.css' in text
    assert 'leaflet@1.9.4/dist/leaflet.js' in text
    assert 'sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=' in text
    assert 'sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=' in text
    assert 'basemaps.cartocdn.com/light_all' in text
    assert 'OpenStreetMap' in text and 'CARTO' in text
    assert 'L.geoJSON(collection' in text
    assert 'class="close-detail"' in text
    assert 'aria-label="Close district and return to statewide map"' in text
    assert 'addEventListener("click",clearDistrict)' in text
    assert "#map{width:100%;height:610px" in css
    assert ".leaflet-interactive:hover" in css


def test_post2016_headline_contests_and_full_chamber_accounting_reconcile():
    _, data = page_and_payload()
    assert sum(r["status"] == "modeled" for c in ("house", "senate") for r in data[c]["races"]) == 48
    assert all(r["status"] != "unmodeled" for c in ("house", "senate") for r in data[c]["races"])
    roster = pd.read_csv(ROOT / "data" / "processed" / "war" / "2026_final_candidate_roster.csv")
    modeled = pd.read_csv(ROOT / "data" / "processed" / "forecast_calibration" / "alabama_war_forecast_v1_2026_modeled_seats.csv")
    for chamber in ("house", "senate"):
        dem = set(roster[(roster.chamber == chamber) & roster.party.eq("D")].district)
        rep = set(roster[(roster.chamber == chamber) & roster.party.eq("R")].district)
        fixed_dem = len(dem - rep)
        expected = modeled[modeled.chamber.eq(chamber)].set_index("dem_modeled_seats").probability
        actual = {row["demSeats"] - fixed_dem: row["probability"] for row in data[chamber]["modelSeatDistributions"]["headline"]}
        assert set(actual) == set(expected.index)
        for seats, probability in expected.items():
            assert abs(actual[seats] - probability) < 1e-12


def test_candidate_finance_is_display_only_not_model_input():
    text, data = page_and_payload()
    scenarios = pd.read_csv(
        ROOT / "data" / "processed" / "forecast_calibration"
        / "alabama_war_forecast_v1_2026_scenarios.csv"
    )
    assert scenarios.finance_used.eq(False).all()
    assert scenarios.fundraising_adjustment.eq(0).all()
    assert "not used by forecast" in text
    assert any(candidate["raised"] is not None for chamber in ("house", "senate") for race in data[chamber]["races"] for candidate in race["candidates"])


def test_methodology_has_no_legacy_forecast_claims():
    text = (ROOT / "docs" / "methodology.html").read_text(encoding="utf-8")
    headline_mae = selected_headline_mae()
    assert "64 contested 2018 races" in text
    assert (
        f"records {headline_mae:.2f} points of MAE"
        in text
    )
    assert "candidate_history_used=false" in text
    assert "Student-t" in text
    assert "50,000 correlated simulations" in text
    for legacy in (
        "Basic and Fundamentals+", "six-point normal", "20% of the CMO",
        "893 model-ready contests", "robust forecast build",
    ):
        assert legacy not in text
    assert "Dem and Rep scenario tabs" in text
