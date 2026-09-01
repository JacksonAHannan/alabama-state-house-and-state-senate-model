from __future__ import annotations

import json
import re
from pathlib import Path


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
    assert sum(section["summary"]["races"] for section in payload.values()) == 509
    assert sum(len(section["candidates"]) for section in payload.values()) == 1_018
    assert 'id="map"' in html
    assert "function renderMap" in html


def test_historical_map_uses_residual_war_and_labels_backcasts() -> None:
    html, payload = page_payload()
    rows = [row for section in payload.values() for row in section["candidates"]]
    assert {row["scoringScope"] for row in rows} == {
        "post2016_southern_model_backcast", "published_same_cycle_residual",
    }
    assert all(row["war"] is not None for row in rows)
    assert all(row["rawGap"] is not None for row in rows)
    assert all(row["predictedStructuralGap"] is not None for row in rows)
    assert "Historical backcasts and published modern residuals are labeled separately" in html
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
    assert abs(row["war"] - 13.295433950839808) < 0.01
    assert row["scoringScope"] == "published_same_cycle_residual"
