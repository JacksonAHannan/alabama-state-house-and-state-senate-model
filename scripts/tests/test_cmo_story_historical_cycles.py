import json
import re

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
