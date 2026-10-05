"""Fixture tests for the 1994 party-label repair; the real warehouse is never opened."""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

import pytest

import repair_alabama_1994_party_labels as repair
from oe_normalize import norm_party
from warehouse import ROOT

SCHEMA = """
CREATE TABLE vote_observations (year INTEGER, county_key TEXT, office TEXT, district REAL, candidate TEXT,
  candidate_key TEXT, party TEXT, party_norm TEXT, votes REAL, source TEXT, source_file TEXT, source_column INTEGER,
  ballot_code TEXT, party_method TEXT, source_file_id TEXT, build_run_id TEXT);
CREATE TABLE canonical_candidates (year INTEGER, chamber TEXT, district INTEGER, canonical_party TEXT, canonical_votes REAL,
  canonical_name TEXT, canonical_source TEXT, person_id TEXT, canonical_candidate_id TEXT, incumbent INTEGER, winner INTEGER);
CREATE UNIQUE INDEX canonical_candidate_id_pk ON canonical_candidates(canonical_candidate_id);
CREATE UNIQUE INDEX canonical_candidate_election_uk ON canonical_candidates(year,chamber,district,canonical_party);
CREATE TABLE canonical_southern_legislative_candidate_election (candidate_result_id TEXT PRIMARY KEY, observation_set_id TEXT,
  contract_version INTEGER, build_run_id TEXT, state_code TEXT, cycle INTEGER, chamber TEXT, district TEXT,
  candidate_name TEXT, candidate_name_original TEXT, party_family TEXT, party_original TEXT, votes INTEGER, vote_share REAL,
  source_family TEXT, authority_rank INTEGER, as_of_utc TEXT);
CREATE TABLE warehouse_source_file (source_file_id TEXT PRIMARY KEY, provider TEXT NOT NULL, local_path TEXT NOT NULL UNIQUE,
  original_url TEXT, retrieved_at_utc TEXT, sha256 TEXT NOT NULL, media_type TEXT, license TEXT,
  extraction_status TEXT NOT NULL, authoritative_scope TEXT);
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
UNRELATED_CANONICAL = [(1994, "house", 2, "D", 8019.0, "Hamilton", "alabama_sos", "ALPERSON-HAMILTON", "AL-1994-house-2-D-HAMILTON", 0, 1),
                       (2018, "house", 10, "D", 100.0, "Other", "alabama_sos", "ALPERSON-OTHER", "AL-2018-house-10-D-OTHER", 0, 1)]
# Pre-existing 1994 surname merges that the new HD51 Rogers and HD92 Martin rows must not join.
PREEXISTING_MERGES = [(1994, "house", 36, "R", 5371.0, "Rogers", "alabama_sos", "ALPERSON-ROGERS", "AL-1994-house-36-R-ROGERS", 0, 1),
                      (1994, "house", 52, "D", 7750.0, "Rogers", "alabama_sos", "ALPERSON-ROGERS", "AL-1994-house-52-D-ROGERS", 0, 1),
                      (1994, "house", 27, "R", 5746.0, "Martin", "alabama_sos", "ALPERSON-MARTIN", "AL-1994-house-27-R-MARTIN", 0, 0),
                      (1994, "house", 40, "D", 5333.0, "Martin", "alabama_sos", "ALPERSON-MARTIN", "AL-1994-house-40-D-MARTIN", 0, 0)]


def _source_rows():
    """Synthetic precinct rows reproducing every target's column/row/vote totals plus contest remainders."""
    rows, column = [], 0
    for index, t in enumerate(repair.SOURCE_TARGETS):
        for i in range(t.rows):
            col = i % t.columns
            votes = t.votes - (t.rows - 1) if i == 0 else 1.0
            rows.append((1994, t.county_key or f"C{col}", t.office or "Statewide Office", t.district_before,
                         f"Target{index}", f"T{index}", t.party_before, norm_party(t.party_before), votes, "alabama_sos",
                         f"94g-prec/T{index}.XLS", 100 + col, t.ballot_code, repair.BEFORE_METHOD, repair.PRECINCT_SOURCE_ID, "RUN-OLD"))
    # Rows for candidates the repair does not touch (Starkey, Drake, Dixon's Elmore column, ...).
    for (chamber, district), contest in repair.CONTESTS.items():
        office = "State House" if chamber == "house" else "State Senate"
        for cid, party, votes, *_ in contest.after:
            covered = 0.0
            for t in repair.SOURCE_TARGETS:
                district_after = t.district_after if t.district_after is not None else t.district_before
                if t.office == office and district_after == district and t.party_after == party:
                    covered += t.votes
            remainder = votes - covered
            if remainder > 0:
                column += 1
                rows.append((1994, "FILLER", office, float(district), cid, f"F{column}", party, party, remainder, "alabama_sos",
                             "94g-prec/FILLER.XLS", column, f"X{column}", repair.BEFORE_METHOD, repair.PRECINCT_SOURCE_ID, "RUN-OLD"))
    rows.append((1998, "MADISON", "State House", 10.0, "Haney", "HANEY", "D", "D", 5.0, "alabama_sos", "98g-prec/MADISON.XLS",
                 3, "AHS10", "ballot_order", "SRC-1998", "RUN-OLD"))
    return rows


