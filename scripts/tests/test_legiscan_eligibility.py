"""Synthetic source-integrity checks; never run an analytical build."""
import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
def source(tmp_path, monkeypatch):
    path = tmp_path / "source.sqlite"
    with sqlite3.connect(path) as con:
        con.executescript("""
        CREATE TABLE source_legiscan_roll_call(
          roll_call_id INTEGER, bill_id INTEGER, session_year INTEGER,
          chamber TEXT, vote_date TEXT, vote_description TEXT,
          yea INTEGER, nay INTEGER, not_voting INTEGER, absent INTEGER,
          total INTEGER, source_file_id TEXT, source_member TEXT);
        CREATE TABLE source_legiscan_member_vote(
          roll_call_id INTEGER, people_id INTEGER, session_year INTEGER,
          chamber TEXT, vote_id INTEGER, vote TEXT);
        CREATE TABLE source_legiscan_bill(bill_id INTEGER, bill_number TEXT,title TEXT,description TEXT);
        INSERT INTO source_legiscan_bill VALUES(1,'HB1','Fixture','Synthetic source');
        CREATE TABLE source_legiscan_legislator_session(
          session_year INTEGER,people_id INTEGER,name TEXT,normalized_name TEXT,
          party TEXT,role TEXT,district TEXT);
        INSERT INTO source_legiscan_legislator_session VALUES
          (2020,11,'Fixture A','FIXTURE A','unknown','Rep','1'),
          (2020,12,'Fixture B','FIXTURE B','unknown','Rep','2');
        INSERT INTO source_legiscan_roll_call VALUES
          (1,1,2020,'house','2020-01-01','Recorded vote',1,1,0,0,2,'fixture','1.json'),
          (2,1,2020,'house','2020-01-01','Recorded vote',2,0,0,0,2,'fixture','2.json'),
          (3,1,2020,'house','2020-01-01','Recorded vote',1,0,0,0,2,'fixture','3.json');
        INSERT INTO source_legiscan_member_vote VALUES
          (1,11,2020,'house',1,'Yea'),(1,12,2020,'house',2,'Nay'),
          (2,11,2020,'house',1,'Yea'),(2,12,2020,'house',2,'Nay'),
          (3,11,2020,'house',1,'Yea'),(3,12,2020,'house',9,'Unknown');
        """)
        con.executescript((Path(__file__).parents[1] / "warehouse_legislative_quality.sql").read_text())
    monkeypatch.setenv("ALABAMA_WAREHOUSE_PATH", str(path))
    return path


def test_canonical_readers_exclude_category_conflicts_and_unknown_codes(source):
    from scripts.legiscan_eligibility import read_member_votes, read_roll_calls
    votes = read_member_votes()
    assert list(votes.vote) == ['Yea', 'Nay']
    assert set(votes.roll_call_id) == {1}
    assert set(read_roll_calls().roll_call_id) == {1}
    with sqlite3.connect(source) as con:
        assert con.execute('SELECT count(*) FROM source_legiscan_member_vote').fetchone()[0] == 6


def test_preparation_retains_full_qa_but_only_canonical_vote_contents(source, monkeypatch):
    from scripts import build_alabama_legislative_ideology as preparation
    monkeypatch.setattr(preparation, 'MINORITY_MIN', 1)
    votes, qa = preparation.prepare_votes()  # Eligibility only; no model/scoring function.
    assert set(qa.roll_call_id) == {1, 2, 3}
    assert qa.reported_total_matches.eq(1).all()
    assert set(qa.loc[qa.eligible_ideal_point, 'roll_call_id']) == {1}
    assert set(votes.roll_call_id) == {1}
    assert list(votes.vote) == ['Yea', 'Nay']


def test_stale_approved_queue_cannot_restore_rejected_or_missing_ids(source):
    import pandas as pd
    from scripts.legiscan_eligibility import read_member_votes, read_roll_calls
    queue = pd.DataFrame({'roll_call_id': [1, 2, 3, 999], 'review_status': ['reviewed'] * 4})
    accepted = queue[queue.roll_call_id.isin(read_roll_calls().roll_call_id)]
    observations = accepted.merge(read_member_votes(), on='roll_call_id', validate='one_to_many')
    assert set(observations.roll_call_id) == {1}
    assert list(observations.vote) == ['Yea', 'Nay']


@pytest.fixture
def standalone(tmp_path):
    path = tmp_path / 'standalone.sqlite'
    with sqlite3.connect(path) as con:
        con.executescript("""
        CREATE TABLE rollcall(canonical_rollcall_id TEXT, session_year INTEGER,
          chamber TEXT,vote_date TEXT,vote_description TEXT,yea_total INTEGER,nay_total INTEGER,bill_number TEXT);
        CREATE TABLE member_vote(canonical_rollcall_id TEXT,session_year INTEGER,
          chamber TEXT,member_source_id TEXT,vote TEXT);
        INSERT INTO rollcall VALUES('LS-1',2020,'house','2020-01-01','Recorded vote',1,1,'HB1');
        INSERT INTO member_vote VALUES
          ('LS-1',2020,'house','LEGISCAN-11','Yea'),
          ('LS-1',2020,'house','LEGISCAN-12','Nay');
        """)
    return path


def test_same_snapshot_is_read_only(source, standalone):
    from scripts.legiscan_eligibility import checked_standalone
    with checked_standalone(standalone) as con:
        assert con.execute('SELECT count(*) FROM member_vote').fetchone()[0] == 2
        with pytest.raises(sqlite3.OperationalError):
            con.execute("DELETE FROM member_vote")


@pytest.mark.parametrize('mutation', [
    "UPDATE member_vote SET vote='Nay' WHERE member_source_id='LEGISCAN-11'",
    "INSERT INTO member_vote VALUES('LS-1',2020,'house','LEGISCAN-99','Yea')",
    "INSERT INTO rollcall VALUES('LS-2',2020,'house','2020-01-01','Recorded vote',2,0,'HB1')",
    "UPDATE rollcall SET yea_total=2",
    "DELETE FROM member_vote WHERE member_source_id='LEGISCAN-12'",
    "UPDATE rollcall SET bill_number='HB999'",
])
def test_stale_snapshot_cannot_restore_or_change_observations(source, standalone, mutation):
    from scripts.legiscan_eligibility import checked_standalone
    with sqlite3.connect(standalone) as con:
        con.execute(mutation)
    with pytest.raises(ValueError, match='LegiScan.*snapshot'):
        with checked_standalone(standalone):
            pytest.fail('stale snapshot accepted')


def test_central_changes_invalidate_previously_matching_snapshot(source, standalone):
    from scripts.legiscan_eligibility import checked_standalone
    with checked_standalone(standalone):
        pass
    with sqlite3.connect(source) as con:
        con.execute('UPDATE source_legiscan_roll_call SET yea=2,nay=0 WHERE roll_call_id=1')
    with pytest.raises(ValueError, match='LegiScan.*snapshot'):
        with checked_standalone(standalone):
            pytest.fail('rejected source roll call accepted from stale snapshot')
