import json

import pytest
import re
from pathlib import Path

from bs4 import BeautifulSoup
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "artifacts" / "site" / "alabama-2026-legislative-forecast.html"
CAL = ROOT / "data" / "processed" / "forecast_calibration"


def test_forecast_template_distinguishes_structural_and_candidate_adjustments():
    from build_2026_forecast_dashboard import HTML

    soup = BeautifulSoup(HTML, "html.parser")
    explanation = soup.select_one("section.method").get_text(" ", strip=True)
    assert "includes the owner-selected structural adjustment" in explanation
    assert "symmetric incumbency effect" in explanation
    assert "advisory limitation" in explanation
    # Candidate history is now an input, and the page must say who it applies to.
    assert "carry a share of their own WAR forward" in explanation
    assert "everyone else is evaluated generically" in explanation
    assert "fixed at zero" not in explanation


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


def forward_train_races() -> int:
    manifest = json.loads(
        (CAL / "alabama_war_forecast_v1_manifest.json").read_text(encoding="utf-8")
    )
    metrics = pd.read_csv(CAL / "alabama_war_forecast_v1_forward_metrics.csv")
    selected = metrics.loc[
        metrics.specification.eq(manifest["selected_specification"]), "train_races"
    ]
    assert len(selected) == 1
    return int(selected.iloc[0])


def test_dashboard_contains_both_chambers_and_shared_design_tokens():
    text, data = page_and_payload()
    # One token system, no remote font or tile dependency.
    assert "--rating-solid-d:" in text and "--war-d3:" in text
    assert "fonts.googleapis.com" not in text
    assert len(data["house"]["races"]) == 105
    assert len(data["senate"]["races"]) == 35
    assert data["house"]["seatDistribution"]
    assert data["senate"]["seatDistribution"]


def test_dashboard_has_accessible_controls_and_fallbacks():
    soup = BeautifulSoup(PAGE.read_text(encoding="utf-8"), "html.parser")
    assert soup.select_one("#detail[aria-live='polite']")
    assert soup.select_one("#map")
    assert soup.select_one("button[data-chamber='house'][aria-pressed]")
    assert soup.select_one("button[data-mode='probability'][aria-pressed]")
    assert soup.select_one("button[data-view='tiles'][aria-pressed]")
    finder = soup.select_one("#districtSearch[role='combobox'][aria-controls='districtOptions']")
    assert finder and soup.select_one("label[for='districtSearch']")
    assert soup.select_one("#districtOptions[role='listbox']")
    assert soup.select_one("#download")
    text = PAGE.read_text(encoding="utf-8")
    # The shared map renders one keyboard tab stop with arrow-key movement.
    assert 'role: "group"' in text and 'role: "button"' in text and "ArrowRight" in text


def test_scenario_tab_arrow_navigation_restores_focus_after_rerender():
    text = PAGE.read_text(encoding="utf-8")
    assert 'selectModel(tabs[n].dataset.model);requestAnimationFrame' in text
    assert 'document.querySelector(`[data-model="${state.model}"]`)?.focus()' in text


def test_dashboard_explains_headline_and_scenarios():
    text = PAGE.read_text(encoding="utf-8")
    assert "Headline" in text
    assert "Dem scenario" in text
    assert "Rep scenario" in text
    assert "each nominee\u2019s own demonstrated WAR where they have run before" in text
    assert "Fundraising is not a forecast input" in text
    assert "Student-t" in text
    assert "50,000 simulations" in text
    assert "Shared national, statewide, and chamber" in text
    assert "six-point normal calibration" not in text
    assert "trained on 2018 and tested on 2022" not in text
    assert (
        "after training on eligible post-2016 Southern races before 2022 "
        f"({forward_train_races():,} training races)" in text
    )
    assert "variableLabels" not in text
    assert "variableGroups" not in text


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
    # The copy must match the model: candidate history is carried forward where matched.
    assert "carried-forward candidate WAR applies only where a nominee has a matched prior Alabama race" in text
    assert "Candidate WAR, history, ideology, and fundraising are not used" not in text
    for chamber in ("house", "senate"):
        for race in (row for row in data[chamber]["races"] if row["status"] == "modeled"):
            for model in data["models"]:
                values = race["models"][model["id"]]
                assert abs(values["steps"][-1][2] - values["margin"]) < 1e-8


def test_candidate_war_timelines_match_source_and_state_their_role():
    text, data = page_and_payload()
    candidates = [candidate for chamber in ("house", "senate") for race in data[chamber]["races"] for candidate in race["candidates"]]
    with_history = [candidate for candidate in candidates if candidate["warHistory"]]
    assert with_history
    assert "carries part of this nominee's most recent matched result forward" in text
    assert "does not use prior WAR" not in text
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
    text = PAGE.read_text(encoding="utf-8")
    # Republican margins sit left of even and Democratic margins right, in every margin chart.
    assert '← ${narrow?"R":"Republican"} favored' in text and '${narrow?"D":"Democratic"} favored →' in text
    assert "x=v=>4+112*(Math.max(-B,Math.min(B,v))+B)/(2*B)" in text


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
    assert 'state.chamber=c;state.selected=null;' in text
    assert 'function updateMapViewport()' in text
    assert 'siteMap.select(String(state.selected))' in text
    assert 'siteMap.select(null,{zoom:!state.area})' in text
    assert '["Statewide",...metros]' in text
    assert 'clearDistrict(true)' in text
    assert 'Select a district' in text


