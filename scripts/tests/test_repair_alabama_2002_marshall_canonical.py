from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

import repair_alabama_2002_marshall_canonical as repair

SCHEMA = """
CREATE TABLE vote_observations (year INTEGER, county_key TEXT, office TEXT, district REAL, party_norm TEXT, votes REAL, source TEXT);
CREATE TABLE canonical_candidates (year INTEGER, chamber TEXT, district INTEGER, canonical_party TEXT, canonical_votes REAL,
  canonical_name TEXT, canonical_source TEXT, person_id TEXT, canonical_candidate_id TEXT, incumbent INTEGER, winner INTEGER);
CREATE UNIQUE INDEX canonical_candidate_id_pk ON canonical_candidates(canonical_candidate_id);
CREATE UNIQUE INDEX canonical_candidate_election_uk ON canonical_candidates(year,chamber,district,canonical_party);
CREATE TABLE canonical_southern_legislative_candidate_election (candidate_result_id TEXT, observation_set_id TEXT, contract_version INTEGER,
  build_run_id TEXT, state_code TEXT, cycle INTEGER, chamber TEXT, district TEXT, candidate_name TEXT, candidate_name_original TEXT,
  party_family TEXT, party_original TEXT, votes INTEGER, vote_share REAL, source_family TEXT, as_of_utc TEXT);
CREATE TABLE warehouse_build_run (build_run_id TEXT PRIMARY KEY, target TEXT NOT NULL, started_at_utc TEXT NOT NULL,
  completed_at_utc TEXT, status TEXT NOT NULL CHECK (status IN ('running','validated','failed')), code_commit TEXT,
  configuration_json TEXT NOT NULL, validation_json TEXT);
CREATE TABLE qa_warehouse_source_repair (issue_id TEXT PRIMARY KEY, build_run_id TEXT NOT NULL REFERENCES warehouse_build_run(build_run_id),
  warehouse_object TEXT NOT NULL, scope TEXT NOT NULL, status TEXT NOT NULL, evidence_json TEXT NOT NULL, recorded_at_utc TEXT NOT NULL);
CREATE TABLE warehouse_manual_adjudication (adjudication_id TEXT PRIMARY KEY, domain TEXT NOT NULL, subject_type TEXT NOT NULL,
  subject_id TEXT NOT NULL, decision TEXT NOT NULL, rationale TEXT, evidence_locator TEXT,
  review_status TEXT NOT NULL CHECK (review_status IN ('proposed','approved','rejected','superseded')), decided_at_utc TEXT NOT NULL,
  supersedes_adjudication_id TEXT REFERENCES warehouse_manual_adjudication(adjudication_id));
CREATE TABLE unrelated_domain (value TEXT);
"""


def build(path: Path, *, break_segment=False, break_before=False) -> None:
    with sqlite3.connect(path) as c:
        c.executescript(SCHEMA)
        for (office, district, county, party), votes in repair.expected_segments().items():
            if break_segment and county == "MARSHALL" and district == 27 and party == "D":
                votes -= 1
            # two precinct rows per segment so the SUM path is exercised
            c.execute("INSERT INTO vote_observations VALUES (2002,?,?,?,?,?,'alabama_sos')", (county, office, float(district), party, votes - 1))
            c.execute("INSERT INTO vote_observations VALUES (2002,?,?,?,?,?,'alabama_sos')", (county, office, float(district), party, 1))
        rows = [(2002, "house", 26, "D", 1102.0, "McDaniel, Frank", "alabama_sos", "ALPERSON-MCDANIEL-FRANK", "AL-2002-house-26-D-MCDANIEL-FRANK", 0, 1),
                (2002, "house", 26, "R", 598.0, "Patterson, Jeffrey", "alabama_sos", "ALPERSON-PATTERSON-JEFFREY", "AL-2002-house-26-R-PATTERSON-JEFFREY", 0, 0),
                (2002, "senate", 9, "D", 8914.0 if not break_before else 8900.0, "Mitchem, Hinton", "alabama_sos", "ALPERSON-MITCHEM-HINTON", "AL-2002-senate-9-D-MITCHEM-HINTON", 0, 0),
                (2002, "senate", 9, "R", 9438.0, "Edmonds, Doris", "alabama_sos", "ALPERSON-EDMONDS-DORIS", "AL-2002-senate-9-R-EDMONDS-DORIS", 0, 1),
                (2018, "house", 1, "D", 100.0, "Other", "alabama_sos", "ALPERSON-OTHER", "AL-2018-house-1-D-OTHER", 0, 1)]
        c.executemany("INSERT INTO canonical_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
        for r in rows[:4]:
            total = {("house", 26): 1700, ("senate", 9): 8914 + 9438}[(r[1], r[2])]
            c.execute("INSERT INTO canonical_southern_legislative_candidate_election VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (r[8], f"ALCANON-2002-{r[1]}-{r[2]}", 1, "legacy", "AL", 2002, "lower" if r[1] == "house" else "upper", str(r[2]),
                       r[5], r[5], "democratic" if r[3] == "D" else "republican", r[3], int(r[4]), r[4] / total, "alabama_canonical", "t"))
        c.execute("INSERT INTO warehouse_build_run VALUES ('RUN-LATEST','prior','t','t','validated','abc','{}','{}')")
        c.execute("INSERT INTO unrelated_domain VALUES ('preserved')")


