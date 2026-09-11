"""Bounded registration replay safeguards; fixtures never touch the live database."""
import importlib.util
from pathlib import Path
import sqlite3
import shutil

import pytest
from warehouse import initialize


@pytest.fixture
def registration(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[2] / "data/processed/elections/backups/pre-canvass-registration-2026-09-07.application.py"
    spec = importlib.util.spec_from_file_location("canvass_registration_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    (tmp_path / "scripts").mkdir()
    for name in ("warehouse.py", "sync_warehouse_source_registry.py"):
        shutil.copyfile(module.ROOT / "scripts" / name, tmp_path / "scripts" / name)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "DATABASE", tmp_path / "warehouse.sqlite")
    monkeypatch.setattr(module, "BACKUP", tmp_path / "before.sqlite")
    manifest = dict(source_file_id="SRC-FIXTURE", provider="fixture", local_path="source.pdf",
                    source_url="https://example.org/source", retrieved_at="2026-01-01T00:00:00Z",
                    sha256="a" * 64, media_type="application/pdf", license_or_terms="review",
                    authoritative_scope="fixture counts")
    monkeypatch.setattr(module, "evidence", lambda: (manifest, {}))
    with sqlite3.connect(module.DATABASE) as c:
        initialize(c)
        c.execute("INSERT INTO warehouse_build_run VALUES (?,?,?,?,'validated',?,?,?)",
                  (module.EXPECTED_RUN, "fixture", "2026-01-01", "2026-01-01", "fixture", "{}", "{}"))
        c.execute("CREATE TABLE qa_warehouse_source_repair(issue_id PRIMARY KEY,build_run_id,warehouse_object,scope,status,evidence_json,recorded_at_utc)")
        c.execute("CREATE TABLE unrelated(value)")
        c.execute("INSERT INTO unrelated VALUES ('preserve')")
    return module


def test_registration_appends_only_one_source_and_control_pair(registration):
    registration.main()
    with sqlite3.connect(registration.DATABASE) as c:
        assert c.execute("SELECT COUNT(*) FROM warehouse_source_file").fetchone() == (1,)
        assert c.execute("SELECT COUNT(*) FROM warehouse_build_run").fetchone() == (2,)
        assert c.execute("SELECT COUNT(*) FROM qa_warehouse_source_repair").fetchone() == (1,)
        assert c.execute("SELECT * FROM unrelated").fetchall() == [("preserve",)]
    with sqlite3.connect(registration.BACKUP) as c:
        assert c.execute("SELECT COUNT(*) FROM warehouse_source_file").fetchone() == (0,)


def test_authorizer_blocks_unrelated_writes_and_rolls_back(registration, monkeypatch):
    def stray_write(connection, *args):
        connection.execute("INSERT INTO unrelated VALUES ('forbidden')")
    monkeypatch.setattr(registration, "begin_run", stray_write)
    with pytest.raises(sqlite3.DatabaseError, match="authorized"):
        registration.main()
    with sqlite3.connect(registration.DATABASE) as c:
        assert c.execute("SELECT * FROM unrelated").fetchall() == [("preserve",)]
        assert c.execute("SELECT COUNT(*) FROM warehouse_source_file").fetchone() == (0,)
        assert c.execute("SELECT COUNT(*) FROM warehouse_build_run").fetchone() == (1,)


def test_existing_backup_is_never_overwritten(registration):
    registration.BACKUP.write_bytes(b"existing recovery evidence")
    with pytest.raises(FileExistsError):
        registration.main()
    assert registration.BACKUP.read_bytes() == b"existing recovery evidence"


def test_changed_snapshot_refuses_before_backup(registration):
    with sqlite3.connect(registration.DATABASE) as c:
        c.execute("UPDATE warehouse_build_run SET build_run_id='different'")
    with pytest.raises(ValueError, match="snapshot changed"):
        registration.main()
    assert not registration.BACKUP.exists()


def test_source_change_during_backup_rolls_back(registration, monkeypatch):
    original = registration.evidence()
    observations = iter([original, (original[0], {"changed": True})])
    monkeypatch.setattr(registration, "evidence", lambda: next(observations))
    with pytest.raises(ValueError, match="changed during backup"):
        registration.main()
    with sqlite3.connect(registration.DATABASE) as c:
        assert c.execute("SELECT COUNT(*) FROM warehouse_source_file").fetchone() == (0,)