def build(path: Path, root: Path, *, drift_source=False, drift_canonical=False, extra_canonical=()) -> None:
    with sqlite3.connect(path) as c:
        c.executescript(SCHEMA)
        rows = _source_rows()
        if drift_source:
            first = list(rows[0]); first[6] = "R"; first[7] = "R"; rows[0] = tuple(first)
        c.executemany(f"INSERT INTO vote_observations VALUES ({','.join('?' * 16)})", rows)
        canonical = list(UNRELATED_CANONICAL) + PREEXISTING_MERGES + list(extra_canonical)
        for (chamber, district), contest in repair.CONTESTS.items():
            for cid, party, votes, winner, name, person in contest.before:
                if drift_canonical and cid == "AL-1994-house-91-D-SPICER":
                    votes -= 1
                canonical.append((1994, chamber, district, party, votes, name, "alabama_sos", person, cid, 0, winner))
        c.executemany("INSERT INTO canonical_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?)", canonical)
        for row in canonical:
            year, chamber, district, party, votes = row[:5]
            total = sum(r[4] for r in canonical if r[:3] == row[:3])
            c.execute("INSERT INTO canonical_southern_legislative_candidate_election VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (row[8], f"ALCANON-{year}-{chamber}-{district}", 1, "legacy", "AL", year,
                       "lower" if chamber == "house" else "upper", str(district), row[5], row[5],
                       "democratic" if party == "D" else "republican", party, int(votes), votes / total,
                       "alabama_canonical", 5, "legacy"))
        c.execute("INSERT INTO canonical_southern_legislative_candidate_election VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  ("LCAND-HD92", "LSET-HD92", 2, "RUN-K", "AL", 1994, "lower", "92", "HAMMETT, SETH", "hammett, seth",
                   "democratic", "d", 5449, 0.56, "klarner", 30, "t"))
        c.execute("INSERT INTO warehouse_source_file VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (repair.PRECINCT_SOURCE_ID, "alabama_sos", repair.PRECINCT_ARCHIVE, "u", "t",
                   repair.PRECINCT_ARCHIVE_SHA256, "zip", None, "normalized", "official_vote_counts"))
        c.execute("INSERT INTO warehouse_build_run VALUES ('RUN-LATEST','prior','t','t','validated','abc','{}','{}')")
        c.execute("INSERT INTO unrelated_domain VALUES ('preserved')")


