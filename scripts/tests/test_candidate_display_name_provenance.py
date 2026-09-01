from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / "data/processed/elections/alabama_elections.sqlite"


def test_finance_provider_committee_names_never_become_candidate_display_names() -> None:
    with sqlite3.connect(DATABASE) as connection:
        provider_committee_rows = connection.execute("""
            SELECT count(*) FROM source_southern_candidate_cycle_finance
            WHERE lower(coalesce(provider_candidate_name,'')) LIKE '%committee%'
               OR lower(coalesce(provider_candidate_name,'')) LIKE '%campaign%'
               OR lower(coalesce(provider_candidate_name,'')) LIKE '%friends of%'
        """).fetchone()[0]
        canonical_leaks = connection.execute("""
            SELECT count(*) FROM source_southern_candidate_cycle_finance
            WHERE lower(coalesce(candidate_name,'')) LIKE '%committee%'
               OR lower(coalesce(candidate_name,'')) LIKE '%campaign%'
               OR lower(coalesce(candidate_name,'')) LIKE '%friends of%'
        """).fetchone()[0]
        mart_leaks = connection.execute("""
            SELECT count(*) FROM mart_southern_candidate_cycle_finance
            WHERE lower(coalesce(candidate_name,'')) LIKE '%committee%'
               OR lower(coalesce(candidate_name,'')) LIKE '%campaign%'
               OR lower(coalesce(candidate_name,'')) LIKE '%friends of%'
        """).fetchone()[0]
    assert provider_committee_rows > 0
    assert canonical_leaks == 0
    assert mart_leaks == 0
