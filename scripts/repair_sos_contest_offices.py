"""Correct reviewed source office/district labels, preserving every vote and ID.

Dry-run is read-only. Application requires a current run ID and a new backup.
No source refresh, identity rebuild, geographic allocation or analytical output.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
from zipfile import ZipFile

import pandas as pd

from build_election_database import _observations
from sos_precinct import _office, _workbook_sheets, normalize_workbook
from load_alabama_2022_certified_source import digest_rows, encode, identifier
from warehouse import ROOT, begin_run, database_path, file_sha256, finish_run, utcnow

AUDIT = Path("project_docs/audits/SOS_CONTEST_CELL_LINEAGE_2026_09_07.json")
AUDIT_SHA256 = "73283ffa8f17fae24799420adf4c6a1684123d50a2e71b1680be1dceb21781ad"
SOURCE_IDS = {2010: "SRC-FF8B52A38CA4247C0714", 2012: "SRC-7DA917C4D69397F1C305"}
TARGET = "sos_contest_office_label_repair"
TABLE = "vote_observations"
BUILD = "warehouse_build_run"
QA = "qa_warehouse_source_repair"
CONTROLS = [BUILD, QA, "warehouse_source_file"]
STALE = {
    "dynamic_source_views": "Office/district filters reflect corrected labels immediately; not independently revalidated.",
    "precinct_identity": "precinct_nodes, fingerprints, match candidates and source links for Geneva2010/Morgan2012 require stale review; office is a dependency.",
    "geography_consumers": "Affected county/year geography links, transfer evidence, allocations and dependent materializations require separate reconciliation.",
    "historical_federal_baseline": "Existing normalization handles old/new federal labels; no numerical change established, not a full validation.",
    "not_rebuilt": "No identity, allocation, candidate, model or publication rebuild performed.",
}


def plain(value):
    return None if pd.isna(value) else value.item() if hasattr(value, "item") else value


def records(frame: pd.DataFrame) -> list[dict]:
    return [{key: plain(value) for key, value in row.items()} for row in frame.to_dict("records")]


def key_of(row, columns):
    return tuple(plain(row[column]) for column in columns)


def load_sources(root: Path = ROOT):
    if file_sha256(root / AUDIT) != AUDIT_SHA256:
        raise ValueError("Reviewed office audit hash mismatch")
    audit = json.loads((root / AUDIT).read_text(encoding="utf-8"))
    hashes = {str(AUDIT): AUDIT_SHA256} | audit["code_sha256"]
    frames, sheets_by_cohort = {}, {}
    for path, digest in audit["code_sha256"].items():
        if file_sha256(root / path) != digest:
            raise ValueError(f"Audited parser hash mismatch: {path}")
    for scope in audit["cohorts"]:
        path, member = root / scope["source_path"], scope["source_member"]
        if file_sha256(path) != scope["source_sha256"]:
            raise ValueError("Source archive hash mismatch")
        with ZipFile(path) as archive:
            if archive.namelist().count(member) != 1:
                raise ValueError("Missing or ambiguous archive member")
            content = archive.read(member)
        if hashlib.sha256(content).hexdigest() != scope["member_sha256"]:
            raise ValueError("Source member hash mismatch")
        hashes[scope["source_path"]] = scope["source_sha256"]
        parsed = normalize_workbook(content, scope["county"], scope["year"])
        parsed["source_file"] = member
        key = (scope["year"], scope["county"].upper())
        frames[key] = _observations(parsed, "alabama_sos", 1)
        sheets_by_cohort[key] = _workbook_sheets(content)
    return audit, frames, sheets_by_cohort, hashes


def registered_sources(connection, audit, root=ROOT):
    evidence = {}
    for scope in audit["cohorts"]:
        rows = connection.execute("SELECT source_file_id,local_path,sha256 FROM warehouse_source_file WHERE local_path=?", (scope["source_path"],)).fetchall()
        if rows != [(SOURCE_IDS[scope["year"]], scope["source_path"], scope["source_sha256"])]:
            raise ValueError("Registered source identity/path/hash mismatch")
        if file_sha256(root / scope["source_path"]) != scope["source_sha256"]:
            raise ValueError("Registered source changed on disk")
        evidence[rows[0][0]] = {"local_path": rows[0][1], "sha256": rows[0][2],
                               "member": scope["source_member"], "member_sha256": scope["member_sha256"]}
    return evidence


def stage(connection, audit, frames, sheets):
    """Pair only unique unchanged-grain keys; retain every ambiguous row."""
    columns = audit["comparison_key"]
    changes, unchanged_ambiguous, reports = [], [], []
    for scope in audit["cohorts"]:
        key = (scope["year"], scope["county"].upper())
        stored = pd.read_sql_query(f"SELECT rowid AS stored_rowid,* FROM {TABLE} WHERE year=? AND county_key=? AND source='alabama_sos' ORDER BY rowid", connection, params=key)
        parsed = frames[key]
        old_rows, new_rows = records(stored), records(parsed)
        old_groups, new_groups = defaultdict(list), defaultdict(list)
        for row in old_rows: old_groups[key_of(row, columns)].append(row)
        for row in new_rows: new_groups[key_of(row, columns)].append(row)
        if Counter({k: len(v) for k, v in old_groups.items()}) != Counter({k: len(v) for k, v in new_groups.items()}):
            raise ValueError("Full vote/identity key multiset drift; office-only repair refused")
        ambiguous_keys = {k for k in old_groups if len(old_groups[k]) != 1 or len(new_groups[k]) != 1}
        ambiguous_old = [row for k in ambiguous_keys for row in old_groups[k]]
        ambiguous_new = [row for k in ambiguous_keys for row in new_groups[k]]
        def projected_equal(actual, expected):
            if len(actual) != len(expected): return False
            if not expected: return True
            names = list(expected[0])
            return sorted(encode([plain(row[name]) for name in names]) for row in actual) == sorted(encode([plain(row[name]) for name in names]) for row in expected)
        # Python numeric equality accepts SQL 1.0 versus audit JSON 1 without
        # changing values; canonical comparison keys still retain multiplicity.
        def numeric_projection(actual, expected):
            def normalized(row):
                return {k: int(v) if isinstance(v, float) and v.is_integer() else v for k, v in row.items()}
            if not expected: return not actual
            names = expected[0].keys()
            return projected_equal([normalized({k: r[k] for k in names}) for r in actual], [normalized(r) for r in expected])
        if not numeric_projection(ambiguous_old, scope["ambiguous_stored"]) or not numeric_projection(ambiguous_new, scope["ambiguous_reparsed"]):
            raise ValueError("Audited ambiguous source rows changed")
        if (len(stored) != scope["stored_rows"] or len(parsed) != scope["reparsed_rows"]
                or len(ambiguous_old) != scope["ambiguous_stored_rows"]
                or len(old_groups) - len(ambiguous_keys) != scope["unique_pairs"]):
            raise ValueError("Audited source cohort counts changed")
        mappings = Counter()
        for match_key in sorted(old_groups, key=str):
            if match_key in ambiguous_keys: continue
            before, fresh = old_groups[match_key][0], new_groups[match_key][0]
            if (before["office"], before["district"]) == (fresh["office"], fresh["district"]): continue
            sheet = sheets[key][fresh["source_sheet"]]
            printed_title = sheet[0][0]
            office, district = _office(printed_title)
            if (office, district) != (fresh["office"], fresh["district"]):
                raise ValueError("Printed contest title does not support staged office/district")
            row_number, column_number = int(fresh["source_row"]), int(fresh["source_column"])
            physical_vote = sheet[row_number - 1][column_number - 1]
            if float(physical_vote) != fresh["votes"]:
                raise ValueError("Physical source cell vote mismatch")
            after = before | {"office": office, "district": district}
            changes.append({"stored_rowid": before["stored_rowid"], "before": before, "after": after,
                "source_file_id": SOURCE_IDS[scope["year"]], "source_member": scope["source_member"],
                "source_sheet": fresh["source_sheet"], "source_row": row_number, "source_column": column_number,
                "printed_title": printed_title, "printed_candidate": fresh["printed_candidate"],
                "printed_precinct": fresh["printed_precinct"]})
            mappings[(before["office"], office, before["district"], district)] += 1
        reviewed_mappings = Counter({(r["office_old"], r["office_new"], r["district_old"], r["district_new"]): r["rows"] for r in scope["changes_by_field"]})
        # Zero changes may be a replay, but requires committed before/after QA
        # below. A partially changed cohort is never silently accepted.
        if mappings and mappings != reviewed_mappings:
            raise ValueError("Office/district change mapping differs from reviewed audit")
        unchanged_ambiguous.extend(ambiguous_old)
        reports.append({"year": scope["year"], "county": scope["county"], "unique_pairs": scope["unique_pairs"],
                        "ambiguous_rows_unchanged": len(ambiguous_old), "changed_rows": sum(mappings.values())})
    expected_count = sum(scope["semantic_change_pairs"] for scope in audit["cohorts"])
    if changes and len(changes) != expected_count:
        raise ValueError("Partial office-label repair refused")
    if not changes:
        previous = connection.execute(f"SELECT evidence_json FROM {QA} WHERE warehouse_object=? AND scope=? ORDER BY rowid DESC LIMIT 1", (TABLE, TARGET)).fetchone()
        if not previous:
            raise ValueError("No pending changes and no committed repair evidence; not a verified replay")
        previous = json.loads(previous[0])
        if previous["audit_sha256"] != AUDIT_SHA256 or len(previous["changes"]) != expected_count:
            raise ValueError("Replay evidence does not identify reviewed repair")
        for change in previous["changes"]:
            cursor = connection.execute(f"SELECT rowid AS stored_rowid,* FROM {TABLE} WHERE rowid=?", (change["stored_rowid"],))
            row = cursor.fetchone()
            if row is None or dict(zip([d[0] for d in cursor.description], row)) != change["after"]:
                raise ValueError("Previously repaired row changed; replay refused")
    return changes, unchanged_ambiguous, reports


def vote_digests(connection, changes=()):
    updates = {change["stored_rowid"]: change["after"] for change in changes}
    original, expected = hashlib.sha256(), hashlib.sha256()
    cursor = connection.execute(f"SELECT rowid,* FROM {TABLE} ORDER BY rowid")
    columns = [d[0] for d in cursor.description]
    count = 0
    for values in cursor:
        count += 1
        raw = encode(values).encode() + b"\n"
        original.update(raw)
        if values[0] in updates:
            replacement = list(values)
            for column in ["office", "district"]:
                replacement[columns.index(column)] = updates[values[0]][column]
            expected.update(encode(replacement).encode() + b"\n")
        else: expected.update(raw)
    return original.hexdigest(), expected.hexdigest(), count


def controls(connection):
    return {table: digest_rows(connection.execute(f"SELECT * FROM {table} ORDER BY rowid")) for table in CONTROLS}


def authorize(action, table, column, database, trigger):
    if action == sqlite3.SQLITE_UPDATE:
        allowed = trigger is None and (table == BUILD or table == TABLE and column in {"office", "district"})
        return sqlite3.SQLITE_OK if allowed else sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_INSERT:
        return sqlite3.SQLITE_OK if trigger is None and table in {BUILD, QA} else sqlite3.SQLITE_DENY
    if action in (sqlite3.SQLITE_DELETE, sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_DROP_TABLE,
                  sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_CREATE_VIEW, sqlite3.SQLITE_DROP_VIEW,
                  sqlite3.SQLITE_CREATE_TRIGGER, sqlite3.SQLITE_DROP_TRIGGER, sqlite3.SQLITE_CREATE_INDEX,
                  sqlite3.SQLITE_DROP_INDEX, sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH):
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def repair(database: Path, *, apply=False, expected_run=None, backup: Path | None = None, root: Path = ROOT):
    if apply and (not expected_run or backup is None): raise ValueError("Apply requires expected run and new backup")
    database = database.resolve()
    if not database.is_file(): raise FileNotFoundError(database)
    if apply:
        backup = backup.resolve()
        if backup == database or backup.exists(): raise FileExistsError("Backup requires a new separate path")
    audit, frames, sheets, hashes = load_sources(root)
    code_paths = [Path(__file__), Path(__file__).with_name("warehouse.py"), Path(__file__).with_name("oe_normalize.py"),
                  Path(__file__).with_name("load_alabama_2022_certified_source.py")]
    code_hashes = {str(path): file_sha256(path) for path in code_paths}
    mode = "rw" if apply else "ro"
    with closing(sqlite3.connect(database.as_uri() + f"?mode={mode}", uri=True)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        if not apply: connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN IMMEDIATE" if apply else "BEGIN")
        try:
            latest = connection.execute(f"SELECT build_run_id FROM {BUILD} ORDER BY rowid DESC LIMIT 1").fetchone()[0]
            if expected_run is not None and latest != expected_run: raise ValueError("Warehouse snapshot changed")
            sources = registered_sources(connection, audit, root)
            changes, ambiguous, reports = stage(connection, audit, frames, sheets)
            report = {"warehouse_status": "dry_run" if changes else "unchanged", "latest_run": latest,
                      "changed_rows": len(changes), "ambiguous_rows_unchanged": len(ambiguous),
                      "cohorts": reports, "source_files": sources, "stale_dependencies": STALE}
            if not apply or not changes:
                connection.rollback()
                return report
            if any(r[0] in {TABLE, BUILD, QA} for r in connection.execute("SELECT tbl_name FROM sqlite_master WHERE type='trigger'")):
                raise ValueError("Owned-table trigger requires separate review")
            before_hash, expected_hash, count = vote_digests(connection, changes)
            control_before = controls(connection)
            counts_before = {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in CONTROLS}
            schema = digest_rows(connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"))
            connection.set_authorizer(authorize)
            backup.parent.mkdir(parents=True, exist_ok=True)
            with backup.open("xb"): pass
            with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as reader, closing(sqlite3.connect(backup)) as destination:
                reader.execute("PRAGMA query_only=ON")
                reader.backup(destination)
                if destination.execute("PRAGMA quick_check").fetchall() != [("ok",)]: raise ValueError("Backup quick_check failed")
                if vote_digests(destination)[0] != before_hash or controls(destination) != control_before:
                    raise ValueError("Backup before-image mismatch")
                if digest_rows(destination.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")) != schema:
                    raise ValueError("Backup schema mismatch")
            registered_sources(connection, audit, root)
            if any(file_sha256(root / path) != digest for path, digest in hashes.items()): raise ValueError("Source/parser evidence changed during repair")
            if any(file_sha256(Path(path)) != digest for path, digest in code_hashes.items()): raise ValueError("Application code changed during repair")
            config = {"expected_run": expected_run, "backup": str(backup), "audit_sha256": AUDIT_SHA256,
                      "source_files": sources, "source_parser_hashes": hashes, "application_code_hashes": code_hashes,
                      "vote_observations_before_sha256": before_hash, "expected_after_sha256": expected_hash,
                      "digest_contract": "SHA256 UTF-8 compact sorted-key JSON arrays of rowid plus every SQLite column, ORDER BY rowid; newline after each row"}
            run = begin_run(connection, TARGET, config)
            for change in changes:
                after = change["after"]
                cursor = connection.execute(f"UPDATE {TABLE} SET office=?,district=? WHERE rowid=? AND office IS ? AND district IS ?",
                    (after["office"], after["district"], change["stored_rowid"], change["before"]["office"], change["before"]["district"]))
                if cursor.rowcount != 1: raise ValueError("Guarded source update did not match one row")
            after_hash, _, after_count = vote_digests(connection)
            if after_hash != expected_hash or after_count != count: raise ValueError("Unexpected source row/column mutation")
            if connection.execute("PRAGMA foreign_key_check").fetchone(): raise ValueError("Foreign key violation")
            evidence = {"audit_sha256": AUDIT_SHA256, "changes": changes, "ambiguous_rows_unchanged": ambiguous,
                        "cohorts": reports, "source_files": sources, "stale_dependencies": STALE,
                        "before_sha256": before_hash, "after_sha256": after_hash, "source_rows": count}
            issue_id = identifier("SOSOFFICE", run)
            connection.execute(f"INSERT INTO {QA} VALUES (?,?,?,?,?,?,?)", (issue_id, run, TABLE, TARGET,
                "office_labels_repaired_dependencies_pending", encode(evidence), utcnow()))
            finish_run(connection, run, {"changed_rows": len(changes), "ambiguous_rows_unchanged": len(ambiguous),
                                        "source_rows": count, "stale_dependencies": STALE})
            for table in CONTROLS:
                prefix = digest_rows(connection.execute(f"SELECT * FROM {table} ORDER BY rowid LIMIT ?", (counts_before[table],)))
                actual = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                if prefix != control_before[table] or actual != counts_before[table] + int(table in {BUILD, QA}):
                    raise ValueError("Prior control/registry rows changed")
            connection.commit()
            return report | {"warehouse_status": "committed", "build_run_id": run, "qa_issue_id": issue_id,
                             "configuration": config, "validation": evidence}
        except BaseException:
            connection.rollback()
            raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=database_path())
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-run")
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args(argv)
    report = repair(args.database, apply=args.apply, expected_run=args.expected_run, backup=args.backup)
    if "validation" in report:
        report["validation"] = {key: value for key, value in report["validation"].items()
                                if key not in {"changes", "ambiguous_rows_unchanged"}}
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