def test_dry_run_stages_without_writing(tmp_path):
    db = tmp_path / "w.sqlite"; build(db)
    result = repair.repair(db)
    assert result["warehouse_status"] == "dry_run"
    assert [u["id"] for u in result["proposal"]["updates"]] == [u["id"] for u in repair.UPDATES]
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT COUNT(*) FROM canonical_candidates").fetchone() == (5,)


def test_apply_updates_inserts_and_records_adjudications(tmp_path):
    db = tmp_path / "w.sqlite"; build(db)
    result = repair.repair(db, apply=True, expected_run="RUN-LATEST", backup=tmp_path / "b" / "pre.sqlite", authorized_by="owner")
    assert result["warehouse_status"] == "committed"
    with sqlite3.connect(db) as c:
        rows = dict(c.execute("SELECT canonical_candidate_id, canonical_votes FROM canonical_candidates"))
        assert rows["AL-2002-house-26-D-MCDANIEL-FRANK"] == 7069.0 and rows["AL-2002-senate-9-R-EDMONDS-DORIS"] == 16995.0
        assert rows["AL-2002-house-27-D-MCLAUGHLIN-JEFFREY"] == 7724.0 and rows["AL-2018-house-1-D-OTHER"] == 100.0
        winners = dict(c.execute("SELECT canonical_candidate_id, winner FROM canonical_candidates WHERE year=2002 AND chamber='senate'"))
        assert winners == {"AL-2002-senate-9-D-MITCHEM-HINTON": 1, "AL-2002-senate-9-R-EDMONDS-DORIS": 0}
        shares = c.execute("SELECT observation_set_id, ROUND(SUM(vote_share),9), COUNT(*) FROM canonical_southern_legislative_candidate_election GROUP BY 1").fetchall()
        assert sorted(shares) == [("ALCANON-2002-house-26", 1.0, 2), ("ALCANON-2002-house-27", 1.0, 2), ("ALCANON-2002-senate-9", 1.0, 2)]
        assert c.execute("SELECT COUNT(*) FROM warehouse_manual_adjudication WHERE review_status='approved'").fetchone() == (3,)
        assert c.execute("SELECT * FROM unrelated_domain").fetchall() == [("preserved",)]
        assert c.execute("SELECT status FROM warehouse_build_run ORDER BY rowid DESC LIMIT 1").fetchone() == ("validated",)
    with sqlite3.connect(tmp_path / "b" / "pre.sqlite") as saved:
        assert saved.execute("SELECT canonical_votes FROM canonical_candidates WHERE canonical_candidate_id='AL-2002-senate-9-D-MITCHEM-HINTON'").fetchone() == (8914.0,)
    report = json.loads((tmp_path / "b" / "pre.sqlite.application.json").read_text(encoding="utf-8"))
    assert report["validation"]["adjudications"] == [a[0] for a in repair.ADJUDICATIONS]
    assert repair.repair(db)["warehouse_status"] == "unchanged"


def test_refuses_when_source_segments_or_before_images_differ(tmp_path):
    db = tmp_path / "seg.sqlite"; build(db, break_segment=True)
    with pytest.raises(ValueError, match="Source segments differ"):
        repair.repair(db)
    db2 = tmp_path / "img.sqlite"; build(db2, break_before=True)
    with pytest.raises(ValueError, match="Before-image mismatch"):
        repair.repair(db2)


def test_apply_requires_snapshot_and_fresh_backup(tmp_path):
    db = tmp_path / "w.sqlite"; build(db)
    with pytest.raises(ValueError, match="snapshot changed"):
        repair.repair(db, apply=True, expected_run="RUN-OTHER", backup=tmp_path / "x.sqlite", authorized_by="owner")
    existing = tmp_path / "exists.sqlite"; existing.write_bytes(b"")
    with pytest.raises(FileExistsError):
        repair.repair(db, apply=True, expected_run="RUN-LATEST", backup=existing, authorized_by="owner")
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT COUNT(*) FROM canonical_candidates").fetchone() == (5,)
