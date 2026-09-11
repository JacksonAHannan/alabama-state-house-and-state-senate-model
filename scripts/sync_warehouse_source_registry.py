"""Load existing checked source manifests into the central warehouse registry."""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd

from warehouse import ROOT, begin_run, connect, database_path, file_sha256, finish_run, initialize, source_file_id, utcnow

MANIFESTS = [
    ("census_acs", ROOT/"data/raw/acs/block_group_joint/source_manifest.csv", "local_path", "source_url", "retrieved_on"),
    ("internet_archive_adah", ROOT/"data/raw/alabama_legislature/acts/internet_archive/source_manifest.csv", "local_path", "source_url", "retrieved_at_utc"),
    ("alabama_legislature", ROOT/"data/raw/alabama_legislature/house_journals/manifest.csv", "local_path", "source_url", None),
    # checked_utc is a verification time, including for previously cached files.
    ("us_census", ROOT/"data/raw/census/source_manifest.csv", "filename", "url", None),
    ("pollster_document", ROOT/"data/raw/polling/silver_recent/manifest.csv", "filename", "source_url", "retrieved_utc"),
]


def resolve_path(manifest: Path, value: object) -> Path:
    path=Path(str(value))
    if path.is_absolute():return path
    from_root=ROOT/path
    return from_root if from_root.exists() else manifest.parent/path


def main() -> None:
    rows=[]
    with closing(connect()) as connection:
        initialize(connection)
        # Election source records predate the general registry.
        if connection.execute("select count(*) from sqlite_master where type='table' and name='source_manifest'").fetchone()[0]:
            for source_id,year,provider,path,digest,authoritative in connection.execute(
                    "select source_id,year,source,path,sha256,authoritative_votes from source_manifest"):
                rows.append((provider,ROOT/path,None,None,digest,
                             "normalized","official_vote_counts" if authoritative else "identity_enrichment"))
        for provider,manifest,path_col,url_col,time_col in MANIFESTS:
            if not manifest.exists():continue
            frame=pd.read_csv(manifest)
            for record in frame.to_dict("records"):
                digest=str(record.get("sha256","")).strip().lower()
                if len(digest)!=64:continue
                path=resolve_path(manifest,record.get(path_col,""))
                if not path.exists():continue
                status="normalized" if provider in {"census_acs","us_census"} else "registered"
                rows.append((provider,path,record.get(url_col),record.get(time_col) if time_col else None,
                             digest,status,None))
        for provider,path,url,retrieved,digest,status,scope in rows:
            relative=path.resolve().relative_to(ROOT).as_posix()
            connection.execute("""INSERT INTO warehouse_source_file
              (source_file_id,provider,local_path,original_url,retrieved_at_utc,sha256,media_type,
               license,extraction_status,authoritative_scope)
              VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(source_file_id) DO UPDATE SET
              original_url=coalesce(excluded.original_url,warehouse_source_file.original_url),retrieved_at_utc=coalesce(excluded.retrieved_at_utc,warehouse_source_file.retrieved_at_utc),
              sha256=excluded.sha256,media_type=excluded.media_type,
              extraction_status=excluded.extraction_status,authoritative_scope=coalesce(excluded.authoritative_scope,warehouse_source_file.authoritative_scope)""",
              (source_file_id(provider,relative),provider,relative,None if pd.isna(url) else url,
               None if retrieved is None or pd.isna(retrieved) else str(retrieved),digest,
               mimetypes.guess_type(path.name)[0],None,status,scope))
        connection.commit()
        print(pd.read_sql("select provider,count(*) files,sum(case when extraction_status='normalized' then 1 else 0 end) normalized from warehouse_source_file group by provider order by provider",connection).to_string(index=False))


REGISTRY = "warehouse_source_file"
CONTROLS = {"warehouse_build_run", "qa_warehouse_source_repair"}
KEYS = {REGISTRY: "source_file_id", "warehouse_build_run": "build_run_id",
        "qa_warehouse_source_repair": "issue_id"}


def registry_snapshot(connection):
    return {table: connection.execute(f'SELECT * FROM "{table}" ORDER BY "{key}"').fetchall()
            for table, key in KEYS.items()}


