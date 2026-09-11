from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

import repair_morgan_1994_fractional_cell as repair


SCHEMA = """
CREATE TABLE vote_observations (
  year INTEGER, county TEXT, county_key TEXT, precinct TEXT, precinct_key TEXT, office TEXT,
  district REAL, candidate TEXT, candidate_key TEXT, party TEXT, party_norm TEXT, votes REAL,
  source TEXT, authority_rank INTEGER, source_file TEXT, source_sheet TEXT, source_row INTEGER,
  source_column INTEGER, precinct_code TEXT, ballot_code TEXT, party_method TEXT,
  source_file_id TEXT, build_run_id TEXT);
CREATE TABLE warehouse_build_run (
  build_run_id TEXT PRIMARY KEY, target TEXT NOT NULL, started_at_utc TEXT NOT NULL,
  completed_at_utc TEXT, status TEXT NOT NULL CHECK (status IN ('running','validated','failed')),
  code_commit TEXT, configuration_json TEXT NOT NULL, validation_json TEXT);
CREATE TABLE qa_warehouse_source_repair (
  issue_id TEXT PRIMARY KEY, build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
  warehouse_object TEXT NOT NULL, scope TEXT NOT NULL, status TEXT NOT NULL,
  evidence_json TEXT NOT NULL, recorded_at_utc TEXT NOT NULL);
CREATE TABLE warehouse_manual_adjudication (
  adjudication_id TEXT PRIMARY KEY, domain TEXT NOT NULL, subject_type TEXT NOT NULL,
  subject_id TEXT NOT NULL, decision TEXT NOT NULL, rationale TEXT, evidence_locator TEXT,
  review_status TEXT NOT NULL CHECK (review_status IN ('proposed','approved','rejected','superseded')),
  decided_at_utc TEXT NOT NULL,
  supersedes_adjudication_id TEXT REFERENCES warehouse_manual_adjudication(adjudication_id));
"""

COLUMNS = ("year", "county", "county_key", "precinct", "precinct_key", "office", "district", "candidate",
           "candidate_key", "party", "party_norm", "votes", "source", "authority_rank", "source_file",
           "source_sheet", "source_row", "source_column", "precinct_code", "ballot_code", "party_method",
           "source_file_id", "build_run_id")


def observation(**overrides) -> tuple:
    base = dict(year=1994, county="MORGAN", county_key="MORGAN", precinct="26001", precinct_key="26001",
                office="Attorney General", district=None, candidate="Sessions", candidate_key="SESSIONS",
                party="R", party_norm="R", votes=144.4, source="alabama_sos", authority_rank=1,
                source_file="94g-prec/MORGAN.XLS", source_sheet="Morgan", source_row=48, source_column=11,
                precinct_code="26001", ballot_code="AG2", party_method="ballot_order_with_export_code",
                source_file_id="SRC-E64FFC4299ED54CB2D3A", build_run_id="RUN-ORIGINAL")
    base.update(overrides)
    return tuple(base[column] for column in COLUMNS)


def build_warehouse(path: Path, votes: float = 144.4) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(SCHEMA)
        rows = [
            observation(votes=votes),
            observation(source_row=47, precinct="26000", precinct_key="26000", precinct_code="26000", votes=512),
            observation(source_row=48, candidate="Evans", candidate_key="EVANS", party="D", party_norm="D",
                        source_column=10, ballot_code="AG1", votes=301),
            observation(year=1998, source_file="98g-prec/MORGAN.XLS", source_file_id="SRC-OTHER", votes=77),
        ]
        connection.executemany(f"INSERT INTO vote_observations VALUES ({','.join('?' for _ in COLUMNS)})", rows)
        connection.execute("INSERT INTO warehouse_build_run VALUES (?,?,?,?,?,?,?,?)",
                           ("RUN-LATEST", "prior", "2026-09-08T00:00:00+00:00", "2026-09-08T00:00:01+00:00",
                            "validated", "abc", "{}", "{}"))
        connection.execute("INSERT INTO qa_warehouse_source_repair VALUES (?,?,?,?,?,?,?)",
                           (repair.PRIOR_REVIEW, "RUN-LATEST", "vote_observations", "1994/MORGAN/26001/AG2",
                            "source_review", "{}", "2026-09-05T00:00:00+00:00"))


