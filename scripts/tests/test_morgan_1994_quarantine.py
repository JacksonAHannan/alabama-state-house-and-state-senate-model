"""The adjudicated 1994 Morgan Attorney General cell, and the guard that found it.

`warehouse-06` quarantined a reported 144.4 Attorney General value at row 48,
column 11 of the `Morgan` sheet in `94g-prec/MORGAN.XLS` (provider precinct
`26001`, `SRC-E64FFC4299ED54CB2D3A`). The owner adjudicated it on 2026-09-10 to
the reported integer count 144, recorded as `ADJ-1994-MORGAN-26001-AG2-K48`.

This module pins the settled state against the live read-only warehouse - the
adjudicated value, its adjudication record, and that no fractional observation
survives anywhere - and pins, against a synthetic source, that the 1994 boundary
still refuses a fractional cell before reading or changing anything. The guard
is what surfaced this defect; retiring it with the defect would be a regression.

Evidence: `project_docs/audits/MORGAN_1994_FRACTIONAL_CELL_QUARANTINE_2026_09_10.md`,
`MORGAN_1994_ADJUDICATION_2026_09_10.md`, `MORGAN_1994_ADJUDICATION_REVIEW_2026_09_10.md`.
"""
import sqlite3

import pytest

import build_1994_cmo_baseline as baseline
from warehouse import ROOT

DATABASE = ROOT / "data" / "processed" / "elections" / "alabama_elections.sqlite"

ADJUDICATION_ID = "ADJ-1994-MORGAN-26001-AG2-K48"
REPORTED_VALUE = 144.4
ADJUDICATED_VALUE = 144.0
CELL = {
    "source": "alabama_sos", "year": 1994, "county_key": "MORGAN", "precinct_key": "26001",
    "office": "Attorney General", "candidate_key": "SESSIONS", "party_norm": "R",
    "votes": ADJUDICATED_VALUE, "source_file": "94g-prec/MORGAN.XLS", "source_sheet": "Morgan",
    "source_row": 48, "source_column": 11, "source_file_id": "SRC-E64FFC4299ED54CB2D3A",
}
COLUMNS = ["source", "year", "county_key", "precinct_key", "office", "candidate_key",
           "party_norm", "votes", "source_file", "source_sheet", "source_row",
           "source_column", "source_file_id"]
WHERE = ("source='alabama_sos' AND year=1994 AND county_key='MORGAN' "
         "AND precinct_key='26001' AND office='Attorney General'")
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
    """Minimal 1994 source database holding only the cell, as originally reported."""
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
                    '94g-prec/MORGAN.XLS','Morgan',48,11)""", (REPORTED_VALUE,))
        connection.execute("""CREATE TABLE canonical_candidates
            (year INTEGER, chamber TEXT, district INTEGER, canonical_party TEXT,
             canonical_votes REAL)""")
    return path


def test_the_cell_holds_the_adjudicated_count_in_its_recorded_slot(warehouse):
    stored = _query(warehouse, f"SELECT {','.join(COLUMNS)} FROM vote_observations "
                               f"WHERE {CELL_WHERE}")
    assert stored == [CELL]
    canonical = _query(warehouse, f"SELECT {','.join(COLUMNS)} FROM canonical_vote_observations "
                                  f"WHERE {CELL_WHERE}")
    assert canonical == [CELL]


def test_the_adjudication_is_recorded_with_evidence_and_review(warehouse):
    row = warehouse.execute(
        "SELECT decision, rationale, evidence_locator, review_status, subject_id "
        "FROM warehouse_manual_adjudication WHERE adjudication_id=?",
        (ADJUDICATION_ID,)).fetchone()
    assert row is not None, "the correction must not exist without its adjudication record"
    decision, rationale, evidence, review, subject = row
    assert decision == "reported_count=144"
    assert "SRC-E64FFC4299ED54CB2D3A" in subject and "R48C11" in subject
    assert str(REPORTED_VALUE) in rationale
    assert "MORGAN_1994_FRACTIONAL_CELL_QUARANTINE_2026_09_10" in evidence
    assert review


def test_no_fractional_vote_observation_survives(warehouse):
    assert _query(warehouse, f"SELECT {','.join(COLUMNS)} FROM vote_observations "
                             "WHERE votes <> CAST(votes AS INTEGER)") == []
    assert warehouse.execute(
        "SELECT count(*) FROM qa_vote_observation_quality "
        "WHERE issue='fractional_source_vote'").fetchone() == (0,)


def test_the_1994_boundary_still_refuses_a_fractional_cell(source_db, monkeypatch):
    """The guard that surfaced this defect must survive its repair."""
    def forbidden(*args, **kwargs):
        pytest.fail("Downstream read reached before the 1994 source refusal")

    monkeypatch.setattr(baseline, "ELECTION_DB", source_db)
    monkeypatch.setattr(baseline.pd, "read_sql_query", forbidden)
    with pytest.raises(ValueError, match="fractional_source_vote") as error:
        baseline.load_returns()
    message = str(error.value)
    for fragment in ('"votes": 144.4', '"source_file": "94g-prec/MORGAN.XLS"',
                     '"source_sheet": "Morgan"', '"source_row": 48', '"source_column": 11',
                     '"precinct_key": "26001"'):
        assert fragment in message


def test_the_live_1994_baseline_now_loads(monkeypatch):
    legislative, statewide, candidates = baseline.load_returns()
    assert not statewide.empty
    assert (statewide.votes == statewide.votes.astype(int)).all()


@pytest.mark.parametrize("votes", [144, 0])
def test_integer_reported_count_in_the_same_slot_clears_the_refusal(
        source_db, monkeypatch, votes):
    with sqlite3.connect(source_db) as connection:
        connection.execute("UPDATE vote_observations SET votes=?", (votes,))
    monkeypatch.setattr(baseline, "ELECTION_DB", source_db)
    legislative, statewide, candidates = baseline.load_returns()
    assert legislative.empty and candidates.empty
    assert statewide.votes.tolist() == [float(votes)]