@pytest.fixture()
def env(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    for relative in (repair.ADJUDICATIONS_CSV, repair.SUPERSESSION_CSV):
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, root / relative)
    ideology = root / "data" / "manual" / "ideology"; ideology.mkdir(parents=True)
    (ideology / "notes.csv").write_text("canonical_candidate_id,note\nAL-1994-house-19-R-ANDERSON,retired reference\n", encoding="utf-8")
    hashes = {}
    for relative in (repair.PRECINCT_ARCHIVE, *[spec["path"] for spec in repair.EVIDENCE_REGISTRATIONS]):
        path = root / relative; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(relative.encode("utf-8"))
        hashes[relative] = hashlib.sha256(relative.encode("utf-8")).hexdigest()
    monkeypatch.setattr(repair, "PRECINCT_ARCHIVE_SHA256", hashes[repair.PRECINCT_ARCHIVE])
    monkeypatch.setattr(repair, "EVIDENCE_REGISTRATIONS", tuple(
        {**spec, "sha256": hashes[spec["path"]]} for spec in repair.EVIDENCE_REGISTRATIONS))
    database = tmp_path / "warehouse.sqlite"
    build(database, root)
    return root, database, tmp_path


def _apply(root, database, tmp_path, name="pre.sqlite"):
    return repair.repair(database, apply=True, expected_run="RUN-LATEST", backup=tmp_path / "backups" / name,
                         authorized_by="owner test", root=root)


def test_dry_run_reports_every_change_without_writing(env):
    root, database, _ = env
    before = database.read_bytes()
    result = repair.repair(database, root=root)
    assert result["warehouse_status"] == "dry_run"
    summary = result["summary"]
    assert (summary["source_targets"], summary["source_columns"], summary["source_rows"]) == (45, 267, 11259)
    assert (summary["contests"], summary["canonical_rows_before"], summary["canonical_rows_after"]) == (38, 54, 49)
    assert summary["war_universe_enter"] == ["house-101", "house-11", "house-21", "house-51", "house-91", "house-92",
                                             "senate-11", "senate-31"]
    assert len(summary["war_universe_leave"]) == 14
    assert summary["manual_references"]["rekeyed_references"] == {}
    assert summary["manual_references"]["retired_references"] == {"data/manual/ideology/notes.csv": ["AL-1994-house-19-R-ANDERSON"]}
    assert database.read_bytes() == before