def test_map_colors_follow_current_probability_and_rating_bands():
    text = PAGE.read_text(encoding="utf-8")
    assert 'const RATING_COLORS=' in text
    assert 'const probabilityColor=p=>RATING_COLORS[ratingForProbability(p)]' in text
    assert 'if(state.mode==="probability") return probabilityColor(r.demProbability)' in text
    assert 'return marginColor(r.margin)' in text
    assert 'r.demProbability*200-100' not in text


def test_rating_thresholds_match_published_probability_bands():
    text, data = page_and_payload()
    assert 'q<.60?"Toss-up":q<.80?`Lean ${lead}`:q<.95?`Likely ${lead}`:q<.98?`Very likely ${lead}`:`Solid ${lead}`' in text
    assert "Very likely D" in text
    assert "Very likely R" in text
    # The legend prints each band's cut-off with no gaps between bands.
    assert '["Very likely D","95–98%"]' in text
    assert '["Toss-up","under 60% for either party"]' in text
    assert '["Solid D","98% or more"]' in text
    ratings = {r["rating"] for chamber in ("house", "senate") for r in data[chamber]["races"]}
    assert ratings <= {
        "Not modeled", "Toss-up", "Lean D", "Lean R", "Likely D", "Likely R",
        "Very likely D", "Very likely R", "Solid D", "Solid R",
    }


def test_map_is_self_hosted_svg_with_tiles_and_close_control():
    text, data = page_and_payload()
    for remote in ("leaflet", "cartocdn", "unpkg.com", "fonts.googleapis.com"):
        assert remote not in text
    assert data["context"]["counties"].startswith("M")
    assert {city["name"] for city in data["context"]["cities"]} >= {"Birmingham", "Huntsville", "Montgomery", "Mobile"}
    for chamber, total in (("house", 105), ("senate", 35)):
        geometry = data[chamber]["geometry"]
        assert len(geometry["districts"]) == total
        assert set(geometry["tiles"]) == set(geometry["districts"])
        assert len({tuple(xy) for xy in geometry["tiles"].values()}) == total
        assert all(d["path"].startswith("M") and len(d["label"]) == 2 for d in geometry["districts"].values())
        assert {m["name"] for m in geometry["metroMembers"]} == {"Birmingham", "Huntsville", "Montgomery", "Mobile"}
    assert 'class="close-detail"' in text
    assert 'aria-label="Close district and return to statewide map"' in text
    assert 'addEventListener("click",()=>clearDistrict(true))' in text


def test_outcome_dots_reproduce_the_published_interval_and_probability():
    _, data = page_and_payload()
    offsets = data["meta"]["outcomeOffsets"]
    assert len(offsets) == 100 and offsets == sorted(offsets)
    races = [r for c in ("house", "senate") for r in data[c]["races"] if r["status"] == "modeled"]
    for race in races:
        headline = race["models"]["headline"]
        dots = [headline["margin"] + o for o in offsets]
        # The 10th and 90th of 100 equally likely outcomes bracket the published 80% interval.
        assert dots[9] <= headline["low80"] + 0.5 and dots[10] >= headline["low80"] - 0.5
        assert dots[89] <= headline["high80"] + 0.5 and dots[90] >= headline["high80"] - 0.5
        assert abs(sum(d > 0 for d in dots) / 100 - headline["demProbability"]) <= 0.011


def test_seat_history_is_explicit_about_unknown_seats():
    _, data = page_and_payload()
    history = data["seatHistory"]
    assert history["runId"].startswith("AL-SEATS-V1-")
    for chamber, size in (("house", 105), ("senate", 35)):
        rows = history["chambers"][chamber]
        assert [r["cycle"] for r in rows] == [1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022]
        for row in rows:
            assert row["D"] + row["R"] + row["other"] + row["unknown"] == size == row["seats"]
    # Unknown seats come only from the seats product's own `unknown` winner status, never imputed;
    # the 1994 conflicts were resolved by the 2026-10-04 party-label repair, not by the page.
    winners = pd.read_csv(ROOT / "data/processed/elections/alabama_seats_by_cycle_v1/district_winners.csv")
    unknown = winners[winners.winner_status.eq("unknown")].groupby(["cycle", "chamber"]).size()
    for chamber in ("house", "senate"):
        for row in history["chambers"][chamber]:
            assert row["unknown"] == int(unknown.get((row["cycle"], chamber), 0))


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
    assert "not used by forecast" in text
    assert any(candidate["raised"] is not None for chamber in ("house", "senate") for race in data[chamber]["races"] for candidate in race["candidates"])


def test_methodology_has_no_legacy_forecast_claims():
    text = (ROOT / "docs" / "methodology.html").read_text(encoding="utf-8")
    headline_mae = selected_headline_mae()
    assert "eligible Southern races after 2016 and before 2022" in text
    assert "WAR model's incumbency term" in text
    assert f"records {headline_mae:.2f} points" in text
    assert "carried-forward candidate WAR" in text
    assert "Student-t" in text
    assert "50,000 correlated simulations" in text
    for legacy in (
        "Basic and Fundamentals+", "six-point normal", "20% of the CMO",
        "893 model-ready contests", "robust forecast build",
    ):
        assert legacy not in text
    assert "Dem and Rep scenario tabs" in text
