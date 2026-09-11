"""Fill uniquely evidenced, NULL source-cell locators; never change source facts.

Default is read-only. Apply requires an expected latest run and a new backup.
Original ingest build_run_id remains untouched; repair evidence has its own run.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

from repair_sos_contest_offices import (
    AUDIT_SHA256, BUILD, CONTROLS, QA, SOURCE_IDS, TABLE, controls, key_of,
    load_sources, plain, registered_sources,
)
from load_alabama_2022_certified_source import digest_rows, encode, identifier
from warehouse import ROOT, begin_run, database_path, file_sha256, finish_run, utcnow

TARGET = "sos_unique_source_cell_lineage"
FIELDS = ("source_file", "source_sheet", "source_row", "source_column", "source_file_id")
EXPECTED = {(2010, "GENEVA"): (1551, 1549, 2), (2012, "MORGAN"): (2538, 2534, 4)}
LIMITATIONS = "Six ambiguous observations remain unresolved. Cached/exported physical-provenance consumers require scoped refresh/review; no numeric invalidation is implied. No ingest-run reconstruction, source adjudication, consumer rebuild or publication certification."


def rows(connection, sql, parameters=()):
    cursor = connection.execute(sql, parameters)
    names = [d[0] for d in cursor.description]
    return [dict(zip(names, values)) for values in cursor]


def stage(connection, audit, frames, sheets):
    columns = audit["comparison_key"] + ["office", "district"]
    changes, matched, unresolved, reports = [], [], [], []
    if set(frames) != set(EXPECTED):
        raise ValueError("Unexpected source cohort universe")
    for scope in audit["cohorts"]:
        cohort = scope["year"], scope["county"].upper()
        old = rows(connection, f"SELECT rowid AS stored_rowid,* FROM {TABLE} WHERE year=? AND county_key=? AND source='alabama_sos' ORDER BY rowid", cohort)
        fresh = [{k: plain(v) for k, v in r.items()} for r in frames[cohort].to_dict("records")]
        old_groups, fresh_groups = defaultdict(list), defaultdict(list)
        for row in old: old_groups[key_of(row, columns)].append(row)
        for row in fresh: fresh_groups[key_of(row, columns)].append(row)
        if Counter({k: len(v) for k, v in old_groups.items()}) != Counter({k: len(v) for k, v in fresh_groups.items()}):
            raise ValueError("Full source key multiset drift")
        unique = sum(len(v) == 1 for v in old_groups.values())
        if (len(old), unique, len(old) - unique) != EXPECTED[cohort] or len(fresh) != scope["reparsed_rows"] or len(old) != scope["stored_rows"]:
            raise ValueError("Reviewed cohort counts changed")
        physical = set()
        for row in fresh:
            locator = tuple(row[k] for k in FIELDS[:4])
            if any(v is None for v in locator) or locator in physical:
                raise ValueError("Missing or duplicate physical source cell")
            physical.add(locator)
            if locator[0] != scope["source_member"]:
                raise ValueError("Source member mismatch")
            for field in ("source_row", "source_column"):
                if isinstance(row[field], bool) or not isinstance(row[field], (int, float)) or row[field] < 1 or int(row[field]) != row[field]:
                    raise ValueError("Invalid one-based cell locator")
            sheet = sheets[cohort][row["source_sheet"]]
            cell = sheet[int(row["source_row"]) - 1][int(row["source_column"]) - 1]
            if cell is None or isinstance(cell, bool) or float(cell) != row["votes"]:
                raise ValueError("Physical cell differs from parsed votes")
        for key in sorted(old_groups, key=str):
            existing, candidates = old_groups[key], fresh_groups[key]
            if len(existing) != 1:
                # Compare against the pinned audit's unresolved subset, not row order.
                for row in existing:
                    evidence = [r for r in scope["ambiguous_stored"] if r["stored_rowid"] == row["stored_rowid"]]
                    if len(evidence) != 1 or any(row[k] != v for k, v in evidence[0].items()):
                        raise ValueError("Unresolved stored row differs from reviewed audit")
                    if any(row[k] is not None for k in FIELDS):
                        raise ValueError("Unresolved row already has unaudited lineage")
                for row in candidates:
                    if not any(all(row[k] == v for k, v in r.items()) for r in scope["ambiguous_reparsed"]):
                        raise ValueError("Unresolved physical alternatives changed")
                unresolved.append({"stored_rows": existing, "candidate_cells": candidates})
                continue
            before, source = existing[0], candidates[0]
            if any(before[k] != source[k] for k in ("county", "precinct", "candidate")):
                raise ValueError("Printed display identity differs; lineage match refused")
            values = {k: source[k] for k in FIELDS[:4]} | {"source_file_id": SOURCE_IDS[scope["year"]]}
            values.update(source_row=int(values["source_row"]), source_column=int(values["source_column"]))
            after = before | values
            evidence = {"stored_rowid": before["stored_rowid"], "before": before, "after": after,
                        "printed_title": plain(sheets[cohort][source["source_sheet"]][0][0]),
                        "printed_precinct": source["printed_precinct"], "printed_candidate": source["printed_candidate"]}
            matched.append(evidence)
            if all(before[k] is None for k in FIELDS):
                changes.append(evidence)
            elif any(before[k] != values[k] for k in FIELDS):
                raise ValueError("Non-NULL or partial lineage conflict")
        reports.append({"year": cohort[0], "county": cohort[1], "rows": len(old), "unique_pairs": unique, "unresolved_rows": len(old) - unique})
    if len(matched) != sum(v[1] for v in EXPECTED.values()):
        raise ValueError("Incomplete source cohort universe")
    if changes and len(changes) != len(matched):
        raise ValueError("Partial repair is not a verified replay")
    if not changes:
        prior = connection.execute(f"SELECT evidence_json FROM {QA} WHERE warehouse_object=? AND scope=? ORDER BY rowid DESC LIMIT 1", (TABLE, TARGET)).fetchone()
        if not prior:
            raise ValueError("No committed evidence for replay")
        prior = json.loads(prior[0])
        if prior["audit_sha256"] != AUDIT_SHA256 or len(prior["changes"]) != len(matched):
            raise ValueError("Replay evidence mismatch")
        if {r["stored_rowid"]: r["after"] for r in prior["changes"]} != {r["stored_rowid"]: r["after"] for r in matched} or prior["unresolved"] != unresolved:
            raise ValueError("Previously repaired rows changed")
    return changes, unresolved, reports


def vote_digests(connection, changes=()):
    updates = {r["stored_rowid"]: r["after"] for r in changes}
    before, after, count = hashlib.sha256(), hashlib.sha256(), 0
    cursor = connection.execute(f"SELECT rowid,* FROM {TABLE} ORDER BY rowid")
    columns = [d[0] for d in cursor.description]
    for values in cursor:
        count += 1
        before.update(encode(values).encode() + b"\n")
        expected = list(values)
        if values[0] in updates:
            for field in FIELDS: expected[columns.index(field)] = updates[values[0]][field]
        after.update(encode(expected).encode() + b"\n")
    return before.hexdigest(), after.hexdigest(), count


def authorize(action, table, column, database, trigger):
    if action == sqlite3.SQLITE_UPDATE:
        return sqlite3.SQLITE_OK if trigger is None and (table == BUILD or table == TABLE and column in FIELDS) else sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_INSERT:
        return sqlite3.SQLITE_OK if trigger is None and table in {BUILD, QA} else sqlite3.SQLITE_DENY
    if action in (sqlite3.SQLITE_DELETE, sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_ALTER_TABLE,
                  sqlite3.SQLITE_CREATE_VIEW, sqlite3.SQLITE_DROP_VIEW, sqlite3.SQLITE_CREATE_TRIGGER, sqlite3.SQLITE_DROP_TRIGGER,
                  sqlite3.SQLITE_CREATE_INDEX, sqlite3.SQLITE_DROP_INDEX, sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH):
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
    code = {str(path): file_sha256(path) for path in [Path(__file__), *[Path(__file__).with_name(n) for n in
            ("repair_sos_contest_offices.py", "load_alabama_2022_certified_source.py", "warehouse.py")]]}
    with closing(sqlite3.connect(database.as_uri() + ("?mode=rw" if apply else "?mode=ro"), uri=True)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        if not apply: connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN IMMEDIATE" if apply else "BEGIN")
        try:
            latest = connection.execute(f"SELECT build_run_id FROM {BUILD} ORDER BY rowid DESC LIMIT 1").fetchone()[0]
            if expected_run is not None and latest != expected_run: raise ValueError("Warehouse snapshot changed")
            sources = registered_sources(connection, audit, root)
            changes, unresolved, cohorts = stage(connection, audit, frames, sheets)
            report = {"warehouse_status": "dry_run" if changes else "unchanged", "latest_run": latest,
                      "changed_rows": len(changes), "unresolved_rows": sum(len(r["stored_rows"]) for r in unresolved),
                      "cohorts": cohorts, "source_files": sources, "limitations": LIMITATIONS}
            if not apply or not changes:
                connection.rollback()
                return report
            if any(r[0] in {TABLE, BUILD, QA} for r in connection.execute("SELECT tbl_name FROM sqlite_master WHERE type='trigger'")):
                raise ValueError("Owned-table trigger requires review")
            before, expected, count = vote_digests(connection, changes)
            control_before = controls(connection)
            counts = {t: connection.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in CONTROLS}
            schema_sql = "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
            schema = digest_rows(connection.execute(schema_sql))
            connection.set_authorizer(authorize)
            backup.parent.mkdir(parents=True, exist_ok=True)
            with backup.open("xb"): pass
            with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as reader, closing(sqlite3.connect(backup)) as destination:
                reader.execute("PRAGMA query_only=ON")
                reader.backup(destination)
                if destination.execute("PRAGMA quick_check").fetchall() != [("ok",)]: raise ValueError("Backup quick_check failed")
                if vote_digests(destination)[0] != before or controls(destination) != control_before or digest_rows(destination.execute(schema_sql)) != schema:
                    raise ValueError("Backup before-image mismatch")
            registered_sources(connection, audit, root)
            if any(file_sha256(root / p) != h for p, h in hashes.items()) or any(file_sha256(Path(p)) != h for p, h in code.items()):
                raise ValueError("Source/parser/application hash changed")
            config = {"expected_run": expected_run, "backup": str(backup), "audit_sha256": AUDIT_SHA256,
                      "source_parser_hashes": hashes, "application_code_hashes": code, "source_files": sources,
                      "before_sha256": before, "expected_after_sha256": expected,
                      "digest_contract": "SHA256 UTF-8 compact JSON array of rowid plus all SQLite columns ordered by rowid, newline per row"}
            run = begin_run(connection, TARGET, config)
            for change in changes:
                values = [change["after"][k] for k in FIELDS]
                cursor = connection.execute(f"UPDATE {TABLE} SET " + ",".join(f"{k}=?" for k in FIELDS) + " WHERE rowid=? AND " + " AND ".join(f"{k} IS NULL" for k in FIELDS), values + [change["stored_rowid"]])
                if cursor.rowcount != 1: raise ValueError("NULL-only update did not match exactly one row")
            after, _, actual_count = vote_digests(connection)
            if after != expected or actual_count != count: raise ValueError("Unexpected source row/column mutation")
            if connection.execute("PRAGMA foreign_key_check").fetchone(): raise ValueError("Foreign key violation")
            evidence = {"audit_sha256": AUDIT_SHA256, "changes": changes, "unresolved": unresolved,
                        "before_sha256": before, "after_sha256": after, "source_rows": count, "cohorts": cohorts,
                        "source_files": sources, "limitations": LIMITATIONS}
            issue = identifier("SOSCELL", run)
            connection.execute(f"INSERT INTO {QA} VALUES (?,?,?,?,?,?,?)", (issue, run, TABLE, TARGET, "unique_lineage_repaired_ambiguities_retained", encode(evidence), utcnow()))
            finish_run(connection, run, report | {"warehouse_status": "validated", "source_rows": count})
            for table in CONTROLS:
                if digest_rows(connection.execute(f"SELECT * FROM {table} ORDER BY rowid LIMIT ?", (counts[table],))) != control_before[table] or connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] != counts[table] + int(table in {BUILD, QA}):
                    raise ValueError("Prior controls or registry changed")
            connection.commit()
            return report | {"warehouse_status": "committed", "build_run_id": run, "qa_issue_id": issue, "configuration": config,
                             "validation": {k: v for k, v in evidence.items() if k not in {"changes", "unresolved"}}}
        except BaseException:
            connection.rollback()
            raise


def apply_legacy_proposal(database: Path, proposal: Path, expected_sha256: str,
                          backup: Path, root: Path = ROOT):
    """Apply a reviewed metadata-only proposal against its exact source snapshot."""
    if file_sha256(proposal) != expected_sha256:
        raise ValueError("Proposal hash mismatch")
    report = json.loads(proposal.read_text(encoding="utf-8"))
    if report.get("schema_version") != 1 or report.get("warehouse_status") != "unchanged":
        raise ValueError("Not a read-only lineage proposal")
    changes = report["changes"]
    if not changes:
        raise ValueError("Proposal has no eligible changes")
    rowids = [change["stored_rowid"] for change in changes]
    if len(rowids) != len(set(rowids)):
        raise ValueError("Repeated proposed row ID")
    if any(set(change["before"]) != set(FIELDS) or set(change["after"]) != set(FIELDS)
           for change in changes):
        raise ValueError("Proposal may change only physical provenance")
    if any(change["before"][field] is not None and change["before"][field] != change["after"][field]
           for change in changes for field in FIELDS):
        raise ValueError("Proposal overwrites existing provenance")
    database, backup = database.resolve(), backup.resolve()
    if backup == database or backup.exists():
        raise FileExistsError("Backup requires a new separate path")
    code_paths = [Path(__file__).resolve(), *[Path(__file__).with_name(name).resolve() for name in
                  ("stage_legacy_source_lineage.py", "warehouse.py", "load_alabama_2022_certified_source.py",
                   "repair_sos_contest_offices.py", "sos_precinct.py", "oe_normalize.py", "build_election_database.py")]]
    if set(report["code_hashes"]) != {str(path) for path in code_paths}:
        raise ValueError("Incomplete staged code hashes")
    def verify_files():
        if file_sha256(proposal) != expected_sha256:
            raise ValueError("Proposal changed during application")
        for path, digest in report["code_hashes"].items():
            if file_sha256(Path(path)) != digest:
                raise ValueError(f"Staged code changed: {path}")
        for source in report["sources"]:
            if file_sha256(root / source["local_path"]) != source["sha256"]:
                raise ValueError("Registered source bytes changed")
        review = report.get("office_review")
        if review and file_sha256(Path(review["path"])) != review["sha256"]:
            raise ValueError("Office review evidence changed")
    verify_files()
    with closing(sqlite3.connect(database.as_uri()+"?mode=rw", uri=True)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("BEGIN IMMEDIATE")
        try:
            latest = connection.execute(f"SELECT build_run_id FROM {BUILD} ORDER BY rowid DESC LIMIT 1").fetchone()[0]
            if latest != report["latest_run"]:
                raise ValueError("Warehouse snapshot changed")
            schema_sql = "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
            if digest_rows(connection.execute(schema_sql)) != report["schema_sha256"]:
                raise ValueError("Warehouse schema changed")
            source_sql = "SELECT rowid,* FROM vote_observations WHERE source='alabama_sos' AND year IN (1998,2004) ORDER BY rowid"
            if digest_rows(connection.execute(source_sql)) != report["source_rows_sha256"]:
                raise ValueError("Staged source rows changed")
            for source in report["sources"]:
                current = connection.execute("SELECT local_path,sha256 FROM warehouse_source_file WHERE source_file_id=?",
                                             (source["source_file_id"],)).fetchall()
                if current != [(source["local_path"], source["sha256"])]:
                    raise ValueError("Source registry disagrees with proposal")
            if any(row[0] in {TABLE, BUILD, QA} for row in connection.execute("SELECT tbl_name FROM sqlite_master WHERE type='trigger'")):
                raise ValueError("Owned-table trigger requires review")
            # Confirm every target's substantive before-image, including original labels.
            from stage_legacy_source_lineage import CORE
            for change in changes:
                current = connection.execute(f"SELECT {','.join(CORE)} FROM {TABLE} WHERE rowid=?",
                                             (change["stored_rowid"],)).fetchone()
                if current is None or list(current) != change["source_key"]:
                    raise ValueError("Proposed row does not match original substantive fields")
            before, expected, count = vote_digests(connection, changes)
            control_before = controls(connection)
            counts = {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in CONTROLS}
            backup.parent.mkdir(parents=True, exist_ok=True)
            with backup.open("xb"):
                pass
            with closing(sqlite3.connect(database.as_uri()+"?mode=ro", uri=True)) as reader, closing(sqlite3.connect(backup)) as destination:
                reader.execute("PRAGMA query_only=ON")
                reader.backup(destination)
                if destination.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                    raise ValueError("Backup integrity failed")
                if vote_digests(destination)[0] != before or controls(destination) != control_before or digest_rows(destination.execute(schema_sql)) != report["schema_sha256"]:
                    raise ValueError("Backup before-image mismatch")
            verify_files()
            connection.set_authorizer(authorize)
            config = {"proposal": str(proposal.resolve()), "proposal_sha256": expected_sha256,
                      "backup": str(backup), "expected_run": latest, "code_hashes": report["code_hashes"],
                      "source_files": report["sources"], "before_sha256": before, "expected_after_sha256": expected}
            run = begin_run(connection, "sos_legacy_source_cell_lineage", config)
            for change in changes:
                cursor = connection.execute(f"UPDATE {TABLE} SET "+",".join(f"{field}=?" for field in FIELDS)
                    + " WHERE rowid=? AND source='alabama_sos' AND year IN (1998,2004) AND "
                    + " AND ".join(f"{field} IS ?" for field in FIELDS),
                    [change["after"][field] for field in FIELDS]+[change["stored_rowid"]]
                    +[change["before"][field] for field in FIELDS])
                if cursor.rowcount != 1:
                    raise ValueError("Provenance before-image update did not match exactly one row")
            after, _, actual_count = vote_digests(connection)
            if after != expected or actual_count != count:
                raise ValueError("Unexpected source mutation")
            if connection.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("Foreign key violation")
            issue = identifier("SOSLEGACYCELL", run)
            evidence = {"proposal_sha256": expected_sha256, "proposal_path": str(proposal.resolve()),
                        "backup": str(backup), "changed_rows": len(changes), "cohorts": report["cohorts"],
                        "before_sha256": before, "after_sha256": after, "source_rows": count,
                        "limitations": "Metadata only. Source facts, source-grain ambiguity and original ingest IDs unchanged. Prior analytical outputs not revalidated."}
            connection.execute(f"INSERT INTO {QA} VALUES (?,?,?,?,?,?,?)",
                               (issue, run, TABLE, "legacy_1998_2004_source_locators", "metadata_repaired_review_scopes_retained", encode(evidence), utcnow()))
            finish_run(connection, run, evidence)
            for table in CONTROLS:
                if digest_rows(connection.execute(f"SELECT * FROM {table} ORDER BY rowid LIMIT ?", (counts[table],))) != control_before[table] or connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] != counts[table]+int(table in {BUILD, QA}):
                    raise ValueError("Prior controls or registry changed")
            verify_files()
            connection.commit()
            return {"warehouse_status": "committed", "build_run_id": run, "qa_issue_id": issue, **evidence}
        except BaseException:
            connection.rollback()
            raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=database_path())
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-run")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--legacy-proposal", type=Path)
    parser.add_argument("--proposal-sha256")
    args = parser.parse_args(argv)
    if args.legacy_proposal:
        if not args.apply or not args.proposal_sha256 or not args.backup:
            parser.error("Legacy proposal application requires --apply, --proposal-sha256 and --backup")
        result = apply_legacy_proposal(args.database, args.legacy_proposal, args.proposal_sha256, args.backup)
    else:
        result = repair(args.database, apply=args.apply, expected_run=args.expected_run, backup=args.backup)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
