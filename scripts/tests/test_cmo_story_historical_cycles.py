import csv
import json
import re
from pathlib import Path

from build_war_story_page import (
    build_page,
    load_data,
    modernize_v6_copy,
    modernize_war_headline,
)


def _public_page(payload):
    return modernize_war_headline(modernize_v6_copy(build_page(payload)))


def _section(cycle, chamber):
    return {"cycle": cycle, "chamber": chamber, "summary": {"races": 1}}


def test_story_page_exposes_early_house_and_senate_cycles():
    payload = {
        f"{cycle}-{chamber}": _section(cycle, chamber)
        for cycle in (1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022)
        for chamber in ("house", "senate")
    }
    page = _public_page(payload)
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
    page = _public_page(payload)
    assert "<b>4</b><span>Map views</span>" in page
    assert 'id="scope-filter"' in page
    assert 'id="scope-filter" aria-label="Candidate result scope"' in page
    assert 'id="party-filter" aria-label="Candidate party"' in page
    assert 'id="outcome-filter" aria-label="Candidate outcome"' in page
    assert 'role="button" aria-label="Open ${x.candidate}' in page
    assert "All cycles and chambers" in page
    assert "WAR decomposition" in page
    assert "Unpooled quality residual" in page
    assert "Generic incumbency component" in page
    assert "Total electoral value" in page
    assert "Uncertainty interval" in page
    assert "Historical structural expectation" in page
    assert "Historical accuracy" in page
    assert "Structural expectation" in page
    assert "Residual-quality penalty" in page
    assert "Fundamentals+" not in page
    assert "Data and sources" in page
    assert "Data sources and attribution" in page
    assert "Alabama Secretary of State" in page
    assert "U.S. Census Bureau" in page
    assert "Voting and Election Science Team (VEST)" in page
    assert "Database on Ideology, Money in Politics, and Elections (DIME), Adam Bonica" in page
    assert "FollowTheMoney / National Institute on Money in Politics" in page
    assert "Shor–McCarty state legislative data" in page
    assert "Attribution boundary" in page
    assert "selectCandidate(" in page
    assert "Candidate WAR timeline" in page
    assert "career-observation" in page
    assert "historyMax=Math.max" in page
    assert "WAR is candidate-oriented" in page
    assert "Candidate Atlas" not in page
    assert ".distribution-label{position:absolute;top:17px;left:0;right:0" in page
    assert ".distribution>i{position:absolute" in page
    assert "@media(max-width:480px){.dashboard,.dashboard>*,.map-panel,.detail{min-width:0;max-width:100%}" in page
    assert ".racebox>table{width:100%;table-layout:fixed}" in page
    assert "districtStatus" in page
    assert '<button data-map-mode="quality" class="active">WAR</button>' in page
    assert '<button data-map-mode="absolute">CMO</button>' in page
    assert '<button data-map-mode="governor">Raw overperformance vs. governor</button>' in page
    assert '<button data-map-mode="presidential">Raw overperformance vs. previous presidential margin</button>' in page
    assert 'data-map-mode="relative"' not in page
    assert 'data-map-mode="within"' not in page
    assert 'data-map-mode="rawticket"' not in page
    assert "mapMode='quality'" in page
    assert "cap:30,low:'#d34b45'" in page
    assert "cap:20,low:'#a66a24',mid:'#f3efe5',high:'#267c78'" in page
    assert "Number(v)/c.cap" in page
    assert "Math.sqrt(Math.min(30,Math.abs(v))/30)" not in page
    assert "WAR differential on its own gold-to-teal scale" in page
    assert "square-root scale" not in page
    assert "linear-gradient(90deg,#d34b45 0%,#f2f1ed 50%,#3d77a8 100%)" in page
    assert "ticks:['R +30','R +15','Even','D +15','D +30']" in page
    assert "ticks:['R +20','R +10','Even','D +10','D +20']" in page
    assert "function candidateMetric(x)" in page
    assert "if(mapMode==='quality')return Number(x.partialPooled)" in page
    assert "function ordinal(value)" in page
    assert "${ordinal(percentile)} percentile" in page
    assert "function candidateHeadline(x)" in page
    assert "${candidateHeadline(x)}" in page
    assert "selectedParty=party" in page
    assert "renderMap();detail(currentSelectedCandidate())" in page
    assert "function clearSelection()" in page
    detail = page.index("function detail(x)")
    headline = page.index('<div class="candidate-headline">', detail)
    race_box = page.index("${raceBox(x)}", detail)
    assert headline < race_box
    assert "Candidate Quality Index" not in page
    assert "CQI" not in page
    assert "Split Ticket" in page


def test_hd32_2010_uses_corrected_democratic_previous_presidential_context():
    data = load_data()
    section = data["2010-house"]
    baseline = next(
        item for item in section["baselines"]["32"]
        if item["kind"] == "presidential"
    )
    assert baseline["label"] == "2008 President"
    assert baseline["demName"] == "Barack Obama"
    assert baseline["repName"] == "John McCain"
    assert baseline["demMargin"] == 24.05

    boyd = next(
        candidate for candidate in section["candidates"]
        if candidate["district"] == 32
        and candidate["candidate"] == "BARBARA BIGSBY BOYD"
    )
    assert boyd["priorPres"] == 24.05
    assert boyd["predictiveResidual"] == 18.69


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
