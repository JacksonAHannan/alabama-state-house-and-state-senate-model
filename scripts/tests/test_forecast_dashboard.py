import json
import re
from pathlib import Path

from bs4 import BeautifulSoup


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
    assert "Candidate and finance adjustments remain separate experimental scenarios" in text
    assert "View experimental candidate scenarios" in text
    assert "middle 80% of simulated outcomes" in text
    assert "Experimental uncertainty estimates" in text
    assert "full 1994–2022 archive and expanding-window holdouts from 1998 through 2022" in text
    assert "provisional rather than fully calibrated" in text


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
