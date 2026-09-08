"""Stage or append reviewed Alabama 2022 source observations, never promote them.

Default execution is read-only. Application needs an explicit snapshot and new
backup path. JSON is emitted to stdout for the coordinator to retain; this tool
does not write exports, register sources, or rebuild canonical/model tables.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import math
from pathlib import Path
import sqlite3

import pandas as pd

import alabama_2022_official_results as adapter
from warehouse import ROOT, begin_run, database_path, file_sha256, finish_run, utcnow

AUDIT = Path("project_docs/audits/ALABAMA_2022_CERTIFIED_SOURCE_RECONCILIATION.json")
MANIFEST = Path("data/raw/alabama_elections_and_geography/2022_general_certified_canvass.manifest.json")
AUDIT_SHA256 = "263a02e45aa6780f86ffa1ced3058a030fc78bf02412d73963efbd6e10373475"
FAMILY = "alabama_sos_certified_canvass"
PARSER = "alabama_2022_official_results.certified_canvass"
SETS = "source_southern_legislative_observation_set"
CANDIDATES = "source_southern_legislative_candidate_result"
QA = "qa_southern_legislative_source_reconciliation"
BUILD = "warehouse_build_run"
REPAIR = "qa_warehouse_source_repair"
OWNED = {SETS, CANDIDATES, QA, BUILD, REPAIR}
SNAPSHOT_TABLES = sorted(OWNED | {"warehouse_source_file"})
KEY = ["chamber", "district", "party", "candidate_norm", "category"]


def encode(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def identifier(prefix: str, *parts) -> str:
    return prefix + "-" + hashlib.sha256(encode(parts).encode()).hexdigest()[:24].upper()


def digest_rows(rows) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(encode(tuple(row)).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def snapshot(connection) -> dict:
    return {table: digest_rows(connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid'))
            for table in SNAPSHOT_TABLES} | {
        "schema": digest_rows(connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"))}


def verified_evidence(root: Path = ROOT):
    """Reconcile fresh source parsing against the exact reviewed immutable audit."""
    audit_path, manifest_path = root / AUDIT, root / MANIFEST
    if file_sha256(audit_path) != AUDIT_SHA256:
        raise ValueError("Reviewed reconciliation audit hash mismatch")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if audit["canvass_source"] != manifest or audit["status"] != "matched_certified_contest_totals":
        raise ValueError("Canvass manifest/audit disagreement")
    for path, digest in audit["code_sha256"].items():
        if file_sha256(root / path) != digest:
            raise ValueError(f"Audited adapter code changed: {path}")
    source_path = root / manifest["local_path"]
    if file_sha256(source_path) != manifest["sha256"] or source_path.stat().st_size != manifest["size_bytes"]:
        raise ValueError("Canvass source hash/size mismatch")
    cells, precinct = adapter.load_official_cells(root)
    if precinct != audit["precinct_source"]:
        raise ValueError("Precinct source/member evidence changed")
    certified, metadata = adapter.load_certified_canvass(source_path)
    if metadata["sha256"] != manifest["sha256"]:
        raise ValueError("Fresh canvass parser source mismatch")
    reconciled = adapter.reconcile_canvass(cells, certified)
    if not reconciled.reconciliation_status.eq("matched_certified_total").all():
        raise ValueError("Fresh source reconciliation contains review rows")
    # The reviewed JSON uses pandas' ten-decimal float serialization. Compare
    # every audited locator/count/value, not just aggregate sums or input order.
    fresh = json.loads(reconciled[audit["columns"]].to_json(orient="values"))
    key_columns = [audit["columns"].index(key) for key in KEY]
    def keyed(rows):
        result = {tuple(row[i] for i in key_columns): row for row in rows}
        if len(result) != len(rows):
            raise ValueError("Duplicate reviewed source keys")
        return result
    if keyed(fresh) != keyed(audit["rows"]):
        raise ValueError("Fresh source rows differ from reviewed audit")
    summary = {"contests": len(reconciled[["chamber", "district"]].drop_duplicates()),
               "named_candidates": int(reconciled.category.eq("named_candidate").sum()),
               "write_in_totals": int(reconciled.category.eq("write_in").sum()),
               "named_votes": int(reconciled.loc[reconciled.category.eq("named_candidate"), "certified_votes"].sum()),
               "write_in_votes": int(reconciled.loc[reconciled.category.eq("write_in"), "certified_votes"].sum()),
               "unknown_cells_retained": int(reconciled.unknown_cells.sum()), "review_rows": 0}
    if summary != audit["summary"] or summary["contests"] != 140 or len(reconciled) != 351:
        raise ValueError("Reviewed cohort coverage mismatch")
    return reconciled, cells, manifest, {
        "audit_sha256": AUDIT_SHA256, "manifest_sha256": file_sha256(manifest_path),
        "adapter_code_sha256": audit["code_sha256"], "precinct_source": precinct,
        "canvass_source": manifest, "summary": summary,
    }


def registered_sources(connection, evidence: dict, root: Path = ROOT) -> dict:
    result = {}
    for metadata in [evidence["canvass_source"], evidence["precinct_source"]]:
        path = metadata.get("local_path", metadata.get("source_path"))
        rows = connection.execute("SELECT source_file_id,local_path,sha256 FROM warehouse_source_file WHERE local_path=?", (path,)).fetchall()
        if len(rows) != 1 or rows[0][2] != metadata["sha256"] or file_sha256(root / path) != rows[0][2]:
            raise ValueError(f"Missing or inconsistent registered source: {path}")
        if "source_file_id" in metadata and rows[0][0] != metadata["source_file_id"]:
            raise ValueError("Registered source identity mismatch")
        result[rows[0][0]] = {"local_path": rows[0][1], "sha256": rows[0][2]}
    return result


def cohort(reconciled: pd.DataFrame, cells: pd.DataFrame, manifest: dict, evidence: dict,
           run: str, timestamp: str) -> dict[str, list[dict]]:
    """Construct source rows with stable artifact/physical-cell identifiers."""
    if reconciled.duplicated(KEY).any() or not reconciled.reconciliation_status.eq("matched_certified_total").all():
        raise ValueError("Duplicate or unvalidated staged source keys")
    if any(pd.isna(value) or isinstance(value, bool) or not math.isfinite(float(value))
           or float(value) < 0 or not float(value).is_integer() for value in reconciled.certified_votes):
        raise ValueError("Malformed certified vote value")
    expected = {(chamber, district) for chamber, n in [("house", 105), ("senate", 35)] for district in range(1, n + 1)}
    if set(zip(reconciled.chamber, reconciled.district)) != expected or len(reconciled) != 351:
        raise ValueError("Staged cohort is not the complete reviewed 140/351 source")
    source_id = manifest["source_file_id"]
    result = {SETS: [], CANDIDATES: [], QA: []}
    for (source_chamber, district), group in reconciled.groupby(["chamber", "district"], sort=True):
        chamber = "lower" if source_chamber == "house" else "upper"
        set_id = identifier("AL22SET", source_id, manifest["sha256"], chamber, int(district))
        denominator = int(group.certified_votes.sum())
        if denominator <= 0 or int(group.category.eq("write_in").sum()) != 1:
            raise ValueError("Invalid certified contest denominator/write-in coverage")
        row_evidence = []
        for row in group.sort_values(["canvass_page", "canvass_column"]).to_dict("records"):
            box = [round(float(v), 10) for v in row["canvass_value_bbox"]]
            physical = {"source_file_id": source_id, "sha256": manifest["sha256"],
                        "page": int(row["canvass_page"]), "value_bbox": box}
            candidate_id = identifier("AL22CELL", physical)
            writein = row["category"] == "write_in"
            source_cells = cells[cells.chamber.eq(source_chamber) & cells.district.eq(district)
                                 & cells.category.eq(row["category"]) & cells.candidate_norm.eq(row["candidate_norm"])
                                 & cells.cell_kind.eq("precinct")]
            printed_party = {"D": "DEM", "R": "REP", "L": "LIB", "I": "IND", "O": "NON"}[row["party"]]
            source_cells = source_cells[source_cells.printed_party.str.strip().str.upper().eq(printed_party)]
            if (int(source_cells.votes.notna().sum()) != row["observed_cells"]
                    or int(source_cells.votes.isna().sum()) != row["unknown_cells"]):
                raise ValueError("Physical precinct evidence/missingness mismatch")
            locators = json.loads(source_cells[["source_member", "source_sheet", "source_row", "source_column",
                "county", "precinct", "printed_party", "printed_candidate", "votes", "value_status"]].to_json(orient="records"))
            result[CANDIDATES].append({
                "source_candidate_result_id": candidate_id, "observation_set_id": set_id,
                "candidate_source_id": encode(physical), "candidate_name": row["canvass_printed_candidate"],
                "candidate_name_original": row["canvass_printed_candidate"],
                "party_family": "unknown" if writein else {"D": "democratic", "R": "republican", "L": "other", "I": "independent"}[row["party"]],
                "party_original": None if writein else row["canvass_printed_party"],
                "votes": int(row["certified_votes"]), "vote_share": None,
                "vote_value_status": "observed", "writein_status": "true" if writein else "false",
                "incumbent_status": None, "winner_status": None, "validation_status": "passed", "as_of_utc": timestamp,
            })
            row_evidence.append({"source_candidate_result_id": candidate_id, "physical_canvass_cell": physical,
                "header_text": row["canvass_header_text"], "header_bbox": row["canvass_header_bbox"],
                "header_token": int(row["canvass_header_token"]), "category": row["category"],
                "observed_cells": int(row["observed_cells"]), "unknown_cells": int(row["unknown_cells"]),
                "aggregation_status": row["aggregation_status"], "reconciliation_status": row["reconciliation_status"],
                "precinct_cells": sorted(locators, key=encode)})
        quality = {"promotion_status": "pending_canonical_adoption", "audit_sha256": evidence["audit_sha256"],
            "source_hashes": {"canvass": manifest["sha256"], "precinct": evidence["precinct_source"]["sha256"]},
            "vote_share_denominator": denominator, "denominator_categories": ["named_candidate", "write_in"],
            "unknown_precinct_cells_are_zero": False, "candidate_evidence": row_evidence}
        result[SETS].append({
            "observation_set_id": set_id, "build_run_id": run, "source_file_id": source_id,
            "source_member": None, "provider": manifest["provider"], "source_family": FAMILY, "authority_rank": 10,
            "state_code": "AL", "cycle": 2022, "election_date": "2022-11-08", "election_date_status": "observed",
            "election_stage": "general", "election_stage_original": "General Election",
            "office_code": "SLDL" if chamber == "lower" else "SLDU", "chamber": chamber,
            "district_plan_id": f"AL-2022-{chamber}-reported-unknown-vintage",
            "geography_vintage": manifest["geography_vintage"], "district": str(district), "district_original": str(district),
            "source_coverage": "certified_all_candidate_and_write_in_totals", "contest_status": "unknown",
            "parser_name": PARSER, "quality_flags_json": encode(quality), "validation_status": "review", "as_of_utc": timestamp,
        })
    ids = [row["source_candidate_result_id"] for row in result[CANDIDATES]]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate physical certified cells")
    total = sum(row["votes"] for row in result[CANDIDATES])
    result[QA] = [{"reconciliation_id": identifier("AL22QA", source_id, manifest["sha256"]),
        "build_run_id": run, "source_file_id": source_id, "source_member": None, "state_code": "AL", "cycle": 2022,
        "parser_name": PARSER, "input_rows": len(reconciled), "output_candidate_rows": len(ids),
        "input_votes": total, "output_votes": total, "vote_delta": 0, "unknown_vote_rows": 0,
        "reconciliation_status": "exact", "note": encode({"audit_sha256": evidence["audit_sha256"],
            "unknown_precinct_cells_retained": int(reconciled.unknown_cells.sum()),
            "canonical_adoption": "pending", "counts": evidence["summary"]})}]
    return result


def existing_cohort(connection, expected: dict) -> bool:
    """Replay is a no-op only for an exact cohort, never a partial overwrite."""
    source_id = expected[SETS][0]["source_file_id"]
    queries = {SETS: (f"SELECT * FROM {SETS} WHERE source_family=? OR source_file_id=?", (FAMILY, source_id)),
               CANDIDATES: (f"SELECT c.* FROM {CANDIDATES} c JOIN {SETS} s USING(observation_set_id) WHERE s.source_family=? OR s.source_file_id=?", (FAMILY, source_id)),
               QA: (f"SELECT * FROM {QA} WHERE parser_name=? OR source_file_id=?", (PARSER, source_id))}
    actual = {}
    for table, (query, args) in queries.items():
        cursor = connection.execute(query, args)
        columns = [d[0] for d in cursor.description]
        actual[table] = [dict(zip(columns, row)) for row in cursor]
    if not any(actual.values()):
        return False
    def stable(rows):
        return sorted(encode({k: v for k, v in row.items() if k not in {"build_run_id", "as_of_utc"}}) for row in rows)
    if any(stable(actual[table]) != stable(expected[table]) for table in expected):
        raise ValueError("Existing source cohort conflicts with reviewed append; no overwrite allowed")
    return True


def authorize(action, table, column, database, trigger):
    if action == sqlite3.SQLITE_INSERT:
        return sqlite3.SQLITE_OK if table in OWNED and trigger is None else sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_UPDATE:
        return sqlite3.SQLITE_OK if table == BUILD and trigger is None else sqlite3.SQLITE_DENY
    if action in (sqlite3.SQLITE_DELETE, sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_DROP_TABLE,
                  sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_CREATE_VIEW, sqlite3.SQLITE_DROP_VIEW,
                  sqlite3.SQLITE_CREATE_TRIGGER, sqlite3.SQLITE_DROP_TRIGGER, sqlite3.SQLITE_CREATE_INDEX,
                  sqlite3.SQLITE_DROP_INDEX, sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH):
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def append_source(database: Path, *, apply: bool = False, expected_run: str | None = None,
                  backup: Path | None = None, root: Path = ROOT) -> dict:
    database = database.resolve()
    if apply and (not expected_run or backup is None):
        raise ValueError("Application requires --expected-run and --backup")
    if not database.is_file():
        raise FileNotFoundError(database)
    if apply:
        backup = backup.resolve()
        if backup == database or backup.exists():
            raise FileExistsError("Backup must be a new separate path")
    reconciled, cells, manifest, evidence = verified_evidence(root)
    staged = cohort(reconciled, cells, manifest, evidence, "staged", "staged")
    mode = "rw" if apply else "ro"
    with closing(sqlite3.connect(database.as_uri() + f"?mode={mode}", uri=True)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        if not apply:
            connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN IMMEDIATE" if apply else "BEGIN")
        try:
            sources = registered_sources(connection, evidence, root)
            latest = connection.execute(f"SELECT build_run_id FROM {BUILD} ORDER BY rowid DESC LIMIT 1").fetchone()
            latest = latest[0] if latest else None
            if expected_run is not None and expected_run != latest:
                raise ValueError(f"Warehouse snapshot changed: expected {expected_run}, found {latest}")
            present = existing_cohort(connection, staged)
            report = {"warehouse_status": "unchanged" if present else "dry_run", "latest_run": latest,
                      "source_files": sources, "evidence": evidence,
                      "staged_counts": {table: len(rows) for table, rows in staged.items()}}
            if present or not apply:
                connection.rollback()
                return report
            if any(row[0] in OWNED for row in connection.execute("SELECT tbl_name FROM sqlite_master WHERE type='trigger'")):
                raise ValueError("Owned-table triggers require separate review")
            before = snapshot(connection)
            before_counts = {table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                             for table in SNAPSHOT_TABLES}
            code_paths = [Path(__file__), Path(__file__).with_name("warehouse.py"),
                          Path(__file__).with_name("load_southern_legislative_history_warehouse.py")]
            application_code = {str(path): file_sha256(path) for path in code_paths}
            connection.set_authorizer(authorize)
            backup.parent.mkdir(parents=True, exist_ok=True)
            with backup.open("xb"):
                pass
            with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as source, closing(sqlite3.connect(backup)) as destination:
                source.execute("PRAGMA query_only=ON")
                source.backup(destination)
                if destination.execute("PRAGMA quick_check").fetchall() != [("ok",)] or snapshot(destination) != before:
                    raise ValueError("Separate backup validation failed")
            # Sources can change on disk independently of the database lock.
            registered_sources(connection, evidence, root)
            for path, digest in evidence["adapter_code_sha256"].items():
                if file_sha256(root / path) != digest:
                    raise ValueError("Adapter changed during source application")
            if any(file_sha256(Path(path)) != digest for path, digest in application_code.items()):
                raise ValueError("Application code changed during source application")
            if file_sha256(root / AUDIT) != evidence["audit_sha256"] or file_sha256(root / MANIFEST) != evidence["manifest_sha256"]:
                raise ValueError("Reviewed evidence changed during application")
            config = {"backup": str(backup), "expected_run": expected_run, "before_snapshot": before,
                      "before_counts": before_counts,
                      "source_files": sources, "evidence": evidence,
                      "application_code_sha256": application_code}
            run = begin_run(connection, "alabama_2022_certified_source_append", config)
            timestamp = utcnow()
            for table, rows in staged.items():
                columns = list(rows[0])
                values = [tuple(run if column == "build_run_id" else timestamp if column == "as_of_utc" else row[column]
                                for column in columns) for row in rows]
                connection.executemany(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})", values)
            if not existing_cohort(connection, staged):
                raise ValueError("Appended source cohort not found")
            if connection.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("Foreign key violation")
            details = {"source_counts": report["staged_counts"], "source_reconciliation": evidence["summary"],
                       "canonical_adoption": "pending", "source_set_status": "review",
                       "unchanged": ["canonical identities/results", "outcomes", "allocations", "model outputs", "publications"],
                       "backup": str(backup)}
            connection.execute(f"INSERT INTO {REPAIR} VALUES (?,?,?,?,?,?,?)",
                (identifier("AL22LOAD", run), run, SETS, "Alabama 2022 certified source append only",
                 "source_loaded_pending_adoption", encode(details), timestamp))
            finish_run(connection, run, details)
            deltas = {SETS: len(staged[SETS]), CANDIDATES: len(staged[CANDIDATES]), QA: len(staged[QA]), BUILD: 1, REPAIR: 1}
            for table, count in before_counts.items():
                # UPDATE permission for the new run must not mask modification
                # of prior runs. All before-image rows must survive identically.
                preserved = digest_rows(connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid LIMIT ?', (count,)))
                actual_count = connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                if preserved != before[table] or actual_count != count + deltas.get(table, 0):
                    raise ValueError(f"Append changed prior rows or unexpected counts: {table}")
            connection.commit()
            return report | {"warehouse_status": "committed", "build_run_id": run,
                             "configuration": config, "validation": details}
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
    print(json.dumps(append_source(args.database, apply=args.apply, expected_run=args.expected_run,
                                  backup=args.backup), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