def test_apply_relabels_rekeys_and_records_adjudications(env):
    root, database, tmp_path = env
    result = _apply(root, database, tmp_path)
    assert result["warehouse_status"] == "committed" and result["report_status"] == "written"
    with sqlite3.connect(database) as c:
        ids = {r[0] for r in c.execute("SELECT canonical_candidate_id FROM canonical_candidates WHERE year=1994")}
        assert {"AL-1994-house-10-R-HANEY", "AL-1994-house-91-R-MOORE", "AL-1994-house-92-D-HAMMETT",
                "AL-1994-senate-11-R-HILL", "AL-1994-house-21-D-HINSHAW", "AL-1994-house-21-R-JOHNSTON"} <= ids
        assert not ids & {"AL-1994-house-10-D-HANEY", "AL-1994-house-8-R-NEW", "AL-1994-senate-25-D-ANDERSON",
                          "AL-1994-house-21-D-JOHNSTON"}
        winners = dict(c.execute("SELECT canonical_candidate_id, winner FROM canonical_candidates WHERE year=1994 AND chamber='house' AND district=91"))
        assert winners == {"AL-1994-house-91-D-SPICER": 0, "AL-1994-house-91-R-MOORE": 1}
        assert c.execute("SELECT canonical_votes FROM canonical_candidates WHERE canonical_candidate_id='AL-1994-senate-25-R-DIXON'").fetchone() == (32550.0,)
        sets = c.execute("""SELECT observation_set_id, ROUND(SUM(vote_share), 9), COUNT(*) FROM canonical_southern_legislative_candidate_election
                            WHERE observation_set_id IN ('ALCANON-1994-house-92','ALCANON-1994-senate-11','ALCANON-1994-house-8') GROUP BY 1""").fetchall()
        assert sorted(sets) == [("ALCANON-1994-house-8", 1.0, 1), ("ALCANON-1994-house-92", 1.0, 2), ("ALCANON-1994-senate-11", 1.0, 2)]
        covington = c.execute("SELECT DISTINCT ballot_code, district, party, party_method FROM vote_observations WHERE ballot_code LIKE '_HS92' ORDER BY 1").fetchall()
        assert covington == [("AHS92", 92.0, "D", repair.BEFORE_METHOD), ("BHS92", 92.0, "R", repair.BEFORE_METHOD),
                             ("CHS92", 92.0, "I", repair.OFFICIAL)]
        assert set(c.execute("SELECT DISTINCT party, party_norm, party_method FROM vote_observations WHERE ballot_code='SUPJUST2'")) == {("R", "R", repair.REVIEWED)}
        assert set(c.execute("SELECT DISTINCT party, party_norm FROM vote_observations WHERE ballot_code='ASENAT25' AND county_key='ELMORE'")) == {("", "O")}
        # Rows outside the adjudicated scope are untouched.
        assert c.execute("SELECT party, party_method FROM vote_observations WHERE year=1998").fetchone() == ("D", "ballot_order")
        unrelated = c.execute("""SELECT * FROM canonical_candidates
                                 WHERE year<>1994 OR (year=1994 AND chamber='house' AND district=2)""").fetchall()
        assert sorted(unrelated) == sorted(UNRELATED_CANONICAL)
        assert c.execute("SELECT COUNT(*) FROM canonical_southern_legislative_candidate_election WHERE observation_set_id='LSET-HD92'").fetchone() == (1,)
        assert c.execute("SELECT SUM(votes) FROM vote_observations").fetchone()[0] == sum(r[8] for r in _source_rows())
        assert c.execute("SELECT * FROM unrelated_domain").fetchall() == [("preserved",)]
        assert c.execute("SELECT COUNT(*) FROM warehouse_manual_adjudication WHERE review_status='approved'").fetchone() == (42,)
        registered = c.execute("SELECT provider, retrieved_at_utc, license, extraction_status FROM warehouse_source_file WHERE source_file_id<>?",
                               (repair.PRECINCT_SOURCE_ID,)).fetchall()
        assert sorted(registered) == [("alabama_forestry_commission", None, None, "registered"), ("alabama_sos", None, None, "registered")]
        evidence = json.loads(c.execute("SELECT evidence_json FROM qa_warehouse_source_repair").fetchone()[0])
        assert len(evidence["supersession"]) == 49 and evidence["not_rebuilt"]
        assert c.execute("SELECT status FROM warehouse_build_run ORDER BY rowid DESC LIMIT 1").fetchone() == ("validated",)
    with sqlite3.connect(tmp_path / "backups" / "pre.sqlite") as saved:
        assert saved.execute("SELECT canonical_votes FROM canonical_candidates WHERE canonical_candidate_id='AL-1994-house-91-D-SPICER'").fetchone() == (11761.0,)
    # Idempotent: a second run sees the applied state and changes nothing.
    assert repair.repair(database, root=root)["warehouse_status"] == "unchanged"
    run = sqlite3.connect(database).execute("SELECT build_run_id FROM warehouse_build_run ORDER BY rowid DESC LIMIT 1").fetchone()[0]
    assert repair.repair(database, apply=True, expected_run=run, backup=tmp_path / "backups" / "again.sqlite",
                         authorized_by="owner test", root=root)["warehouse_status"] == "unchanged"


def test_refuses_drifted_source_or_canonical_before_images(tmp_path, env):
    root, _, _ = env
    for flag in ("drift_source", "drift_canonical"):
        database = tmp_path / f"{flag}.sqlite"
        build(database, root, **{flag: True})
        with pytest.raises(ValueError, match="Before-image mismatch"):
            repair.repair(database, root=root)


