import csv
import json
import re
from pathlib import Path

from build_war_story_page import build_page


def _section(cycle, chamber):
    return {"cycle": cycle, "chamber": chamber, "summary": {"races": 1}}


def test_story_page_exposes_early_house_and_senate_cycles():
    payload = {
        f"{cycle}-{chamber}": _section(cycle, chamber)
        for cycle in (1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022)
        for chamber in ("house", "senate")
    }
    page = build_page(payload)
    assert "Early historical · 1994–2006" in page
    assert "<b>8</b><span>Historical cycles</span>" in page
    encoded = re.search(r"const DATA=(\{.*?\});\n", page, re.S)
    assert encoded
    data = json.loads(encoded.group(1))
    for cycle in (1994, 1998, 2002, 2006):
        assert f"{cycle}-house" in data
        assert f"{cycle}-senate" in data


def test_story_page_publishes_transparency_and_exploration_controls():
    payload = {
        "2010-house": _section(2010, "house"),
        "2022-senate": _section(2022, "senate"),
    }
    page = build_page(payload)
    assert "<b>4</b><span>Distinct estimands</span>" in page
    assert 'id="scope-filter"' in page
    assert "All cycles and chambers" in page
    assert "Context CMO" in page
    assert "Within-cycle" in page
    assert "Raw ticket" in page
    assert "Predictive residual" in page
    assert "Partial-pooled" in page
    assert "Specification/data-quality band" in page
    assert "Diagnostics" in page
    assert "Cycle-balanced error" in page
    assert "Construct-validity checks" in page
    assert "Fundamentals+" not in page
    assert "Data and provenance" in page
    assert "Data sources and attribution" in page
    assert "Alabama Secretary of State" in page
    assert "U.S. Census Bureau" in page
    assert "Voting and Election Science Team (VEST)" in page
    assert "Database on Ideology, Money in Politics, and Elections (DIME), Adam Bonica" in page
    assert "FollowTheMoney / National Institute on Money in Politics" in page
    assert "Shor–McCarty state legislative data" in page
    assert "Attribution boundary" in page
    assert "selectCandidate(" in page
    assert "districtStatus" in page


def test_canonical_office_export_covers_every_story_cycle_and_chamber():
    path = Path(__file__).parents[2] / "data" / "processed" / "elections" / "canonical_cmo_district_office_baselines.csv"
    with path.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    coverage = {}
    for row in rows:
        if row.get("office_margin") in (None, ""):
            continue
        key = (int(row["cycle"]), row["chamber"], int(float(row["district"])))
        coverage.setdefault(key, set()).add(row["office"])
    for cycle in (1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022):
        for chamber in ("house", "senate"):
            districts = [offices for (year, body, _), offices in coverage.items()
                         if (year, body) == (cycle, chamber)]
            assert districts
            assert all({"Governor", "Attorney General"} <= offices for offices in districts)
