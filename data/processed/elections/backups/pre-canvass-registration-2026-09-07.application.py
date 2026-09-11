"""Auditable one-time, append-only certified source registration. No result writes."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
from warehouse import begin_run, finish_run, file_sha256, source_file_id, utcnow
from sync_warehouse_source_registry import registry_snapshot, snapshot_digests

MANIFEST = ROOT / "data/raw/alabama_elections_and_geography/2022_general_certified_canvass.manifest.json"
AUDIT = ROOT / "project_docs/audits/ALABAMA_2022_CERTIFIED_SOURCE_RECONCILIATION.json"
DATABASE = ROOT / "data/processed/elections/alabama_elections.sqlite"
BACKUP = Path(__file__).with_name("pre-canvass-registration-2026-09-07.sqlite")
EXPECTED_RUN = "RUN-FB3931B5261247C094477492E72AC7DB"
OWNED = {"warehouse_source_file", "warehouse_build_run", "qa_warehouse_source_repair"}


def authorize(action, table, column, database, trigger):
    if trigger:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_INSERT:
        return sqlite3.SQLITE_OK if table in OWNED else sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_UPDATE:
        return sqlite3.SQLITE_OK if table == "warehouse_build_run" else sqlite3.SQLITE_DENY
    if action in {sqlite3.SQLITE_DELETE, sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_DROP_TABLE,
                  sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_CREATE_VIEW, sqlite3.SQLITE_DROP_VIEW,
                  sqlite3.SQLITE_CREATE_TRIGGER, sqlite3.SQLITE_DROP_TRIGGER,
                  sqlite3.SQLITE_CREATE_INDEX, sqlite3.SQLITE_DROP_INDEX,
                  sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH}:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def evidence():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    source = ROOT / manifest["local_path"]
    source.resolve().relative_to(ROOT.resolve())
    if file_sha256(source) != manifest["sha256"] or source.stat().st_size != manifest["size_bytes"]:
        raise ValueError("Canvass changed")
    precinct_source = audit["precinct_source"]
    if file_sha256(ROOT / precinct_source["source_path"]) != precinct_source["sha256"]:
        raise ValueError("Precinct source changed")
    if audit["canvass_source"] != manifest or audit["summary"] != {
            "contests": 140, "named_candidates": 211, "write_in_totals": 140,
            "named_votes": 2426083, "write_in_votes": 30426,
            "unknown_cells_retained": 22018, "review_rows": 0}:
        raise ValueError("Reviewed source reconciliation changed")
    for path, digest in audit["code_sha256"].items():
        if file_sha256(ROOT / path) != digest:
            raise ValueError("Reconciliation code changed")
    if source_file_id(manifest["provider"], manifest["local_path"]) != manifest["source_file_id"]:
        raise ValueError("Source identity mismatch")
    return manifest, {"manifest_sha256": file_sha256(MANIFEST), "audit_sha256": file_sha256(AUDIT),
                      "source_sha256": manifest["sha256"]}


def main():
    if BACKUP.exists() or not DATABASE.is_file():
        raise FileExistsError("Require existing warehouse and new separate backup")
    manifest, hashes = evidence()
    with closing(sqlite3.connect(DATABASE.as_uri() + "?mode=rw", uri=True)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("BEGIN IMMEDIATE")
        try:
            latest = connection.execute("SELECT build_run_id FROM warehouse_build_run ORDER BY started_at_utc DESC LIMIT 1").fetchone()
            if latest != (EXPECTED_RUN,):
                raise ValueError("Warehouse snapshot changed; review before replay")
            if connection.execute("SELECT 1 FROM warehouse_source_file WHERE source_file_id=? OR local_path=?",
                                  (manifest["source_file_id"], manifest["local_path"])).fetchone():
                raise ValueError("Source already registered; no overwrite allowed")
            if any(row[0] in OWNED for row in connection.execute("SELECT tbl_name FROM sqlite_master WHERE type='trigger'")):
                raise ValueError("Owned table triggers require review")
            before = registry_snapshot(connection)
            with BACKUP.open("xb"):
                pass
            with closing(sqlite3.connect(DATABASE.as_uri() + "?mode=ro", uri=True)) as source, closing(sqlite3.connect(BACKUP)) as destination:
                source.execute("PRAGMA query_only=ON")
                source.backup(destination)
                if destination.execute("PRAGMA quick_check").fetchall() != [("ok",)] or registry_snapshot(destination) != before:
                    raise ValueError("Backup verification failed")
            if evidence() != (manifest, hashes):
                raise ValueError("Source evidence changed during backup")
            connection.set_authorizer(authorize)
            configuration = {**hashes, "backup": str(BACKUP.relative_to(ROOT)),
                             "application_code_sha256": file_sha256(Path(__file__)),
                             "helper_code_sha256": {name: file_sha256(ROOT / "scripts" / name)
                                                     for name in ("warehouse.py", "sync_warehouse_source_registry.py")},
                             "before_snapshot": snapshot_digests(before),
                             "source_file_id": manifest["source_file_id"],
                             "scope": "append one source registry row; no election result or model changes"}
            run = begin_run(connection, "alabama_2022_certified_source_registration", configuration)
            row = (manifest["source_file_id"], manifest["provider"], manifest["local_path"],
                   manifest["source_url"], manifest["retrieved_at"], manifest["sha256"],
                   manifest["media_type"], manifest["license_or_terms"], "registered",
                   manifest["authoritative_scope"])
            connection.execute("INSERT INTO warehouse_source_file VALUES (?,?,?,?,?,?,?,?,?,?)", row)
            details = {"registered_rows": 1, "source_file_id": row[0], "result_rows_changed": 0,
                       "limitations": ["No canonical result repair or producer integration",
                                       "Unknown precinct values unchanged", "Redistribution terms remain review"]}
            issue = "WQA-CANVASS-REGISTRATION-" + run
            connection.execute("INSERT INTO qa_warehouse_source_repair VALUES (?,?,?,?,?,?,?)",
                               (issue, run, "warehouse_source_file", row[0], "registered_source_only",
                                json.dumps(details, sort_keys=True), utcnow()))
            finish_run(connection, run, details)
            after = registry_snapshot(connection)
            if after["warehouse_source_file"] != sorted(before["warehouse_source_file"] + [row]):
                raise ValueError("Unexpected registry change")
            for table, new_id in [("warehouse_build_run", run), ("qa_warehouse_source_repair", issue)]:
                if [r for r in after[table] if r[0] != new_id] != before[table] or len(after[table]) != len(before[table]) + 1:
                    raise ValueError("Unexpected control history change")
            if connection.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("Foreign key violation")
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
    print(json.dumps({"status": "committed", "build_run_id": run,
                      "configuration": configuration, "validation": details}))


if __name__ == "__main__":
    main()
