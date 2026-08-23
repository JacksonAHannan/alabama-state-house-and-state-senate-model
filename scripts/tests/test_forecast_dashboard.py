import json
import re
from pathlib import Path

from bs4 import BeautifulSoup
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "artifacts" / "site" / "alabama-2026-legislative-forecast.html"


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


def test_dashboard_explains_headline_and_scenarios():
    text = PAGE.read_text(encoding="utf-8")
    assert "Headline" in text
    assert "Historical CMO is analyzed separately" in text
    assert "Student-t" in text
    assert "50,000 simulations" in text
    assert "Shared national, state, and chamber" in text
    assert "six-point normal calibration" not in text


def test_model_switcher_and_default_decomposition_are_complete():
    text, data = page_and_payload()
    assert data["meta"]["model"] == "headline"
    manifest = json.loads((ROOT / "data" / "processed" / "forecast_calibration" / "robust_forecast_v1_manifest.json").read_text(encoding="utf-8"))
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
    assert "Technical variable detail" in text
    assert "Data sources and freshness" in text
    assert "Finance scenario</th>" not in text
    assert "difference_from_headline" in text
    assert "URLSearchParams(location.search)" in text
    assert 'aria-controls="workspace"' in text


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


def test_live_probabilities_use_recent_southern_calibration():
    _, data = page_and_payload()
    hd21 = next(r for r in data["house"]["races"] if r["district"] == 21)
    headline = hd21["models"]["headline"]
    assert .02 < headline["demProbability"] < .023
    assert headline["high80"] - headline["low80"] < 18


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


def test_robust_v1_contests_and_full_chamber_accounting_reconcile():
    _, data = page_and_payload()
    assert sum(r["status"] == "modeled" for c in ("house", "senate") for r in data[c]["races"]) == 48
    assert all(r["status"] != "unmodeled" for c in ("house", "senate") for r in data[c]["races"])
    roster = pd.read_csv(ROOT / "data" / "processed" / "war" / "2026_final_candidate_roster.csv")
    modeled = pd.read_csv(ROOT / "data" / "processed" / "forecast_calibration" / "robust_forecast_v1_2026_modeled_seats.csv")
    for chamber in ("house", "senate"):
        dem = set(roster[(roster.chamber == chamber) & roster.party.eq("D")].district)
        rep = set(roster[(roster.chamber == chamber) & roster.party.eq("R")].district)
        fixed_dem = len(dem - rep)
        expected = modeled[modeled.chamber.eq(chamber)].set_index("dem_modeled_seats").probability
        actual = {row["demSeats"] - fixed_dem: row["probability"] for row in data[chamber]["modelSeatDistributions"]["headline"]}
        assert set(actual) == set(expected.index)
        for seats, probability in expected.items():
            assert abs(actual[seats] - probability) < 1e-12


def test_methodology_has_no_legacy_forecast_claims():
    text = (ROOT / "docs" / "methodology.html").read_text(encoding="utf-8")
    assert "893 model-ready contests" in text
    assert "Student-t" in text
    assert "50,000 simulations" in text
    for legacy in ("Basic and Fundamentals+", "six-point normal", "20% of the CMO"):
        assert legacy not in text
    assert "Historical CMO is not a forecast tab" in text