def test_apply_requires_snapshot_authorization_and_fresh_backup(env):
    root, database, tmp_path = env
    with pytest.raises(ValueError, match="requires"):
        repair.repair(database, apply=True, expected_run="RUN-LATEST", backup=tmp_path / "b.sqlite", root=root)
    with pytest.raises(ValueError, match="snapshot changed"):
        repair.repair(database, apply=True, expected_run="RUN-OTHER", backup=tmp_path / "b.sqlite",
                      authorized_by="owner test", root=root)
    existing = tmp_path / "exists.sqlite"; existing.write_bytes(b"")
    with pytest.raises(FileExistsError):
        repair.repair(database, apply=True, expected_run="RUN-LATEST", backup=existing, authorized_by="owner test", root=root)
    with sqlite3.connect(database) as c:
        assert c.execute("SELECT COUNT(*) FROM canonical_candidates WHERE canonical_candidate_id='AL-1994-house-10-D-HANEY'").fetchone() == (1,)


def test_refuses_changed_records_and_rekeyed_manual_references(env):
    root, database, tmp_path = env
    (root / "data" / "manual" / "ideology" / "notes.csv").write_text(
        "canonical_candidate_id,note\nAL-1994-house-10-D-HANEY,would break after re-keying\n", encoding="utf-8")
    with pytest.raises(ValueError, match="re-keyed"):
        _apply(root, database, tmp_path)
    record = root / repair.ADJUDICATIONS_CSV
    record.write_bytes(record.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="Reviewed record changed"):
        repair.repair(database, root=root)


def test_records_match_the_script_and_cover_every_contest():
    records = repair.read_manual_records(ROOT)
    assert len(records["adjudications"]) == 42 and len(records["supersession"]) == 49
    contests = {(r["chamber"], int(r["district"])) for r in records["adjudications"] if r["chamber"]}
    assert contests == set(repair.CONTESTS)
    assert all(r["reviewer_status"] == "owner-approved 2026-10-04" for r in records["adjudications"])


def test_new_people_never_join_another_1994_contest_person_id(tmp_path, env):
    from alabama_candidate_identity import career_identity, is_stub_person
    root, database, _ = env
    _apply(root, database, tmp_path)
    with sqlite3.connect(database) as c:
        people = dict(c.execute("SELECT canonical_candidate_id, person_id FROM canonical_candidates WHERE year=1994"))
        frame = __import__("pandas").read_sql("SELECT canonical_candidate_id, person_id, canonical_name AS resolved_name "
                                              "FROM canonical_candidates WHERE year=1994", c)
    for cid, (name_id, qualified) in repair.DISAMBIGUATED_PERSON_IDS.items():
        assert people[cid] == qualified and not is_stub_person(qualified)
        assert [other for other, person in people.items() if person == qualified] == [cid]
    # The career helper keeps a non-stub person_id as is; it never folds it back by name.
    careers = career_identity(frame).set_index("canonical_candidate_id")
    assert careers.loc["AL-1994-senate-11-R-HILL", "career_person_id"] == "ALPERSON-HILL--1994-SENATE-11"
    assert careers.loc["AL-1994-house-41-R-HILL", "career_person_id"] == "ALPERSON-HILL"
    # Re-keyed rows keep their existing person (pre-existing merges are not changed).
    assert people["AL-1994-house-10-R-HANEY"] == "ALPERSON-HANEY"


def test_refuses_a_new_person_whose_surname_id_is_held_elsewhere(tmp_path, env):
    root, _, _ = env
    database = tmp_path / "collision.sqlite"
    build(database, root, extra_canonical=[(1994, "house", 60, "D", 10.0, "Oden", "alabama_sos", "ALPERSON-ODEN",
                                            "AL-1994-house-60-D-ODEN", 0, 1)])
    with pytest.raises(ValueError, match="Person ID collision"):
        repair.repair(database, root=root)
