"""Exact metadata recovery on isolated SQLite and synthetic artifact bytes."""
import json
from pathlib import Path
import sqlite3

import pytest

import sync_warehouse_source_registry as sync
from warehouse import file_sha256, initialize, source_file_id


@pytest.fixture
def fixture(tmp_path):
    artifact = tmp_path/sync.SHOR_ARTIFACT
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"synthetic source bytes")
    manifest = tmp_path/sync.SHOR_MANIFEST
    manifest.write_text(json.dumps(dict(filename=artifact.name, publisher="Harvard Dataverse",
        file_persistent_id="doi:10.7910/DVN/GZJOT3/6PK3W0", sha256=file_sha256(artifact),
        access_url="https://dataverse.harvard.edu/api/access/datafile/:persistentId/?persistentId=doi:10.7910/DVN/GZJOT3/6PK3W0",
        license="CC0 1.0")), encoding="utf-8")
    database = tmp_path/"warehouse.sqlite"
    identifier = source_file_id("shor_mccarty", sync.SHOR_ARTIFACT.as_posix())
    with sqlite3.connect(database) as connection:
        initialize(connection)
        connection.execute("INSERT INTO warehouse_build_run VALUES ('BEFORE','fixture','2026-01-01','2026-01-01','validated','fixture','{}','{}')")
        connection.execute("CREATE TABLE qa_warehouse_source_repair(issue_id PRIMARY KEY,build_run_id,warehouse_object,scope,status,evidence_json,recorded_at_utc)")
        connection.execute("INSERT INTO warehouse_source_file(source_file_id,provider,local_path,sha256,retrieved_at_utc,authoritative_scope) VALUES (?,'shor_mccarty',?,?,'original-time','original-scope')",
                           (identifier,sync.SHOR_ARTIFACT.as_posix(),file_sha256(artifact)))
        connection.execute("CREATE TABLE unrelated(value)")
        connection.execute("INSERT INTO unrelated VALUES ('preserve')")
    return dict(root=tmp_path, database=database, manifest=manifest, artifact=artifact,
                backup=tmp_path/"backup.sqlite", expected_run="BEFORE",
                expected_manifest_sha256=file_sha256(manifest), apply=True)


def apply(fixture):
    return sync.repair_shor_manifest_metadata(**{k:v for k,v in fixture.items() if k not in {"manifest", "artifact"}})


def snapshot(path):
    with sqlite3.connect(path) as connection:
        return sync.registry_snapshot(connection) | {"unrelated":connection.execute("SELECT * FROM unrelated").fetchall()}


def test_dry_run_and_exact_fill_with_verified_backup(fixture):
    before = snapshot(fixture["database"])
    raw = fixture["database"].read_bytes()
    result = sync.repair_shor_manifest_metadata(fixture["database"], root=fixture["root"])
    assert set(result["candidate"]["changes"]) == {"original_url", "license"}
    assert fixture["database"].read_bytes() == raw
    applied = apply(fixture)
    assert applied["warehouse_status"] == "committed"
    assert snapshot(fixture["backup"]) == before
    after = snapshot(fixture["database"])
    assert after["unrelated"] == before["unrelated"]
    with sqlite3.connect(fixture["database"]) as connection:
        row = connection.execute("SELECT original_url,license,retrieved_at_utc,authoritative_scope FROM warehouse_source_file").fetchone()
        assert row == (result["candidate"]["after"]["original_url"], "CC0 1.0", "original-time", "original-scope")
        assert connection.execute("SELECT COUNT(*) FROM warehouse_build_run").fetchone() == (2,)
        assert connection.execute("SELECT COUNT(*) FROM qa_warehouse_source_repair").fetchone() == (1,)
    fixture.update(expected_run=applied["build_run_id"], backup=fixture["root"]/"replay.sqlite")
    with pytest.raises(ValueError, match="replay"): apply(fixture)
    assert not fixture["backup"].exists()


@pytest.mark.parametrize("field", ["original_url", "license"])
def test_matching_populated_field_preserved_while_empty_field_filled(fixture, field):
    values = json.loads(fixture["manifest"].read_text())
    value = values["access_url" if field == "original_url" else "license"]
    other = "license" if field == "original_url" else "original_url"
    with sqlite3.connect(fixture["database"]) as connection:
        connection.execute(f"UPDATE warehouse_source_file SET {field}=?,{other}='  '", (value,))
    assert apply(fixture)["warehouse_status"] == "committed"
    with sqlite3.connect(fixture["database"]) as connection:
        assert connection.execute(f"SELECT {field} FROM warehouse_source_file").fetchone() == (value,)


@pytest.mark.parametrize("kind", ["url_conflict", "license_conflict", "provider", "path", "hash", "raw", "manifest", "latest", "missing_manifest_hash", "manifest_filename", "manifest_provider"])
def test_refusal_preserves_registry(fixture, kind):
    with sqlite3.connect(fixture["database"]) as connection:
        if kind == "url_conflict": connection.execute("UPDATE warehouse_source_file SET original_url='existing'")
        if kind == "license_conflict": connection.execute("UPDATE warehouse_source_file SET license='existing'")
        if kind == "provider": connection.execute("UPDATE warehouse_source_file SET provider='other'")
        if kind == "path": connection.execute("UPDATE warehouse_source_file SET local_path='other'")
        if kind == "hash": connection.execute("UPDATE warehouse_source_file SET sha256=?", ("0"*64,))
    if kind == "raw": fixture["artifact"].write_bytes(b"changed")
    if kind == "manifest": fixture["manifest"].write_text(fixture["manifest"].read_text()+" ")
    if kind == "latest": fixture["expected_run"] = "OTHER"
    if kind == "missing_manifest_hash": fixture["expected_manifest_sha256"] = None
    if kind in {"manifest_filename", "manifest_provider"}:
        record = json.loads(fixture["manifest"].read_text())
        record["filename" if kind == "manifest_filename" else "publisher"] = "other"
        fixture["manifest"].write_text(json.dumps(record))
        fixture["expected_manifest_sha256"] = file_sha256(fixture["manifest"])
    before = snapshot(fixture["database"])
    with pytest.raises(ValueError): apply(fixture)
    assert snapshot(fixture["database"]) == before
    assert not fixture["backup"].exists()


def test_backup_never_overwritten(fixture):
    fixture["backup"].write_bytes(b"keep")
    with pytest.raises(FileExistsError): apply(fixture)
    assert fixture["backup"].read_bytes() == b"keep"


@pytest.mark.parametrize("failure", ["after_update", "unrelated", "old_history", "source_drift", "code_drift"])
def test_transaction_failure_restores_snapshot(fixture, monkeypatch, failure):
    before = snapshot(fixture["database"])
    original = sync.finish_run
    def fail(connection, *args):
        if failure == "after_update": raise KeyboardInterrupt("injected interruption")
        if failure == "unrelated": connection.execute("UPDATE unrelated SET value='bad'")
        if failure == "old_history": connection.execute("UPDATE warehouse_build_run SET target='bad' WHERE build_run_id='BEFORE'")
        if failure == "source_drift": fixture["artifact"].write_bytes(b"changed")
        if failure == "code_drift":
            hasher = sync.file_sha256
            monkeypatch.setattr(sync, "file_sha256", lambda path: "changed" if Path(path).name == "warehouse.py" else hasher(path))
        return original(connection, *args)
    monkeypatch.setattr(sync, "finish_run", fail)
    with pytest.raises((ValueError, sqlite3.DatabaseError, KeyboardInterrupt)): apply(fixture)
    assert snapshot(fixture["database"]) == before
    assert snapshot(fixture["backup"]) == before
