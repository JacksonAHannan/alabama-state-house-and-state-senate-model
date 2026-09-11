"""Metadata transaction safeguards using synthetic databases and source bytes."""
import json
from pathlib import Path
import sqlite3

import pytest

import repair_sos_cell_lineage as repair
from stage_legacy_source_lineage import CORE, FIELDS
from warehouse import file_sha256, initialize


SOURCE_SQL = "SELECT rowid,* FROM vote_observations WHERE source='alabama_sos' AND year IN (1998,2004) ORDER BY rowid"
SCHEMA_SQL = "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"


def snapshot(path):
    with sqlite3.connect(path) as connection:
        return {table: connection.execute(f'SELECT rowid,* FROM "{table}" ORDER BY rowid').fetchall()
                for table in [repair.TABLE, *repair.CONTROLS, "unrelated"]}


@pytest.fixture
def fixture(tmp_path):
    database = tmp_path / "warehouse.sqlite"
    source = tmp_path / "source.zip"
    source.write_bytes(b"immutable synthetic source")
    with sqlite3.connect(database) as connection:
        initialize(connection)
        connection.execute("INSERT INTO warehouse_build_run VALUES ('BEFORE','fixture','2026-01-01','2026-01-01','validated','fixture','{}','{}')")
        connection.execute("CREATE TABLE qa_warehouse_source_repair(issue_id PRIMARY KEY,build_run_id,warehouse_object,scope,status,evidence_json,recorded_at_utc)")
        connection.execute("INSERT INTO warehouse_source_file(source_file_id,provider,local_path,sha256) VALUES ('fixture-source','fixture','source.zip',?)", (file_sha256(source),))
        fields = [*CORE, *FIELDS, "build_run_id"]
        connection.execute("CREATE TABLE vote_observations (" + ",".join(fields) + ")")
        for i, year in enumerate([1998, 2004, 2000]):
            row = dict(year=year, county="Example", county_key="EXAMPLE", precinct="P", precinct_key="P",
                       office="Unresolved", district=None, candidate=f"Fixture {i}", candidate_key=f"FIXTURE {i}",
                       party="", party_norm="O", votes=i, source="alabama_sos", authority_rank=1,
                       **dict.fromkeys(FIELDS), build_run_id="original-ingest")
            connection.execute("INSERT INTO vote_observations VALUES ("+",".join("?" for _ in fields)+")", [row[field] for field in fields])
        connection.execute("CREATE TABLE unrelated(value)")
        connection.execute("INSERT INTO unrelated VALUES ('preserve')")
        code_paths = [Path(repair.__file__).resolve(), *[Path(repair.__file__).with_name(name).resolve() for name in
                      ("stage_legacy_source_lineage.py", "warehouse.py", "load_alabama_2022_certified_source.py",
                       "repair_sos_contest_offices.py", "sos_precinct.py", "oe_normalize.py", "build_election_database.py")]]
        changes = []
        for rowid in [1, 2]:
            changes.append(dict(stored_rowid=rowid, before=dict.fromkeys(FIELDS),
                after=dict(source_file="member.xls", source_sheet="Sheet", source_row=3,
                           source_column=rowid+1, source_file_id="fixture-source"),
                source_key=list(connection.execute("SELECT "+",".join(CORE)+" FROM vote_observations WHERE rowid=?", (rowid,)).fetchone())))
        report = dict(schema_version=1, warehouse_status="unchanged", latest_run="BEFORE", changes=changes,
                      source_rows_sha256=repair.digest_rows(connection.execute(SOURCE_SQL)),
                      schema_sha256=repair.digest_rows(connection.execute(SCHEMA_SQL)),
                      code_hashes={str(path): file_sha256(path) for path in code_paths},
                      sources=[dict(source_file_id="fixture-source", local_path="source.zip", sha256=file_sha256(source))],
                      cohorts=[], ambiguities=[])
    return dict(root=tmp_path, database=database, report=report,
                proposal=tmp_path/"proposal.json", backup=tmp_path/"backup.sqlite")


def apply(fixture, expected=None):
    proposal = fixture["proposal"]
    proposal.write_text(json.dumps(fixture["report"]), encoding="utf-8")
    return repair.apply_legacy_proposal(fixture["database"], proposal,
        expected or file_sha256(proposal), fixture["backup"], root=fixture["root"])


