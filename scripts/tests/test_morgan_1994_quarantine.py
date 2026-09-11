"""Quarantine evidence for the unresolved fractional 1994 Morgan source cell.

`warehouse-06` retains the reported 144.4 Attorney General value at row 48,
column 11 of the `Morgan` sheet in `94g-prec/MORGAN.XLS` (provider precinct
`26001`, `SRC-E64FFC4299ED54CB2D3A`). The value is never rounded, nulled or
substituted; the 1994 source slice refuses to aggregate it. This module pins,
against the live read-only warehouse, that the cell is the only fractional
observation, that the advisory quality view flags it and no view excludes it,
and that the 1994 baseline boundary refuses it before any read or write. It
also proves the quarantine is about the fraction only: an integer in the same
slot is accepted.

Evidence and disposition: `project_docs/audits/`
`MORGAN_1994_FRACTIONAL_CELL_QUARANTINE_2026_09_10.md`.
"""
import sqlite3

import pytest

import build_1994_cmo_baseline as baseline
from warehouse import ROOT

DATABASE = ROOT / "data" / "processed" / "elections" / "alabama_elections.sqlite"

# The recorded observation, as stored. Rowid is deliberately not asserted: a
# source-layer rewrite may reassign it while the observation itself persists.
CELL = {
    "source": "alabama_sos", "year": 1994, "county_key": "MORGAN", "precinct_key": "26001",
    "office": "Attorney General", "candidate_key": "SESSIONS", "party_norm": "R",
    "votes": 144.4, "source_file": "94g-prec/MORGAN.XLS", "source_sheet": "Morgan",
    "source_row": 48, "source_column": 11, "source_file_id": "SRC-E64FFC4299ED54CB2D3A",
}
COLUMNS = ["source", "year", "county_key", "precinct_key", "office", "candidate_key",
           "party_norm", "votes", "source_file", "source_sheet", "source_row",
           "source_column", "source_file_id"]
WHERE = ("source='alabama_sos' AND year=1994 AND county_key='MORGAN' "
         "AND precinct_key='26001' AND office='Attorney General'")
# The precinct reports both Attorney General candidates; the quarantined cell is
# the Sessions (AG2/R) column at row 48.
CELL_WHERE = f"{WHERE} AND candidate_key='SESSIONS' AND source_column=11"


def _query(connection, sql, params=()):
    rows = connection.execute(sql, params).fetchall()
    return [dict(zip(COLUMNS, row)) for row in rows]


@pytest.fixture
def warehouse():
    connection = sqlite3.connect(f"file:{DATABASE}?mode=ro", uri=True)
    connection.execute("PRAGMA query_only=ON")
    yield connection
    connection.close()


@pytest.fixture
def source_db(tmp_path):
    """Minimal 1994 source database holding only the recorded cell."""
    path = tmp_path / "source.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute("""CREATE TABLE vote_observations (
            source TEXT, year INTEGER, county_key TEXT, precinct_key TEXT, office TEXT,
            district TEXT, candidate_key TEXT, party_norm TEXT, votes, source_file TEXT,
            source_sheet TEXT, source_row INTEGER, source_column INTEGER)""")
        connection.execute("""INSERT INTO vote_observations
            (source,year,county_key,precinct_key,office,candidate_key,party_norm,votes,
             source_file,source_sheet,source_row,source_column)
            VALUES ('alabama_sos',1994,'MORGAN','26001','Attorney General','SESSIONS','R',?,
                    '94g-prec/MORGAN.XLS','Morgan',48,11)""", (CELL["votes"],))
        connection.execute("""CREATE TABLE canonical_candidates
            (year INTEGER, chamber TEXT, district INTEGER, canonical_party TEXT,
             canonical_votes REAL)""")
    return path


def test_one_fractional_observation_is_retained_with_its_physical_locator(warehouse):
    fractional = _query(warehouse, f"SELECT {','.join(COLUMNS)} FROM vote_observations "
                                   "WHERE votes <> CAST(votes AS INTEGER)")
    assert fractional == [CELL]


def test_quality_view_flags_the_cell_and_no_view_excludes_it(warehouse):
    flagged = warehouse.execute(
        "SELECT source,year,county_key,precinct_key,office,candidate_key,issue "
        "FROM qa_vote_observation_quality WHERE issue='fractional_source_vote'").fetchall()
    assert flagged == [(CELL["source"], CELL["year"], CELL["county_key"], CELL["precinct_key"],
                        CELL["office"], CELL["candidate_key"], "fractional_source_vote")]
    canonical = _query(warehouse, f"SELECT {','.join(COLUMNS)} FROM canonical_vote_observations "
                                  f"WHERE {CELL_WHERE}")
    # The authoritative view retains the reported value rather than dropping it.
    assert canonical == [CELL]


def test_live_1994_baseline_refuses_before_reading_or_changing_the_source(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Downstream read reached before the 1994 source refusal")

    monkeypatch.setattr(baseline.pd, "read_sql_query", forbidden)
    with pytest.raises(ValueError, match="fractional_source_vote") as error:
        baseline.load_returns()
    message = str(error.value)
    for fragment in ('"votes": 144.4', '"source_file": "94g-prec/MORGAN.XLS"',
                     '"source_sheet": "Morgan"', '"source_row": 48', '"source_column": 11',
                     '"precinct_key": "26001"'):
        assert fragment in message
    with sqlite3.connect(f"file:{DATABASE}?mode=ro", uri=True) as connection:
        assert connection.execute(
            f"SELECT votes FROM vote_observations WHERE {CELL_WHERE}").fetchall() == [(144.4,)]


@pytest.mark.parametrize("votes", [144, 0])
def test_integer_reported_count_in_the_same_slot_clears_the_refusal(
        source_db, monkeypatch, votes):
    with sqlite3.connect(source_db) as connection:
        connection.execute("UPDATE vote_observations SET votes=?", (votes,))
    monkeypatch.setattr(baseline, "ELECTION_DB", source_db)
    legislative, statewide, candidates = baseline.load_returns()
    assert legislative.empty and candidates.empty
    assert statewide.votes.tolist() == [float(votes)]
