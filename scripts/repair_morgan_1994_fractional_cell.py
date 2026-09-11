"""Apply the owner-adjudicated integer reading of the Morgan 1994 Attorney General cell.

The registered 1994 SOS workbook ``94g-prec/MORGAN.XLS`` prints ``144.4`` at sheet
``Morgan`` row 48, column 11 (precinct 26001, ballot code AG2, Sessions R).  The
sheet's own reported county total (K52 = 21,571) is consistent only with 144;
its formula total (K53 = 21,571.4) merely re-adds the printed fraction.  Every
consumer refuses fractional reported counts, so the cell blocks regeneration of
the historical compatibility features.

On 2026-09-10 the owner adjudicated the reported count as 144.  This script
records that adjudication in ``warehouse_manual_adjudication`` and applies it as
a guarded correction to the single ``vote_observations`` row, retaining the
before-image, the raw workbook hashes and the prior review in
``qa_warehouse_source_repair``.  The raw workbook is never touched.  Nothing is
rebuilt here; downstream artifacts remain stale until their producers rerun.

Dry run (default) stages the proposal read-only.  ``--apply`` requires the exact
latest warehouse run and a new separate backup path, mirroring
``repair_alabama_canonical_certified_totals.py``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from source_vote_quality import require_reported_vote_quality
from warehouse import ROOT, begin_run, database_path, file_sha256, finish_run, utcnow

TARGET = "morgan_1994_fractional_cell_adjudication"
OBSERVATIONS = "vote_observations"
ADJUDICATION = "warehouse_manual_adjudication"
BUILD = "warehouse_build_run"
REPAIR = "qa_warehouse_source_repair"
OWNED_INSERT = {ADJUDICATION, BUILD, REPAIR}
CONTROL_TABLES = (BUILD, REPAIR, ADJUDICATION, "warehouse_source_file", "warehouse_table_registry",
                  "warehouse_schema_version", "canonical_candidates")
ADJUDICATION_ID = "ADJ-1994-MORGAN-26001-AG2-K48"
PRIOR_REVIEW = "WQA-04-fractional-evidence"
AUDIT = "project_docs/audits/MORGAN_1994_FRACTIONAL_CELL_QUARANTINE_2026_09_10.md"
CELL = {
    "source": "alabama_sos", "year": 1994, "county_key": "MORGAN", "precinct_key": "26001",
    "office": "Attorney General", "candidate_key": "SESSIONS", "party_norm": "R",
    "source_file": "94g-prec/MORGAN.XLS", "source_sheet": "Morgan", "source_row": 48, "source_column": 11,
    "ballot_code": "AG2", "source_file_id": "SRC-E64FFC4299ED54CB2D3A",
}
REPORTED = 144.4
ADJUDICATED = 144.0
EVIDENCE = {
    "reported_cell": "K48", "reported_value": REPORTED,
    "reported_county_total_cell": "K52", "reported_county_total": 21571,
    "calculated_county_total_cell": "K53", "calculated_county_total": 21571.4,
    "integer_cells_in_column": 45, "fractional_cells_in_column": 1,
    "raw_member_sha256": "e00a9c487b38490a9e6d97c2e85b8f2d3dd07d6e5a2cd3d4eb102d70c30a7b39",
    "raw_archive_sha256": "94512391c389c45d2899f06686484790adaf4c99fa638b217e31f54652c55097",
    "statewide_effect_votes": 0.4, "max_district_effect_pp": 0.006414,
}
RATIONALE = (
    "The provider's own reported county total K52 (21,571) equals the column's 45 integer cells "
    "(21,427) plus 144; the formula total K53 (21,571.4) simply re-adds the printed fraction. "
    "A vote count cannot be fractional; 144.4 is read as a keying artifact of the reported count 144. "
    "No second provider or errata exists; the raw workbook and this before-image are retained."
)


def digest_rows(rows) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(json.dumps(row, default=str).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def cell_predicate() -> tuple[str, tuple]:
    keys = ["source", "year", "county_key", "precinct_key", "office", "candidate_key", "party_norm",
            "source_file", "source_sheet", "source_row", "source_column", "source_file_id"]
    return " AND ".join(f"{key}=?" for key in keys), tuple(CELL[key] for key in keys)


def locate(connection) -> list[dict]:
    where, params = cell_predicate()
    columns = [row[1] for row in connection.execute(f"PRAGMA table_info({OBSERVATIONS})")]
    rows = connection.execute(
        f"SELECT rowid, * FROM {OBSERVATIONS} WHERE {where}", params).fetchall()
    return [dict(zip(["rowid", *columns], row)) for row in rows]


def stage(connection) -> dict:
    """Locate the cell and describe the proposal read-only."""
    rows = locate(connection)
    if len(rows) != 1:
        raise ValueError(f"Expected exactly one Morgan 1994 AG2 observation, found {len(rows)}")
    row = rows[0]
    fractional = connection.execute(
        f"SELECT COUNT(*) FROM {OBSERVATIONS} WHERE votes <> CAST(votes AS INTEGER)").fetchone()[0]
    prior = connection.execute(
        f"SELECT issue_id, status FROM {REPAIR} WHERE issue_id=?", (PRIOR_REVIEW,)).fetchone()
    existing = connection.execute(
        f"SELECT decision, review_status FROM {ADJUDICATION} WHERE adjudication_id=?", (ADJUDICATION_ID,)).fetchone()
    return {
        "observation": row,
        "fractional_observations_in_table": fractional,
        "prior_review": dict(zip(("issue_id", "status"), prior)) if prior else None,
        "existing_adjudication": dict(zip(("decision", "review_status"), existing)) if existing else None,
        "proposal": {"rowid": row["rowid"], "votes_before": row["votes"], "votes_after": ADJUDICATED},
    }


def authorize(action, table, column, database, trigger):
    if action in (sqlite3.SQLITE_READ, sqlite3.SQLITE_SELECT, sqlite3.SQLITE_FUNCTION):
        return sqlite3.SQLITE_OK
    if trigger:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_INSERT:
        return sqlite3.SQLITE_OK if table in OWNED_INSERT else sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_UPDATE:
        if table == OBSERVATIONS and column == "votes":
            return sqlite3.SQLITE_OK
        if table == BUILD:
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY
    if action in (sqlite3.SQLITE_DELETE, sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_DROP_TABLE,
                  sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_CREATE_VIEW, sqlite3.SQLITE_DROP_VIEW,
                  sqlite3.SQLITE_CREATE_TRIGGER, sqlite3.SQLITE_DROP_TRIGGER, sqlite3.SQLITE_CREATE_INDEX,
                  sqlite3.SQLITE_DROP_INDEX, sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH):
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def counts(connection, tables) -> dict[str, int]:
    available = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return {name: connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            for name in tables if name in available}


def control_snapshot(connection) -> dict[str, str]:
    available = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
    return {name: digest_rows(connection.execute(f'SELECT * FROM "{name}" ORDER BY rowid'))
            for name in CONTROL_TABLES if name in available}


def observations_digest_excluding(connection, rowid: int) -> str:
    return digest_rows(connection.execute(
        f"SELECT rowid, * FROM {OBSERVATIONS} WHERE rowid<>? ORDER BY rowid", (rowid,)))


def repair(database: Path, *, apply: bool = False, expected_run: str | None = None,
           backup: Path | None = None, authorized_by: str | None = None) -> dict:
    database = database.resolve()
    if apply and (not expected_run or backup is None or not authorized_by):
        raise ValueError("Application requires --expected-run, --backup and --authorized-by")
    if not database.is_file():
        raise FileNotFoundError(database)
    report_path = None
    if apply:
        backup = backup.resolve()
        report_path = backup.with_name(backup.name + ".application.json")
        if backup == database or backup.exists() or report_path.exists():
            raise FileExistsError("Backup and application report require new separate paths")
    mode = "rw" if apply else "ro"
    with closing(sqlite3.connect(database.as_uri() + f"?mode={mode}", uri=True)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        if not apply:
            connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN IMMEDIATE" if apply else "BEGIN")
        try:
            latest = connection.execute(f"SELECT build_run_id FROM {BUILD} ORDER BY rowid DESC LIMIT 1").fetchone()
            latest = latest[0] if latest else None
            if expected_run is not None and expected_run != latest:
                raise ValueError(f"Warehouse snapshot changed: expected {expected_run}, found {latest}")
            staged = stage(connection)
            row = staged["observation"]
            if staged["existing_adjudication"] or row["votes"] == ADJUDICATED:
                connection.rollback()
                return {"warehouse_status": "unchanged", "latest_run": latest, "staged": staged}
            if row["votes"] != REPORTED:
                raise ValueError(f"Cell no longer holds the reported value {REPORTED}: {row['votes']}")
            if not apply:
                connection.rollback()
                return {"warehouse_status": "dry_run", "latest_run": latest, "staged": staged}
            if any(r[0] in {OBSERVATIONS, *OWNED_INSERT}
                   for r in connection.execute("SELECT tbl_name FROM sqlite_master WHERE type='trigger'")):
                raise ValueError("Triggers on owned tables require separate review")
            before_controls = control_snapshot(connection)
            before_counts = counts(connection, (OBSERVATIONS, *CONTROL_TABLES))
            before_others = observations_digest_excluding(connection, row["rowid"])
            code_paths = [Path(__file__), Path(__file__).with_name("warehouse.py"),
                          Path(__file__).with_name("source_vote_quality.py")]
            application_code = {str(p.resolve().relative_to(ROOT)).replace("\\", "/"): file_sha256(p)
                                for p in code_paths}
            backup.parent.mkdir(parents=True, exist_ok=True)
            with backup.open("xb"):
                pass
            with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as source, \
                    closing(sqlite3.connect(backup)) as destination:
                source.execute("PRAGMA query_only=ON")
                source.backup(destination)
                if destination.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                    raise ValueError("Backup quick_check failed")
                if control_snapshot(destination) != before_controls:
                    raise ValueError("Separate backup validation failed")
                if locate(destination) != [row]:
                    raise ValueError("Backup does not hold the reported cell")
            if {p: file_sha256(ROOT / p) for p in application_code} != application_code:
                raise ValueError("Application code changed during repair")
            connection.set_authorizer(authorize)
            configuration = {
                "backup": str(backup), "expected_run": expected_run, "cell": CELL,
                "before_controls": before_controls, "before_counts": before_counts,
                "observations_digest_excluding_cell": before_others,
                "application_code_sha256": application_code, "evidence": EVIDENCE,
                "authority": "owner adjudication of the provider's reported integer count (K52) over the printed fraction",
                "authorized_by": authorized_by, "audit": AUDIT, "prior_review": PRIOR_REVIEW,
            }
            run = begin_run(connection, TARGET, configuration)
            timestamp = utcnow()
            connection.execute(
                f"INSERT INTO {ADJUDICATION} (adjudication_id, domain, subject_type, subject_id, decision, rationale, "
                "evidence_locator, review_status, decided_at_utc, supersedes_adjudication_id) VALUES (?,?,?,?,?,?,?,?,?,NULL)",
                (ADJUDICATION_ID, "elections_source", "vote_observation_cell",
                 f"{CELL['source_file_id']}:{CELL['source_file']}:{CELL['source_sheet']}:R{CELL['source_row']}C{CELL['source_column']}",
                 f"reported_count={int(ADJUDICATED)}", RATIONALE,
                 json.dumps({"audit": AUDIT, "prior_review": PRIOR_REVIEW, "build_run_id": run,
                             "authorized_by": authorized_by,
                             "independent_review": "project_docs/audits/MORGAN_1994_ADJUDICATION_REVIEW_2026_09_10.md",
                             **EVIDENCE}, sort_keys=True),
                 "approved", timestamp))
            updated = connection.execute(
                f"UPDATE {OBSERVATIONS} SET votes=? WHERE rowid=? AND votes=?",
                (ADJUDICATED, row["rowid"], REPORTED))
            if updated.rowcount != 1:
                raise ValueError("Guarded observation update mismatch")
            after_rows = locate(connection)
            expected_row = {**row, "votes": ADJUDICATED}
            if after_rows != [expected_row]:
                raise ValueError("Corrected cell does not match the expected after-image")
            if observations_digest_excluding(connection, row["rowid"]) != before_others:
                raise ValueError("Other observations changed")
            remaining = connection.execute(
                f"SELECT COUNT(*) FROM {OBSERVATIONS} WHERE votes <> CAST(votes AS INTEGER)").fetchone()[0]
            require_reported_vote_quality(connection, "source='alabama_sos' AND year=1994")
            details = {
                "before_image": row, "after_image": expected_row, "adjudication_id": ADJUDICATION_ID,
                "authorized_by": authorized_by, "prior_review": PRIOR_REVIEW,
                "remaining_fractional_observations": remaining, "backup": str(backup),
                "stale_inventory": AUDIT,
                "not_rebuilt": ["1994 baseline and context marts", "canonical_cmo_features.csv",
                                "canonical_cmo_candidates.csv", "cmo_v5_races.csv", "cmo_v5_candidates.csv",
                                "alabama_historical_war_v1", "downstream pages and forecast"],
                "report_status": "database commit evidence authoritative; report written after commit",
            }
            connection.execute(
                f"INSERT INTO {REPAIR} VALUES (?,?,?,?,?,?,?)",
                ("WQA-04-fractional-adjudicated-" + run, run, OBSERVATIONS, "1994/MORGAN/26001/AG2",
                 "repaired_with_adjudication", json.dumps(details, sort_keys=True, default=str), timestamp))
            after_counts = counts(connection, (OBSERVATIONS, *CONTROL_TABLES))
            expected_deltas = {BUILD: 1, REPAIR: 1, ADJUDICATION: 1}
            for table, count in before_counts.items():
                if after_counts[table] != count + expected_deltas.get(table, 0):
                    raise ValueError(f"Unexpected row-count change: {table}")
            for table in (BUILD, REPAIR, ADJUDICATION):
                preserved = digest_rows(connection.execute(
                    f'SELECT * FROM "{table}" ORDER BY rowid LIMIT ?', (before_counts[table],)))
                if preserved != before_controls[table]:
                    raise ValueError(f"Prior control rows changed: {table}")
            for table, digest in before_controls.items():
                if table in (BUILD, REPAIR, ADJUDICATION):
                    continue
                if digest_rows(connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid')) != digest:
                    raise ValueError(f"Unowned table changed: {table}")
            if connection.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("Foreign key violation")
            finish_run(connection, run, details)
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
    report = {"warehouse_status": "committed", "build_run_id": run, "latest_run_before": latest,
              "configuration": configuration, "validation": details}
    try:
        with report_path.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(report, indent=2, default=str) + "\n")
        report["report_status"] = "written"
    except OSError as exc:
        report["report_status"] = "failed_after_commit"
        report["report_error"] = str(exc)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=database_path())
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-run")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--authorized-by", help="Owner authorization reference recorded with the adjudication")
    args = parser.parse_args(argv)
    result = repair(args.database, apply=args.apply, expected_run=args.expected_run,
                    backup=args.backup, authorized_by=args.authorized_by)
    print(json.dumps(result, indent=2, default=str))
    return 1 if result.get("report_status") == "failed_after_commit" else 0


if __name__ == "__main__":
    raise SystemExit(main())
