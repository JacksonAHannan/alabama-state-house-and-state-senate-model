import sqlite3

import pandas as pd


DB = "data/processed/elections/alabama_elections.sqlite"


def test_vtd_links_have_stable_unique_ids():
    links = pd.read_csv("data/processed/precinct_history/historical_precinct_vtd_links.csv")
    assert links.link_id.is_unique
    assert (links.relationship == "underflow_additional").sum() == 246


def test_block_links_are_unique_within_cycle():
    with sqlite3.connect(DB) as connection:
        total, distinct = connection.execute(
            "SELECT COUNT(*), COUNT(DISTINCT CAST(cycle AS TEXT) || '|' || block_geoid) "
            "FROM precinct_block_links").fetchone()
    assert total == distinct
    assert total > 600_000


def test_block_allocation_coverage_exceeds_98_percent():
    coverage = pd.read_csv(
        "data/processed/precinct_history/historical_precinct_block_link_coverage.csv")
    assert coverage.coverage.min() > 0.98
