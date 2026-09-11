"""Acquisition time must not be inferred from a cached-file verification time."""
import json
from pathlib import Path
import sqlite3
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sync_warehouse_source_registry as registry
from warehouse import file_sha256, source_file_id

CHECKED = "2026-08-14T22:24:06.701187+00:00"


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "ROOT", tmp_path)
    manifest = tmp_path / "data/raw/census/source_manifest.csv"
    manifest.parent.mkdir(parents=True)
    source = manifest.with_name("fixture.zip")
    source.write_bytes(b"immutable Census fixture")
    pd.DataFrame([{"filename": source.name, "url": "https://example.invalid/census",
                   "sha256": file_sha256(source), "checked_utc": CHECKED}]).to_csv(manifest, index=False)
    census = next(item for item in registry.MANIFESTS if item[0] == "us_census")
    monkeypatch.setattr(registry, "MANIFESTS", [(census[0], manifest, *census[2:])])
    database = tmp_path / "warehouse.sqlite"
    monkeypatch.setattr(registry, "connect", lambda: sqlite3.connect(database))
    return database, manifest, source


def test_sync_does_not_promote_check_time_and_preserves_independent_acquisition(inputs):
    database, _, source = inputs
    registry.main()
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT retrieved_at_utc FROM warehouse_source_file").fetchone() == (None,)
        connection.execute("UPDATE warehouse_source_file SET retrieved_at_utc='2020-01-02T03:04:05Z'")
    registry.main()
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT retrieved_at_utc FROM warehouse_source_file").fetchone() == ("2020-01-02T03:04:05Z",)


@pytest.fixture
def database(inputs):
    database, _, source = inputs
    registry.main()
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE warehouse_source_file SET retrieved_at_utc=?", (CHECKED,))
        for identifier, provider, path, timestamp in [
            ("INDEPENDENT", "us_census", "other-census.zip", "2020-01-01Z"),
            ("OTHER", "other_provider", "other.zip", CHECKED),
            ("UNKNOWN", "us_census", "unknown.zip", None),
        ]:
            connection.execute("INSERT INTO warehouse_source_file(source_file_id,provider,local_path,retrieved_at_utc,sha256) VALUES (?,?,?,?,?)",
                               (identifier, provider, path, timestamp, "a" * 64))
        connection.execute("""CREATE TABLE qa_warehouse_source_repair(
            issue_id TEXT PRIMARY KEY, build_run_id TEXT, table_name TEXT, scope TEXT,
            status TEXT, evidence_json TEXT, recorded_at_utc TEXT)""")
        run = registry.begin_run(connection, "prior", {})
        registry.finish_run(connection, run, {"old": True})
        connection.execute("INSERT INTO qa_warehouse_source_repair VALUES (?,?,?,?,?,?,?)",
                           ("OLD", run, "old", "old", "review", "{}", "old"))
        connection.execute("CREATE TABLE unrelated(value TEXT)")
        connection.execute("INSERT INTO unrelated VALUES ('preserved')")
    return database


def test_exact_repair_preserves_sources_registry_controls_and_other_domains(database, inputs):
    _, manifest, source = inputs
    source_hashes = [file_sha256(path) for path in (manifest, source)]
    backup = database.with_name("backup.sqlite")
    result = registry.repair_census_check_times(database, backup)
    assert result["warehouse_status"] == "committed"
    assert result["validation"]["repaired_rows"] == 1
    assert result["validation"]["before_retrieved_at_utc"] == {
        source_file_id("us_census", source.relative_to(database.parent).as_posix()): CHECKED}
    assert [file_sha256(path) for path in (manifest, source)] == source_hashes
    with sqlite3.connect(database) as current, sqlite3.connect(backup) as old:
        assert current.execute("SELECT * FROM unrelated").fetchall() == old.execute("SELECT * FROM unrelated").fetchall()
        before, after = registry.registry_snapshot(old), registry.registry_snapshot(current)
        assert registry.snapshot_digests(before) == result["configuration"]["before_snapshot"]
        assert registry.snapshot_digests(after)[registry.REGISTRY] == result["validation"]["after_registry_sha256"]
        for identifier in ("INDEPENDENT", "OTHER", "UNKNOWN"):
            sql = "SELECT * FROM warehouse_source_file WHERE source_file_id=?"
            assert current.execute(sql, (identifier,)).fetchone() == old.execute(sql, (identifier,)).fetchone()
        assert len(after["warehouse_build_run"]) == len(before["warehouse_build_run"]) + 1
        assert current.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
    assert backup.with_name(backup.name + ".application.json").is_file()
    registry.main()
    replay = database.with_name("replay.sqlite")
    assert registry.repair_census_check_times(database, replay) == {"warehouse_status": "unchanged", "repaired_rows": 0}
    assert not replay.exists()


def test_manifest_match_with_independent_acquisition_is_not_cleared(database):
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE warehouse_source_file SET retrieved_at_utc='2020-01-02Z' WHERE local_path LIKE '%fixture.zip'")
        before = registry.registry_snapshot(connection)
    backup = database.with_name("backup.sqlite")
    assert registry.repair_census_check_times(database, backup)["warehouse_status"] == "unchanged"
    assert not backup.exists()
    with sqlite3.connect(database) as connection:
        assert registry.registry_snapshot(connection) == before


