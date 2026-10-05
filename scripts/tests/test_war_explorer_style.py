"""Both WAR explorers share one presentation layer and one WAR color scale."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_war_pages_share_the_explorer_styles_and_the_map_component():
    story = (ROOT / "scripts/build_war_story_page.py").read_text(encoding="utf-8")
    southern = (ROOT / "scripts/build_southern_war_map.py").read_text(encoding="utf-8")
    for builder in (story, southern):
        assert "dashboard/site_components.css" in builder
        assert "dashboard/site_map.js" in builder
    assert "dashboard/war_explorer.css" in story and "war_explorer.css" in southern


def test_war_explorer_styles_use_tokens_not_remote_fonts_or_party_fills():
    css = (ROOT / "dashboard/war_explorer.css").read_text(encoding="utf-8")
    assert "fonts.googleapis.com" not in css
    # Map, legend and chart colors come from the WAR tokens via the page scripts.
    script = (ROOT / "dashboard/war_explorer.js").read_text(encoding="utf-8")
    assert "'--war-r3'" in script and "'--war-d3'" in script and "var(--war-r2)" in css
    tokens = (ROOT / "dashboard/site_components.css").read_text(encoding="utf-8")
    war = [line for line in tokens.split(";") if line.strip().startswith("--war-")]
    assert war and not any("#2878b5" in item or "#c93f49" in item for item in war)