def snapshot_digests(snapshot):
    return {table: hashlib.sha256(json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
            for table, rows in snapshot.items()}


def census_check_time_candidates(connection):
    """Stage exact copied check times only; differing acquisition evidence survives."""
    manifests = [item for item in MANIFESTS if item[0] == "us_census"]
    if len(manifests) != 1:
        raise ValueError("Expected exactly one Census manifest")
    provider, manifest, path_col, _, _ = manifests[0]
    manifest_hash = file_sha256(manifest)
    frame = pd.read_csv(manifest, dtype=str, keep_default_na=False)
    if not {path_col, "sha256", "checked_utc"}.issubset(frame.columns):
        raise ValueError("Missing Census evidence columns")
    candidates, sources, seen = {}, {}, set()
    for record in frame.to_dict("records"):
        if not record[path_col] or not record["checked_utc"]:
            raise ValueError("Missing Census path or check timestamp")
        path = resolve_path(manifest, record[path_col]).resolve()
        relative = path.relative_to(ROOT.resolve()).as_posix()
        identifier = source_file_id(provider, relative)
        if identifier in seen:
            raise ValueError("Duplicate or ambiguous Census manifest identity")
        seen.add(identifier)
        digest = record["sha256"].lower()
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("Malformed Census source hash")
        if not path.is_file() or file_sha256(path) != digest:
            raise ValueError(f"Census artifact hash mismatch or missing file: {relative}")
        row = connection.execute(f"SELECT provider,local_path,sha256,retrieved_at_utc FROM {REGISTRY} WHERE source_file_id=?",
                                 (identifier,)).fetchone()
        if row is None:
            continue
        if row[:3] != (provider, relative, digest):
            raise ValueError(f"Census registry identity/path/hash mismatch: {identifier}")
        sources[identifier] = {"local_path": relative, "sha256": digest, "checked_utc": record["checked_utc"]}
        if row[3] == record["checked_utc"]:
            candidates[identifier] = row[3]
    if file_sha256(manifest) != manifest_hash:
        raise ValueError("Census manifest changed during staging")
    return candidates, {"manifest": str(manifest.resolve()), "manifest_sha256": manifest_hash, "source_files": sources}


def authorize_timestamp_repair(action, table, column, database, trigger):
    if action == sqlite3.SQLITE_UPDATE:
        allowed = (table == REGISTRY and column == "retrieved_at_utc") or table in CONTROLS
        return sqlite3.SQLITE_OK if allowed else sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_INSERT:
        return sqlite3.SQLITE_OK if table in CONTROLS else sqlite3.SQLITE_DENY
    if action in (sqlite3.SQLITE_DELETE, sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_DROP_TABLE,
                  sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_CREATE_VIEW, sqlite3.SQLITE_DROP_VIEW,
                  sqlite3.SQLITE_CREATE_TRIGGER, sqlite3.SQLITE_DROP_TRIGGER,
                  sqlite3.SQLITE_CREATE_INDEX, sqlite3.SQLITE_DROP_INDEX,
                  sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH):
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def validate_timestamp_repair(connection, expected, before_controls, run):
    actual = registry_snapshot(connection)
    if actual[REGISTRY] != expected:
        raise ValueError("Unexpected registry change")
    for table in CONTROLS:
        key = KEYS[table]
        for row in before_controls[table]:
            if connection.execute(f'SELECT * FROM "{table}" WHERE "{key}"=?', (row[0],)).fetchone() != row:
                raise ValueError("Prior control history changed")
        expected_id = run if table == "warehouse_build_run" else "WQA-CENSUS-TIME-" + run
        extra = [row for row in actual[table] if row[0] not in {old[0] for old in before_controls[table]}]
        if len(extra) != 1 or extra[0][0] != expected_id:
            raise ValueError("Unexpected control additions")
    if connection.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("Foreign key violation")


def repair_census_check_times(database: Path, backup: Path):
    """Clear proven copied check times without initializing or rebuilding the warehouse."""
    database, backup = database.resolve(), backup.resolve()
    report_path = backup.with_name(backup.name + ".application.json")
    if database == backup or backup.exists() or report_path.exists():
        raise FileExistsError("Backup and application report require new separate paths")
    if not database.is_file():
        raise FileNotFoundError(database)
    with closing(sqlite3.connect(database.as_uri() + "?mode=rw", uri=True)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("BEGIN IMMEDIATE")
        try:
            candidates, evidence = census_check_time_candidates(connection)
            if not candidates:
                connection.rollback()
                return {"warehouse_status": "unchanged", "repaired_rows": 0}
            triggers = connection.execute("SELECT tbl_name FROM sqlite_master WHERE type='trigger'")
            if any(row[0] in KEYS for row in triggers):
                raise ValueError("Triggers on owned tables require separate review")
            connection.set_authorizer(authorize_timestamp_repair)
            before = registry_snapshot(connection)
            backup.parent.mkdir(parents=True, exist_ok=True)
            with backup.open("xb"):
                pass
            with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as source, closing(sqlite3.connect(backup)) as destination:
                source.execute("PRAGMA query_only=ON")
                source.backup(destination)
                if destination.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                    raise ValueError("Backup quick_check failed")
                if registry_snapshot(destination) != before:
                    raise ValueError("Backup registry/control snapshot mismatch")
            configuration = {**evidence, "backup": str(backup), "before_snapshot": snapshot_digests(before),
                             "application_code_sha256": file_sha256(Path(__file__)),
                             "contract": "checked_utc is not acquisition time; exact copied values become unknown"}
            run = begin_run(connection, "census_check_time_repair", configuration)
            columns = [row[1] for row in connection.execute(f"PRAGMA table_info({REGISTRY})")]
            time_index, id_index = columns.index("retrieved_at_utc"), columns.index("source_file_id")
            expected = []
            for original in before[REGISTRY]:
                row = list(original)
                if row[id_index] in candidates:
                    row[time_index] = None
                expected.append(tuple(row))
            for identifier, checked in candidates.items():
                source = evidence["source_files"][identifier]
                updated = connection.execute(f"""UPDATE {REGISTRY} SET retrieved_at_utc=NULL
                    WHERE source_file_id=? AND provider='us_census' AND local_path=? AND sha256=? AND retrieved_at_utc=?""",
                    (identifier, source["local_path"], source["sha256"], checked))
                if updated.rowcount != 1:
                    raise ValueError("Guarded timestamp update mismatch")
            # Reverify evidence after backup; concurrent raw-file edits cannot certify a repair.
            _, final_evidence = census_check_time_candidates(connection)
            if final_evidence != evidence:
                raise ValueError("Census evidence changed during repair")
            details = {"repaired_rows": len(candidates), "before_retrieved_at_utc": candidates,
                       "after_registry_sha256": snapshot_digests({REGISTRY: expected})[REGISTRY],
                       "backup": str(backup), "not_rebuilt": ["downstream provenance exports and as-of eligibility audits"],
                       "report_status": "database commit evidence authoritative; report written after commit"}
            connection.execute("INSERT INTO qa_warehouse_source_repair VALUES (?,?,?,?,?,?,?)",
                ("WQA-CENSUS-TIME-" + run, run, REGISTRY, "exact Census checked_utc copied as retrieval time",
                 "repaired_with_review", json.dumps(details, sort_keys=True), utcnow()))
            finish_run(connection, run, details)
            validate_timestamp_repair(connection, expected, before, run)
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
    report = {"warehouse_status": "committed", "build_run_id": run, "configuration": configuration, "validation": details}
    try:
        with report_path.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(report, indent=2) + "\n")
        report["report_status"] = "written"
    except OSError as exc:
        report["report_status"] = "failed_after_commit"
        report["report_error"] = str(exc)
        report["recovery"] = "Warehouse committed. Inspect its run evidence; do not blindly retry the repair."
    return report


SHOR_MANIFEST = Path("data/raw/ideology/shor_mccarty_manifest.json")
SHOR_ARTIFACT = Path("data/raw/ideology/shor_mccarty_individual_legislators_1993_2018.tsv")


def shor_manifest_metadata_candidate(connection, root):
    """Recover two literal metadata fields from the exact registered artifact."""
    root = root.resolve()
    manifest = root / SHOR_MANIFEST
    digest = file_sha256(manifest)
    record = json.loads(manifest.read_text(encoding="utf-8"))
    artifact = root / SHOR_ARTIFACT
    if record.get("filename") != SHOR_ARTIFACT.name:
        raise ValueError("Unexpected manifest artifact path")
    if record.get("publisher") != "Harvard Dataverse" or record.get("file_persistent_id") != "doi:10.7910/DVN/GZJOT3/6PK3W0":
        raise ValueError("Unexpected manifest provider identity")
    if artifact.resolve() != (manifest.parent / record["filename"]).resolve():
        raise ValueError("Manifest artifact path mismatch")
    artifact.resolve().relative_to(root)
    if not artifact.is_file() or file_sha256(artifact) != record.get("sha256"):
        raise ValueError("Manifest artifact hash mismatch")
    values = {"original_url": record.get("access_url"), "license": record.get("license")}
    if values["original_url"] != "https://dataverse.harvard.edu/api/access/datafile/:persistentId/?persistentId=doi:10.7910/DVN/GZJOT3/6PK3W0":
        raise ValueError("Unexpected manifest access URL")
    if not isinstance(values["license"], str) or not values["license"].strip():
        raise ValueError("Manifest lacks explicit license")
    relative = SHOR_ARTIFACT.as_posix()
    identifier = source_file_id("shor_mccarty", relative)
    found = connection.execute(f"SELECT source_file_id,provider,local_path,sha256,original_url,license FROM {REGISTRY} WHERE source_file_id=? OR local_path=?",
                               (identifier, relative)).fetchall()
    if len(found) != 1 or found[0][:4] != (identifier, "shor_mccarty", relative, record["sha256"]):
        raise ValueError("Registry identity/path/hash mismatch")
    before = dict(zip(values, found[0][4:]))
    if any(value is not None and str(value).strip() and value != values[field]
           for field, value in before.items()):
        raise ValueError("Existing registry metadata conflicts with manifest")
    changes = {field: value for field, value in values.items()
               if before[field] is None or not str(before[field]).strip()}
    if file_sha256(manifest) != digest:
        raise ValueError("Manifest changed during staging")
    return {"source_file_id": identifier, "provider": "shor_mccarty", "local_path": relative,
            "sha256": record["sha256"], "manifest_path": str(manifest), "manifest_sha256": digest,
            "before": before, "after": values, "changes": changes}


def authorize_manifest_metadata(action, table, column, database, trigger):
    if action == sqlite3.SQLITE_UPDATE:
        allowed = trigger is None and (table == REGISTRY and column in {"original_url", "license"}
                                      or table == "warehouse_build_run")
        return sqlite3.SQLITE_OK if allowed else sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_INSERT:
        return sqlite3.SQLITE_OK if trigger is None and table in CONTROLS else sqlite3.SQLITE_DENY
    return authorize_timestamp_repair(action, table, column, database, trigger)


def repair_shor_manifest_metadata(database: Path, *, apply=False, expected_run=None,
                                  backup: Path | None = None, expected_manifest_sha256=None,
                                  root: Path = ROOT):
    """Dry-run by default; apply fills absent URL/license under a pinned snapshot."""
    if apply and (not expected_run or backup is None or not expected_manifest_sha256):
        raise ValueError("Apply requires latest run, manifest hash and new backup")
    database = database.resolve()
    if not database.is_file():
        raise FileNotFoundError(database)
    if apply:
        backup = backup.resolve()
        if backup == database or backup.exists():
            raise FileExistsError("Backup requires a new separate path")
    code = {str(path.resolve()): file_sha256(path) for path in
            (Path(__file__), Path(__file__).with_name("warehouse.py"))}
    with closing(sqlite3.connect(database.as_uri()+("?mode=rw" if apply else "?mode=ro"), uri=True)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        if not apply:
            connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN IMMEDIATE" if apply else "BEGIN")
        try:
            latest = connection.execute("SELECT build_run_id FROM warehouse_build_run ORDER BY rowid DESC LIMIT 1").fetchone()[0]
            if expected_run is not None and expected_run != latest:
                raise ValueError("Warehouse snapshot changed")
            evidence = shor_manifest_metadata_candidate(connection, root)
            if expected_manifest_sha256 is not None and evidence["manifest_sha256"] != expected_manifest_sha256:
                raise ValueError("Manifest hash differs from reviewed evidence")
            if not apply:
                connection.rollback()
                return {"warehouse_status": "unchanged", "latest_run": latest, "candidate": evidence}
            if not evidence["changes"]:
                raise ValueError("No missing metadata; replay requires separate review")
            if any(row[0] in KEYS for row in connection.execute("SELECT tbl_name FROM sqlite_master WHERE type='trigger'")):
                raise ValueError("Owned-table triggers require review")
            before = registry_snapshot(connection)
            schema_sql = "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
            schema = connection.execute(schema_sql).fetchall()
            backup.parent.mkdir(parents=True, exist_ok=True)
            with backup.open("xb"):
                pass
            with closing(sqlite3.connect(database.as_uri()+"?mode=ro", uri=True)) as reader, closing(sqlite3.connect(backup)) as destination:
                reader.execute("PRAGMA query_only=ON")
                reader.backup(destination)
                if destination.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                    raise ValueError("Backup integrity failed")
                if registry_snapshot(destination) != before or destination.execute(schema_sql).fetchall() != schema:
                    raise ValueError("Backup snapshot mismatch")
            if shor_manifest_metadata_candidate(connection, root) != evidence:
                raise ValueError("Manifest evidence changed during backup")
            connection.set_authorizer(authorize_manifest_metadata)
            config = {"evidence": evidence, "expected_run": latest, "backup": str(backup),
                      "code_hashes": code, "before_snapshot": snapshot_digests(before)}
            run = begin_run(connection, "shor_manifest_registry_metadata", config)
            fields = list(evidence["changes"])
            update = connection.execute(f"UPDATE {REGISTRY} SET "+",".join(f"{field}=?" for field in fields)
                +" WHERE source_file_id=? AND provider=? AND local_path=? AND sha256=? AND original_url IS ? AND license IS ?",
                [evidence["changes"][field] for field in fields]+[evidence[field] for field in
                    ("source_file_id", "provider", "local_path", "sha256")]+list(evidence["before"].values()))
            if update.rowcount != 1:
                raise ValueError("Metadata before-image mismatch")
            columns = [row[1] for row in connection.execute(f"PRAGMA table_info({REGISTRY})")]
            expected = []
            for row in before[REGISTRY]:
                values = list(row)
                if row[columns.index("source_file_id")] == evidence["source_file_id"]:
                    for field in fields:
                        values[columns.index(field)] = evidence["changes"][field]
                expected.append(tuple(values))
            details = {"source_file_id": evidence["source_file_id"], "before": evidence["before"],
                       "after": evidence["after"], "manifest_sha256": evidence["manifest_sha256"],
                       "limitations": "Literal URL/license recovery only; retrieval, scope, original ingestion and derived products unchanged."}
            issue = "WQA-SHOR-METADATA-"+run
            connection.execute("INSERT INTO qa_warehouse_source_repair VALUES (?,?,?,?,?,?,?)",
                (issue, run, REGISTRY, "exact manifest-backed URL/license", "metadata_repaired",
                 json.dumps(details, sort_keys=True), utcnow()))
            finish_run(connection, run, details)
            actual = registry_snapshot(connection)
            if actual[REGISTRY] != expected or connection.execute(schema_sql).fetchall() != schema:
                raise ValueError("Unexpected registry/schema mutation")
            for table in CONTROLS:
                old_ids = {row[0] for row in before[table]}
                retained = [row for row in actual[table] if row[0] in old_ids]
                added = [row for row in actual[table] if row[0] not in old_ids]
                if retained != before[table] or len(added) != 1 or added[0][0] != (run if table == "warehouse_build_run" else issue):
                    raise ValueError("Prior control history changed")
            final = shor_manifest_metadata_candidate(connection, root)
            if {k:v for k,v in final.items() if k not in {"before", "changes"}} != {k:v for k,v in evidence.items() if k not in {"before", "changes"}}:
                raise ValueError("Manifest evidence changed during application")
            if any(file_sha256(Path(path)) != digest for path, digest in code.items()):
                raise ValueError("Application code changed")
            if connection.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("Foreign key violation")
            connection.commit()
            return {"warehouse_status": "committed", "build_run_id": run, "qa_issue_id": issue,
                    "configuration": config, "validation": details}
        except BaseException:
            connection.rollback()
            raise


def cli(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repair-census-check-times", action="store_true")
    parser.add_argument("--shor-manifest-metadata", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-run")
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--database", type=Path)
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args(argv)
    if args.shor_manifest_metadata:
        if args.repair_census_check_times:
            parser.error("Choose one registry repair")
        result = repair_shor_manifest_metadata(args.database or database_path(), apply=args.apply,
            expected_run=args.expected_run, backup=args.backup, expected_manifest_sha256=args.manifest_sha256)
        print(json.dumps(result, indent=2))
        return 0
    if args.apply or args.expected_run or args.manifest_sha256:
        parser.error("--apply, --expected-run and --manifest-sha256 require --shor-manifest-metadata")
    if not args.repair_census_check_times:
        if args.database or args.backup:
            parser.error("--database and --backup apply only to --repair-census-check-times")
        main()
        return 0
    if args.backup is None:
        parser.error("--repair-census-check-times requires --backup NEWPATH")
    result = repair_census_check_times(args.database or database_path(), args.backup)
    print(json.dumps(result, indent=2))
    return 1 if result.get("report_status") == "failed_after_commit" else 0


if __name__ == "__main__":
    raise SystemExit(cli())