def all_rows(path: Path) -> list[tuple]:
    with sqlite3.connect(path) as connection:
        return connection.execute("SELECT rowid, * FROM vote_observations ORDER BY rowid").fetchall()


def test_dry_run_stages_single_cell_without_writing(tmp_path: Path) -> None:
    database = tmp_path / "w.sqlite"
    build_warehouse(database)
    before = all_rows(database)
    result = repair.repair(database)
    assert result["warehouse_status"] == "dry_run"
    assert result["staged"]["proposal"] == {"rowid": 1, "votes_before": 144.4, "votes_after": 144.0}
    assert result["staged"]["fractional_observations_in_table"] == 1
    assert result["staged"]["prior_review"]["issue_id"] == repair.PRIOR_REVIEW
    assert all_rows(database) == before


def test_apply_corrects_one_cell_and_records_adjudication(tmp_path: Path) -> None:
    database = tmp_path / "w.sqlite"
    build_warehouse(database)
    before = all_rows(database)
    backup = tmp_path / "backups" / "pre-morgan.sqlite"
    result = repair.repair(database, apply=True, expected_run="RUN-LATEST", backup=backup,
                           authorized_by="owner 2026-09-10")
    assert result["warehouse_status"] == "committed"
    after = all_rows(database)
    assert after[0][:12] == before[0][:12] and after[0][12] == 144.0 and after[0][13:] == before[0][13:]
    assert after[1:] == before[1:]
    with sqlite3.connect(database) as connection:
        adjudication = connection.execute(
            "SELECT decision, review_status, rationale FROM warehouse_manual_adjudication").fetchall()
        assert adjudication == [("reported_count=144", "approved", repair.RATIONALE)]
        qa = connection.execute(
            "SELECT status, evidence_json FROM qa_warehouse_source_repair WHERE issue_id LIKE 'WQA-04-fractional-adjudicated-%'"
        ).fetchone()
        assert qa[0] == "repaired_with_adjudication"
        evidence = json.loads(qa[1])
        assert evidence["before_image"]["votes"] == 144.4 and evidence["after_image"]["votes"] == 144.0
        assert evidence["remaining_fractional_observations"] == 0
        assert connection.execute("SELECT COUNT(*) FROM qa_warehouse_source_repair").fetchone()[0] == 2
        assert connection.execute("SELECT status FROM warehouse_build_run ORDER BY rowid DESC LIMIT 1").fetchone() == ("validated",)
    # Backup holds the reported value and a written report exists.
    with sqlite3.connect(backup) as saved:
        assert saved.execute("SELECT votes FROM vote_observations WHERE rowid=1").fetchone() == (144.4,)
    report = json.loads(backup.with_name(backup.name + ".application.json").read_text(encoding="utf-8"))
    assert report["validation"]["adjudication_id"] == repair.ADJUDICATION_ID
    # Re-application is a no-op.
    again = repair.repair(database)
    assert again["warehouse_status"] == "unchanged"


def test_apply_refuses_changed_snapshot_or_value(tmp_path: Path) -> None:
    database = tmp_path / "w.sqlite"
    build_warehouse(database)
    with pytest.raises(ValueError, match="snapshot changed"):
        repair.repair(database, apply=True, expected_run="RUN-OTHER", backup=tmp_path / "b.sqlite",
                      authorized_by="owner")
    assert all_rows(database)[0][12] == 144.4
    drifted = tmp_path / "d.sqlite"
    build_warehouse(drifted, votes=145.5)
    with pytest.raises(ValueError, match="no longer holds the reported value"):
        repair.repair(drifted)


def test_apply_requires_authorization_and_fresh_backup_path(tmp_path: Path) -> None:
    database = tmp_path / "w.sqlite"
    build_warehouse(database)
    with pytest.raises(ValueError, match="authorized-by"):
        repair.repair(database, apply=True, expected_run="RUN-LATEST", backup=tmp_path / "b.sqlite")
    existing = tmp_path / "exists.sqlite"
    existing.write_bytes(b"")
    with pytest.raises(FileExistsError):
        repair.repair(database, apply=True, expected_run="RUN-LATEST", backup=existing, authorized_by="owner")
