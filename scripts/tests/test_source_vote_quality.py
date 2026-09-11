import sqlite3
import json

import pytest

import build_1994_cmo_baseline as baseline
import build_precinct_identity as identity
import stage_precinct_identity_repair as staging
from source_vote_quality import require_reported_vote_quality


@pytest.fixture
def source_db(tmp_path):
    path = tmp_path / "source.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute("""CREATE TABLE vote_observations (
            source TEXT, year INTEGER, county_key TEXT, precinct_key TEXT,
            office TEXT, district TEXT, candidate_key TEXT, party_norm TEXT,
            votes, source_file TEXT, source_sheet TEXT,
            source_row INTEGER, source_column INTEGER)""")
        connection.execute("""INSERT INTO vote_observations VALUES
            ('alabama_sos',1994,'MORGAN','26001','Attorney General',NULL,
             'SESSIONS','R',144.4,'94g-prec/MORGAN.XLS','Morgan',48,11)""")
        connection.execute("""CREATE TABLE canonical_candidates
            (year INTEGER, chamber TEXT, district INTEGER,
             canonical_party TEXT, canonical_votes REAL)""")
    return path


def test_returns_refuse_fractional_source_before_aggregation(source_db, monkeypatch):
    monkeypatch.setattr(baseline, "ELECTION_DB", source_db)
    with pytest.raises(ValueError, match="fractional"):
        baseline.load_returns()


@pytest.mark.parametrize("votes", [0, 1, 144, 144.0])
def test_integer_counts_including_zero_are_valid(source_db, votes):
    with sqlite3.connect(source_db) as connection:
        connection.execute("UPDATE vote_observations SET votes=?", (votes,))
        require_reported_vote_quality(connection)
        assert connection.execute("SELECT votes FROM vote_observations").fetchone()[0] == votes


@pytest.mark.parametrize("votes,issue", [
    (None, "unknown_missing_votes"), (144.4, "fractional"),
    (-1, "negative"), ("invalid", "nonnumeric"), (float("inf"), "nonfinite"),
    (float("-inf"), "nonfinite")])
def test_refusal_preserves_source_and_physical_locator(source_db, votes, issue):
    with sqlite3.connect(source_db) as connection:
        connection.execute("UPDATE vote_observations SET votes=?", (votes,))
        before = connection.execute("SELECT * FROM vote_observations").fetchall()
        with pytest.raises(ValueError, match=issue) as error:
            require_reported_vote_quality(connection)
        assert '"source_file": "94g-prec/MORGAN.XLS"' in str(error.value)
        assert '"source_sheet": "Morgan"' in str(error.value)
        assert '"source_row": 48' in str(error.value)
        assert '"source_column": 11' in str(error.value)
        assert connection.execute("SELECT * FROM vote_observations").fetchall() == before


def test_other_scopes_are_not_blocked(source_db):
    with sqlite3.connect(source_db) as connection:
        require_reported_vote_quality(connection, "year=?", (2010,))
        require_reported_vote_quality(connection, staging.PROFILES[staging.OFFICE_PROFILE])


def test_returns_read_valid_literal_counts_without_changing_source(source_db, monkeypatch):
    with sqlite3.connect(source_db) as connection:
        connection.execute("UPDATE vote_observations SET votes=0")
        connection.execute("""INSERT INTO vote_observations
            (source,year,office,votes) VALUES ('alabama_sos',2010,'Governor',1.5)""")
    monkeypatch.setattr(baseline, "ELECTION_DB", source_db)
    before = source_db.read_bytes()
    legislative, statewide, candidates = baseline.load_returns()
    assert statewide.votes.tolist() == [0]
    assert legislative.empty and candidates.empty
    assert source_db.read_bytes() == before


def test_identity_refuses_before_fingerprint_or_write(source_db, monkeypatch):
    monkeypatch.setattr(identity, "DB", source_db)
    monkeypatch.setattr(identity, "build_nodes", lambda _: pytest.fail("aggregation reached"))
    before = source_db.read_bytes()
    with pytest.raises(ValueError, match="fractional"):
        identity.main()
    assert source_db.read_bytes() == before


def test_stage_refuses_before_aggregation_or_outputs(source_db, tmp_path, monkeypatch):
    output = tmp_path / "stage"
    monkeypatch.setattr(staging.pd, "read_sql_query", lambda *a, **k: pytest.fail("aggregation reached"))
    before = source_db.read_bytes()
    with pytest.raises(ValueError, match="fractional"):
        staging.stage(source_db, output)
    assert not output.exists()
    assert source_db.read_bytes() == before


def test_replay_refuses_offsetting_fractional_cells(tmp_path):
    from scripts.tests.test_apply_precinct_identity_repair import fixture_stage, repair
    database, directory, accepted, *_ = fixture_stage(tmp_path)
    with sqlite3.connect(database) as connection:
        query = staging.source_query(staging.DEFAULT_PROFILE)
        before = connection.execute(query).fetchall()
        # Two cells in the same physical precinct/office group retain their sum.
        rows = connection.execute("""SELECT rowid FROM vote_observations
            WHERE year=1994 AND source='alabama_sos' AND precinct_key='002 B UPDATED'
            ORDER BY rowid""").fetchall()
        assert len(rows) == 2
        connection.execute("UPDATE vote_observations SET votes=votes+0.5 WHERE rowid=?", rows[0])
        connection.execute("UPDATE vote_observations SET votes=votes-0.5 WHERE rowid=?", rows[1])
        assert connection.execute(query).fetchall() == before
        with pytest.raises(ValueError, match="fractional"):
            repair.verified_stage(connection, directory, accepted)


@pytest.mark.parametrize("missing", [True, False])
def test_replay_requires_current_quality_helper_hash(tmp_path, missing):
    from scripts.tests.test_apply_precinct_identity_repair import fixture_stage, repair
    database, directory, _, *_ = fixture_stage(tmp_path)
    path = directory / "manifest.json"
    manifest = json.loads(path.read_text())
    assert "source_vote_quality.py" in manifest["code_sha256"]
    if missing:
        del manifest["code_sha256"]["source_vote_quality.py"]
    else:
        manifest["code_sha256"]["source_vote_quality.py"] = "0" * 64
    path.write_text(json.dumps(manifest))
    with sqlite3.connect(database) as connection:
        with pytest.raises(ValueError, match="Stage code changed: source_vote_quality.py"):
            repair.verified_stage(connection, directory, repair.file_sha256(path))