def test_metadata_only_success_and_recovery_backup(fixture):
    before = snapshot(fixture["database"])
    result = apply(fixture)
    assert result["warehouse_status"] == "committed" and result["changed_rows"] == 2
    assert snapshot(fixture["backup"]) == before
    after = snapshot(fixture["database"])
    assert after["unrelated"] == before["unrelated"]
    assert after["warehouse_source_file"] == before["warehouse_source_file"]
    expected = [list(row) for row in before[repair.TABLE]]
    for change in fixture["report"]["changes"]:
        for offset, field in enumerate(FIELDS, start=1+len(CORE)):
            expected[change["stored_rowid"]-1][offset] = change["after"][field]
    assert after[repair.TABLE] == [tuple(row) for row in expected]
    assert all(row[-1] == "original-ingest" for row in after[repair.TABLE])
    for table in [repair.BUILD, repair.QA]:
        assert after[table][:-1] == before[table]
    fixture["backup"] = fixture["root"] / "replay.sqlite"
    with pytest.raises(ValueError, match="snapshot"):
        apply(fixture)
    assert not fixture["backup"].exists()


@pytest.mark.parametrize("kind", ["source", "schema", "code", "raw", "proposal", "registry", "latest"])
def test_snapshot_drift_refused(fixture, kind):
    with sqlite3.connect(fixture["database"]) as connection:
        if kind == "source": connection.execute("UPDATE vote_observations SET votes=99 WHERE rowid=1")
        if kind == "schema": connection.execute("CREATE TABLE added(value)")
        if kind == "registry": connection.execute("UPDATE warehouse_source_file SET sha256=?", ("0"*64,))
        if kind == "latest": connection.execute("UPDATE warehouse_build_run SET build_run_id='OTHER'")
    if kind == "code": fixture["report"]["code_hashes"][str(Path(repair.__file__).resolve())] = "0"*64
    if kind == "raw": (fixture["root"]/"source.zip").write_bytes(b"changed")
    before = snapshot(fixture["database"])
    with pytest.raises(ValueError):
        apply(fixture, expected="0"*64 if kind == "proposal" else None)
    assert snapshot(fixture["database"]) == before
    assert not fixture["backup"].exists()


@pytest.mark.parametrize("kind", ["duplicate", "populated", "missing", "scope", "source_key", "extra_field"])
def test_invalid_change_refused(fixture, kind):
    change = fixture["report"]["changes"][0]
    if kind == "duplicate": fixture["report"]["changes"].append(change.copy())
    if kind == "populated":
        change["before"]["source_sheet"] = "existing"
        with sqlite3.connect(fixture["database"]) as connection:
            connection.execute("UPDATE vote_observations SET source_sheet='existing' WHERE rowid=1")
            fixture["report"]["source_rows_sha256"] = repair.digest_rows(connection.execute(SOURCE_SQL))
    if kind == "missing": change["stored_rowid"] = 999
    if kind == "scope":
        change["stored_rowid"] = 3
        with sqlite3.connect(fixture["database"]) as connection:
            change["source_key"] = list(connection.execute("SELECT "+",".join(CORE)+" FROM vote_observations WHERE rowid=3").fetchone())
    if kind == "source_key": change["source_key"][0] = 1900
    if kind == "extra_field": change["after"]["votes"] = 99
    before = snapshot(fixture["database"])
    with pytest.raises(ValueError): apply(fixture)
    assert snapshot(fixture["database"]) == before


def test_existing_backup_not_overwritten(fixture):
    fixture["backup"].write_bytes(b"preserve backup")
    before = snapshot(fixture["database"])
    with pytest.raises(FileExistsError): apply(fixture)
    assert fixture["backup"].read_bytes() == b"preserve backup"
    assert snapshot(fixture["database"]) == before


@pytest.mark.parametrize("failure", ["mid_update", "after_updates", "proposal_during_apply", "raw_during_apply"])
def test_interruption_rolls_back_and_preserves_backup(fixture, monkeypatch, failure):
    before = snapshot(fixture["database"])
    if failure == "mid_update":
        original = repair.begin_run
        interrupted = []
        def interrupt(connection, *args):
            run = original(connection, *args)
            baseline = connection.total_changes
            def stop_after_first_change():
                if connection.total_changes > baseline:
                    interrupted.append(connection.total_changes-baseline)
                    connection.set_progress_handler(None, 0)
                    return 1
                return 0
            connection.set_progress_handler(stop_after_first_change, 1)
            return run
        monkeypatch.setattr(repair, "begin_run", interrupt)
    else:
        original = repair.finish_run
        def fail(connection, *args):
            if failure == "after_updates": raise KeyboardInterrupt("injected interruption")
            target = fixture["proposal"] if failure == "proposal_during_apply" else fixture["root"]/"source.zip"
            target.write_bytes(b"changed")
            return original(connection, *args)
        monkeypatch.setattr(repair, "finish_run", fail)
    with pytest.raises((ValueError, sqlite3.DatabaseError, KeyboardInterrupt)):
        apply(fixture)
    assert snapshot(fixture["database"]) == before
    assert snapshot(fixture["backup"]) == before
    if failure == "mid_update": assert interrupted == [1]