@pytest.mark.parametrize("defect", ["artifact_hash", "registry_hash", "registry_path", "provider", "duplicate", "escape"])
def test_evidence_mismatch_and_ambiguity_fail_before_backup(database, inputs, defect):
    _, manifest, source = inputs
    with sqlite3.connect(database) as connection:
        if defect in {"registry_hash", "registry_path", "provider"}:
            column = {"registry_hash": "sha256", "registry_path": "local_path", "provider": "provider"}[defect]
            value = "b" * 64 if defect == "registry_hash" else "incorrect"
            connection.execute(f"UPDATE warehouse_source_file SET {column}=? WHERE local_path LIKE '%fixture.zip'", (value,))
    if defect == "artifact_hash":
        source.write_bytes(b"changed fixture")
    elif defect == "duplicate":
        frame = pd.read_csv(manifest)
        pd.concat([frame, frame]).to_csv(manifest, index=False)
    elif defect == "escape":
        frame = pd.read_csv(manifest)
        frame["filename"] = str(database.parent.parent / "outside.zip")
        frame.to_csv(manifest, index=False)
    backup = database.with_name("backup.sqlite")
    with sqlite3.connect(database) as connection:
        before = registry.registry_snapshot(connection)
    with pytest.raises(ValueError):
        registry.repair_census_check_times(database, backup)
    assert not backup.exists()
    with sqlite3.connect(database) as connection:
        assert registry.registry_snapshot(connection) == before


@pytest.mark.parametrize("collision", ["backup", "report", "database"])
def test_existing_outputs_and_missing_database_are_refused(database, collision):
    backup = database.with_name("backup.sqlite")
    if collision == "database":
        absent = database.with_name("absent.sqlite")
        with pytest.raises(FileNotFoundError):
            registry.repair_census_check_times(absent, backup)
        assert not absent.exists()
        return
    target = backup if collision == "backup" else backup.with_name(backup.name + ".application.json")
    target.write_text("preserved", encoding="utf-8")
    with pytest.raises(FileExistsError):
        registry.repair_census_check_times(database, backup)
    assert target.read_text(encoding="utf-8") == "preserved"


def test_validation_failure_rolls_back_but_retains_recovery_backup(database, monkeypatch):
    with sqlite3.connect(database) as connection:
        before = registry.registry_snapshot(connection)
    def fail(*args):
        raise ValueError("injected validation failure")
    monkeypatch.setattr(registry, "validate_timestamp_repair", fail)
    backup = database.with_name("backup.sqlite")
    with pytest.raises(ValueError, match="injected"):
        registry.repair_census_check_times(database, backup)
    with sqlite3.connect(database) as connection, sqlite3.connect(backup) as recovery:
        assert registry.registry_snapshot(connection) == registry.registry_snapshot(recovery) == before


def test_triggers_and_authorizer_prevent_unrelated_mutations(database):
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TRIGGER unexpected AFTER UPDATE ON warehouse_source_file BEGIN DELETE FROM unrelated; END")
    with pytest.raises(ValueError, match="Triggers"):
        registry.repair_census_check_times(database, database.with_name("backup.sqlite"))
    with sqlite3.connect(database) as connection:
        connection.set_authorizer(registry.authorize_timestamp_repair)
        for sql in ("UPDATE warehouse_source_file SET license='invented'", "DELETE FROM unrelated",
                    "UPDATE unrelated SET value='changed'", "CREATE TABLE unexpected_table(x)",
                    "DROP TABLE unrelated"):
            with pytest.raises(sqlite3.DatabaseError, match="authorized"):
                connection.execute(sql)


def test_backup_snapshot_mismatch_aborts_before_writes(database, monkeypatch):
    original = registry.registry_snapshot
    with sqlite3.connect(database) as connection:
        before = original(connection)
    calls = 0
    def mismatched_backup(connection):
        nonlocal calls
        calls += 1
        result = original(connection)
        if calls == 2:
            result[registry.REGISTRY] = []
        return result
    monkeypatch.setattr(registry, "registry_snapshot", mismatched_backup)
    with pytest.raises(ValueError, match="Backup registry/control"):
        registry.repair_census_check_times(database, database.with_name("backup.sqlite"))
    with sqlite3.connect(database) as connection:
        assert original(connection) == before


def test_source_changes_during_repair_roll_back(database, inputs, monkeypatch):
    _, _, source = inputs
    original = registry.begin_run
    with sqlite3.connect(database) as connection:
        before = registry.registry_snapshot(connection)
    def change_source(connection, *args):
        run = original(connection, *args)
        source.write_bytes(b"concurrent fixture mutation")
        return run
    monkeypatch.setattr(registry, "begin_run", change_source)
    with pytest.raises(ValueError, match="hash mismatch"):
        registry.repair_census_check_times(database, database.with_name("backup.sqlite"))
    with sqlite3.connect(database) as connection:
        assert registry.registry_snapshot(connection) == before


def test_report_failure_is_explicit_after_commit(database, monkeypatch, capsys):
    capsys.readouterr()
    original = Path.open
    def fail_report(path, *args, **kwargs):
        if path.name.endswith(".application.json"):
            raise OSError("injected report failure")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", fail_report)
    assert registry.cli(["--repair-census-check-times", "--database", str(database),
                         "--backup", str(database.with_name("backup.sqlite"))]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["warehouse_status"] == "committed"
    assert result["report_status"] == "failed_after_commit"
    assert "do not blindly retry" in result["recovery"]
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT retrieved_at_utc FROM warehouse_source_file WHERE local_path LIKE '%fixture.zip'").fetchone() == (None,)
        assert connection.execute("SELECT status FROM warehouse_build_run WHERE build_run_id=?", (result["build_run_id"],)).fetchone() == ("validated",)


def test_cli_requires_explicit_repair_backup_and_does_not_sync_by_accident(monkeypatch):
    def no_sync():
        pytest.fail("Unexpected general registry sync")
    monkeypatch.setattr(registry, "main", no_sync)
    for args in (["--repair-census-check-times"], ["--backup", "some.sqlite"]):
        with pytest.raises(SystemExit) as error:
            registry.cli(args)
        assert error.value.code == 2
