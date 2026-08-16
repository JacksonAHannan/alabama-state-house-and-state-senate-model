import pandas as pd

from build_votehub_crosstab_source_inventory import discover_assets
from build_votehub_demographic_polling import pool, validate_reviewed


def test_asset_discovery_keeps_tabulation_documents():
    html = b'<a href="results.pdf">Full crosstabs</a><a href="story">News</a>'
    found = discover_assets("https://example.com/poll", html, "text/html")
    assert [x["asset_url"] for x in found] == ["https://example.com/results.pdf"]


def test_review_and_pool_exclude_partisan_poll():
    catalog = pd.DataFrame([
        {"id": "a", "pollster": "One", "end_date": "2026-08-01", "population": "lv",
         "sample_size": 1000, "internal": False, "partisan": None},
        {"id": "b", "pollster": "Two", "end_date": "2026-08-01", "population": "lv",
         "sample_size": 1000, "internal": False, "partisan": "DEM"},
    ])
    raw = pd.DataFrame([
        {"poll_id": "a", "dimension": "race", "group": "white", "dem_pct": 45,
         "rep_pct": 55, "source_url": "https://x", "reviewed": True},
        {"poll_id": "b", "dimension": "race", "group": "white", "dem_pct": 90,
         "rep_pct": 10, "source_url": "https://y", "reviewed": True},
    ])
    result = pool(validate_reviewed(raw, catalog)).iloc[0]
    assert result.dem_margin_two_party == -10
    assert result.pollsters == 1
