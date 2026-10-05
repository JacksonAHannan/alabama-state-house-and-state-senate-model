from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "docs" / "cmo.html"


def page_payload() -> tuple[str, dict]:
    html = PAGE.read_text(encoding="utf-8")
    match = re.search(r"const DATA=(\{.*?\});\s*let active=", html, re.S)
    assert match is not None
    return html, json.loads(match.group(1))


def test_historical_map_restores_every_cycle_and_chamber() -> None:
    html, payload = page_payload()
    assert len(payload) == 16
    assert {section["cycle"] for section in payload.values()} == {
        1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022,
    }
    assert {section["chamber"] for section in payload.values()} == {"house", "senate"}
    # 504 races after the 1994 party-label repair; 1994 House 1 is withheld by adjudication
    # and appears only through the no-score panel, so 503 scored races are drawn.
    assert sum(section["summary"]["races"] for section in payload.values()) == 503
    assert sum(len(section["candidates"]) for section in payload.values()) == 1_006
    assert payload["1994-house"]["districtStatus"]["1"].startswith("Contested D–R race; WAR withheld")
    assert 'id="map"' in html
    assert "function renderMap" in html


def test_historical_map_uses_residual_war_and_labels_its_scoring_scope() -> None:
    html, payload = page_payload()
    rows = [row for section in payload.values() for row in section["candidates"]]
    assert {row["scoringScope"] for row in rows} == {
        "post2016_southern_model_backcast", "published_same_cycle_residual",
    }
    assert all(row["war"] is not None for row in rows)
    assert all(row["rawGap"] is not None for row in rows)
    assert all(row["predictedStructuralGap"] is not None for row in rows)
    assert "Pre-2016 cycles scored against the fixed reference model and published modern residuals are labeled separately" in html
    assert "One fixed reference model" in html
    # The schema keeps the backcast enum; reader-facing copy must not reuse the retired framing.
    assert "Modern-model backcast" not in html
    assert "No pooled candidate effect" in html
    assert "default view maps CMO" not in html
    assert "Direct CMO" not in html


def test_candidate_display_names_are_election_identities_not_committees() -> None:
    _, payload = page_payload()
    rows = [row for section in payload.values() for row in section["candidates"]]
    committee_like = re.compile(r"\b(?:committee|campaign|friends of|elect|pac)\b", re.I)
    assert not [row["candidate"] for row in rows if committee_like.search(row["candidate"])]
    assert all(row["identityStatus"] for row in rows)


def test_grimsley_2018_is_exact_published_race_residual() -> None:
    _, payload = page_payload()
    section = payload["2018-house"]
    row = next(item for item in section["candidates"] if item["candidate"] == "Dexter Grimsley")
    published = pd.read_csv(
        ROOT / "data/processed/war/alabama_war_v1/candidate_cycle_war.csv"
    )
    source = published[
        published.cycle.eq(2018)
        & published.chamber.eq("lower")
        & published.district.eq(85)
        & published.canonical_party.eq("D")
    ].squeeze()
    assert abs(row["war"] - source.candidate_cycle_war) < 1e-10
    assert row["scoringScope"] == "published_same_cycle_residual"


CANDIDATE = ROOT / "artifacts" / "site" / "alabama-legislative-cmo.html"


def candidate_parts() -> tuple[str, dict, dict]:
    import pytest

    if not CANDIDATE.exists():
        pytest.skip("local candidate not built")
    html = CANDIDATE.read_text(encoding="utf-8")
    payload = json.loads(re.search(r"const DATA=(\{.*?\});\s*let active=", html, re.S).group(1))
    geometry = json.loads(re.search(r"const GEOMETRY=(\{.*?\});const CONTEXT=", html, re.S).group(1))
    return html, payload, geometry


def test_candidate_draws_every_cycle_on_its_own_enacted_plan() -> None:
    html, payload, geometry = candidate_parts()
    assert len(payload) == 16 and 'id="map"' in html and "function renderMap" in html
    for key, section in payload.items():
        plan = geometry[section["plan"]]
        assert "paths" not in section
        assert set(plan["tiles"]) == set(plan["districts"])
        winners = {str(d) for d in section["winners"]}
        assert winners <= set(plan["districts"]), key
    assert payload["1994-house"]["plan"] == payload["1998-house"]["plan"] != payload["2002-house"]["plan"]


def test_candidate_uses_the_war_scale_and_no_remote_dependencies() -> None:
    html, _, _ = candidate_parts()
    for retired in ("#3d77a8", "#d34b45", "fonts.googleapis.com", "Libre Franklin", "leaflet"):
        assert retired not in html
    assert "--war-d3:" in html and "warColor" in html
    assert "Color shows which side ran ahead of expectation. It is not the district's partisan lean." in html
    assert "One fixed reference model" in html and "No pooled candidate effect" in html
    assert "Pre-2016 cycles scored against the fixed reference model and published modern residuals are labeled separately" in html
    assert "The public forecast sets candidate-specific residual WAR to zero" not in (
        CANDIDATE.parent / "cmo-methodology.html").read_text(encoding="utf-8")


def test_candidate_career_chart_displays_title_case_names() -> None:
    html, _, _ = candidate_parts()
    career = html[html.index('<section class="career"'):html.index("</section>", html.index('<section class="career"'))]
    names = re.findall(r'<text x="0" y="\d+" font-size="13" font-weight="700" fill="var\(--ink\)">([^<]+?) <tspan', career)
    assert names and not [n for n in names if n.isupper() and len(n) > 3]
    assert "<details" in career and "<table" in career
