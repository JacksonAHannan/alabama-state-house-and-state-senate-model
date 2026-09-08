"""Bridge Alabama canonical candidates to certified canvass cells and correct totals.

Default execution is a read-only stage that reports the bridge and the canonical
totals that disagree with the certified canvass.  Application needs an explicit
expected warehouse run and a new backup path.  It creates the bridge table
(schema version 27), corrects only `canonical_candidates.canonical_votes` and the
materialized `canonical_southern_legislative_candidate_election` votes/shares for
the affected contests, and records before-images and stale dependencies.  It
never touches the outcome mart; the preparation loader rebuilds that afterwards.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

import pandas as pd

from alabama_certified_bridge import (
    BRIDGE_COLUMNS, BRIDGE_TABLE, CYCLES, ballot_code_names, build_bridge,
    canonical_rows, certified_rows, encode, native_records, precinct_alignment_2018,
)
from warehouse import ROOT, begin_run, database_path, file_sha256, finish_run, register_table, utcnow

SCHEMA = Path(__file__).with_name("warehouse_alabama_certified_bridge_schema.sql")
CODE_ROOT = Path(__file__).resolve().parents[1]
TARGET = "alabama_certified_canonical_total_repair"
CANONICAL = "canonical_candidates"
MATERIALIZED = "canonical_southern_legislative_candidate_election"
BUILD = "warehouse_build_run"
REPAIR = "qa_warehouse_source_repair"
REGISTRY = "warehouse_table_registry"
VERSION = "warehouse_schema_version"
OWNED_INSERT = {BRIDGE_TABLE, BUILD, REPAIR, REGISTRY}
SNAPSHOT_TABLES = (
    CANONICAL, MATERIALIZED, "source_southern_legislative_observation_set",
    "source_southern_legislative_candidate_result", "warehouse_source_file", BUILD, REPAIR,
    VERSION, REGISTRY, "mart_southern_war_outcome",
)
STALE = [
    "mart_southern_war_outcome Alabama 2018/2022 rows: votes, third-party totals and source_file_id "
    "until load_southern_war_preparation_warehouse.py rebuilds the mart",
    "data/processed/war/race_candidate_results.csv and its producer build_war_database.py still carry "
    "the pre-certified 2018/2022 D/R totals; build_candidate_identity.py would regenerate canonical_candidates "
    "from them and must adopt the certified canvass before any identity rebuild",
    "candidate_alias_match_candidates and candidate_aliases copy canonical_votes at identity-build time "
    "(21 rows now differ by the recorded deltas; identity match statuses unchanged)",
    "data/processed/elections/canonical_cmo_candidates.csv, canonical_cmo_features.csv and "
    "historical_cmo_extension.csv compatibility exports embed the old Alabama 2018/2022 totals",
    "Alabama products consuming canonical 2018/2022 totals (alabama_war_v1, alabama_historical_war_v1, "
    "alabama_war_forecast_v1 bundles) are stale pending their own revalidation; not rebuilt here",
]


def digest_rows(rows) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(encode(tuple(row)).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def snapshot(connection) -> dict[str, str]:
    available = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
    return {name: digest_rows(connection.execute(f'SELECT * FROM "{name}" ORDER BY rowid'))
            for name in SNAPSHOT_TABLES if name in available}


def readiness_snapshot(connection) -> dict[str, str | None]:
    available = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
    return {
        name: digest_rows(connection.execute(
            f"SELECT war_outcome_id,{status} FROM {name} ORDER BY war_outcome_id"
        )) if name in available else None
        for name, status in (("mart_southern_war_training_no_finance", "training_status"),
                             ("mart_southern_war_training_with_finance", "evaluation_status"))
    }


def schema_statements() -> list[str]:
    lines = [line for line in SCHEMA.read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.strip().startswith("--")]
    return [block.strip() for block in "\n".join(lines).split(";") if block.strip()]


def materialized_alabama(connection, cycles) -> pd.DataFrame:
    placeholders = ",".join("?" for _ in cycles)
    return pd.read_sql_query(f"""
        SELECT candidate_result_id, observation_set_id, votes, vote_share
        FROM {MATERIALIZED}
        WHERE state_code='AL' AND source_family='alabama_canonical' AND cycle IN ({placeholders})
        ORDER BY candidate_result_id
    """, connection, params=tuple(cycles))


def stage(connection, root: Path = ROOT, cycles=CYCLES, decoder: dict[str, str] | None = None,
          precinct_alignment: dict | None = None) -> dict:
    """Compute the bridge, the corrections and the materialized-copy updates read-only."""
    certified = certified_rows(connection, cycles)
    present_cycles = tuple(sorted(int(value) for value in certified.cycle.unique())) if not certified.empty else ()
    if present_cycles != tuple(sorted(cycles)):
        raise ValueError(f"Certified canvass sets present for {present_cycles}, required {tuple(sorted(cycles))}")
    canonical = canonical_rows(connection, cycles)
    decoder = ballot_code_names() if decoder is None else decoder
    if precinct_alignment is None:
        precinct_alignment = precinct_alignment_2018(root) if 2018 in cycles else {}
    bridge = build_bridge(canonical, certified, decoder, precinct_alignment)
    corrections = bridge[bridge.correction_status.eq("corrected_to_certified")]
    materialized = materialized_alabama(connection, cycles)
    canonical_votes = dict(zip(canonical.canonical_candidate_id, canonical.canonical_votes))
    if set(materialized.candidate_result_id) != set(canonical.canonical_candidate_id):
        raise ValueError("Materialized Alabama canonical rows do not match canonical_candidates")
    drift = materialized[materialized.candidate_result_id.map(canonical_votes).ne(materialized.votes)]
    if not drift.empty:
        raise ValueError(f"Materialized Alabama votes already differ from canonical_candidates: {len(drift)} rows")
    corrected_votes = {**canonical_votes, **dict(zip(corrections.canonical_candidate_id, corrections.certified_votes))}
    affected_sets = set(materialized[materialized.candidate_result_id.isin(corrections.canonical_candidate_id)].observation_set_id)
    updates = []
    for set_id, group in materialized[materialized.observation_set_id.isin(affected_sets)].groupby("observation_set_id"):
        total = sum(int(corrected_votes[identifier]) for identifier in group.candidate_result_id)
        for identifier in group.candidate_result_id:
            votes = int(corrected_votes[identifier])
            updates.append({"candidate_result_id": identifier, "observation_set_id": set_id,
                            "votes": votes, "vote_share": (votes / total) if total > 0 else None})
    winners = canonical.copy()
    winners["corrected_votes"] = winners.canonical_candidate_id.map(corrected_votes)
    winners["expected_winner"] = winners.corrected_votes.eq(
        winners.groupby(["cycle", "chamber", "district"]).corrected_votes.transform("max")
    ).astype(int)
    flips = winners[winners.expected_winner.ne(winners.winner.astype(int))]
    if not flips.empty:
        raise ValueError(f"Certified correction would change a canonical winner flag: {flips.canonical_candidate_id.tolist()}")
    return {"bridge": bridge, "canonical": canonical, "certified": certified, "corrections": corrections,
            "materialized_updates": updates, "affected_observation_sets": sorted(affected_sets),
            "materialized_before": materialized}


def existing_bridge(connection, bridge: pd.DataFrame) -> bool:
    exists = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (BRIDGE_TABLE,)).fetchone()
    if not exists:
        return False
    current = pd.read_sql_query(f"SELECT * FROM {BRIDGE_TABLE}", connection)
    if current.empty:
        return False
    # A replay stages from already-corrected canonical totals, so correction
    # history legitimately differs; identity, cell, file, method and certified
    # totals must not.  Vote agreement is checked separately by the caller.
    identity = ["bridge_id", "canonical_candidate_id", "cycle", "chamber", "district", "canonical_party",
                "observation_set_id", "source_candidate_result_id", "source_file_id",
                "certified_candidate_name", "match_method", "certified_votes", "review_status"]
    def stable(frame):
        return sorted(encode({k: row[k] for k in identity}) for row in native_records(frame))
    if stable(current) != stable(bridge):
        raise ValueError("Existing Alabama certified bridge conflicts with the staged bridge; no overwrite allowed")
    return True


def source_evidence(connection, root: Path, identifiers) -> dict:
    evidence = {}
    for identifier in sorted(set(identifiers)):
        row = connection.execute("SELECT local_path,sha256 FROM warehouse_source_file WHERE source_file_id=?",
                                 (identifier,)).fetchone()
        if row is None:
            raise ValueError(f"Certified source file is not registered: {identifier}")
        path = root / row[0]
        if not path.is_file() or file_sha256(path) != row[1]:
            raise ValueError(f"Registered source hash mismatch or missing file: {identifier}")
        evidence[identifier] = {"local_path": row[0], "sha256": row[1]}
    return evidence


def authorize(action, table, column, database, trigger):
    # Reads through views report the view name in the trigger slot; reading is
    # always permitted, but no write may originate from a trigger or view.
    if action in (sqlite3.SQLITE_READ, sqlite3.SQLITE_SELECT, sqlite3.SQLITE_FUNCTION):
        return sqlite3.SQLITE_OK
    if trigger:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_INSERT:
        return sqlite3.SQLITE_OK if table in OWNED_INSERT else sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_UPDATE:
        if table == CANONICAL and column == "canonical_votes":
            return sqlite3.SQLITE_OK
        if table == MATERIALIZED and column in {"votes", "vote_share"}:
            return sqlite3.SQLITE_OK
        if table in {BUILD, REGISTRY}:
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
    return {name: connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] for name in tables if name in available}


def repair(database: Path, *, apply: bool = False, expected_run: str | None = None,
           backup: Path | None = None, root: Path = ROOT, cycles=CYCLES,
           decoder: dict[str, str] | None = None, precinct_alignment: dict | None = None) -> dict:
    database = database.resolve()
    if apply and (not expected_run or backup is None):
        raise ValueError("Application requires --expected-run and --backup")
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
            staged = stage(connection, root, cycles, decoder, precinct_alignment)
            bridge, corrections = staged["bridge"], staged["corrections"]
            sources = source_evidence(connection, root, bridge.source_file_id)
            present = existing_bridge(connection, bridge)
            summary = {
                "bridge_rows": len(bridge),
                "match_methods": {str(k): int(v) for k, v in bridge.match_method.value_counts().items()},
                "corrections": len(corrections),
                "corrected_candidates": [
                    {"canonical_candidate_id": row.canonical_candidate_id, "before": int(row.canonical_votes_before),
                     "after": int(row.certified_votes), "certified_cell": row.source_candidate_result_id,
                     "certified_candidate_name": row.certified_candidate_name}
                    for row in corrections.itertuples(index=False)
                ],
                "affected_observation_sets": staged["affected_observation_sets"],
                "materialized_rows_updated": len(staged["materialized_updates"]),
                "source_files": sources,
            }
            if present:
                pending = corrections[corrections.canonical_candidate_id.map(
                    dict(zip(staged["canonical"].canonical_candidate_id, staged["canonical"].canonical_votes))
                ).ne(corrections.certified_votes)]
                if not pending.empty:
                    raise ValueError("Bridge exists but canonical totals still disagree with certified cells")
                connection.rollback()
                return {"warehouse_status": "unchanged", "latest_run": latest, "summary": summary}
            if not apply:
                connection.rollback()
                return {"warehouse_status": "dry_run", "latest_run": latest, "summary": summary}
            if any(row[0] in set(SNAPSHOT_TABLES) | {BRIDGE_TABLE}
                   for row in connection.execute("SELECT tbl_name FROM sqlite_master WHERE type='trigger'")):
                raise ValueError("Triggers on owned tables require separate review")
            before = snapshot(connection)
            before_counts = counts(connection, SNAPSHOT_TABLES)
            readiness_before = readiness_snapshot(connection)
            canonical_before = pd.read_sql_query(f"SELECT * FROM {CANONICAL} ORDER BY canonical_candidate_id", connection)
            code_paths = [Path(__file__), Path(__file__).with_name("alabama_certified_bridge.py"),
                          Path(__file__).with_name("warehouse.py"), SCHEMA]
            application_code = {str(path.resolve().relative_to(CODE_ROOT)).replace("\\", "/"): file_sha256(path)
                                for path in code_paths}
            backup.parent.mkdir(parents=True, exist_ok=True)
            with backup.open("xb"):
                pass
            with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as source, closing(sqlite3.connect(backup)) as destination:
                source.execute("PRAGMA query_only=ON")
                source.backup(destination)
                if destination.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                    raise ValueError("Backup quick_check failed")
                if snapshot(destination) != before or readiness_snapshot(destination) != readiness_before:
                    raise ValueError("Separate backup validation failed")
            source_evidence(connection, root, bridge.source_file_id)
            if {path: file_sha256(CODE_ROOT / path) for path in application_code} != application_code:
                raise ValueError("Application code changed during repair")
            for statement in schema_statements():
                connection.execute(statement)
            connection.set_authorizer(authorize)
            configuration = {"backup": str(backup), "expected_run": expected_run, "cycles": list(cycles),
                             "before_snapshot": before, "before_counts": before_counts,
                             "application_code_sha256": application_code, "source_files": sources,
                             "authority": "certified State Canvassing Board canvass totals for Alabama legislative contests",
                             "contract": "one approved bridge per canonical candidate at exact race/party grain with name evidence; "
                                         "disagreeing canonical totals corrected to certified; before-images retained"}
            run = begin_run(connection, TARGET, configuration)
            timestamp = utcnow()
            rows = bridge.copy()
            rows["build_run_id"] = run
            rows["recorded_at_utc"] = timestamp
            connection.executemany(
                f"INSERT INTO {BRIDGE_TABLE} ({','.join(BRIDGE_COLUMNS)}) VALUES ({','.join('?' for _ in BRIDGE_COLUMNS)})",
                [tuple(row[column] for column in BRIDGE_COLUMNS) for row in native_records(rows)],
            )
            before_images = []
            for row in corrections.itertuples(index=False):
                updated = connection.execute(
                    f"UPDATE {CANONICAL} SET canonical_votes=? WHERE canonical_candidate_id=? AND canonical_votes=?",
                    (float(row.certified_votes), row.canonical_candidate_id, float(row.canonical_votes_before)))
                if updated.rowcount != 1:
                    raise ValueError(f"Guarded canonical update mismatch: {row.canonical_candidate_id}")
                before_images.append({"canonical_candidate_id": row.canonical_candidate_id,
                                      "canonical_votes_before": int(row.canonical_votes_before),
                                      "canonical_votes_after": int(row.certified_votes),
                                      "certified_cell": row.source_candidate_result_id})
            materialized_before = staged["materialized_before"].set_index("candidate_result_id")
            for update in staged["materialized_updates"]:
                previous = materialized_before.loc[update["candidate_result_id"]]
                updated = connection.execute(
                    f"UPDATE {MATERIALIZED} SET votes=?, vote_share=? WHERE candidate_result_id=? AND votes=?",
                    (update["votes"], update["vote_share"], update["candidate_result_id"], int(previous.votes)))
                if updated.rowcount != 1:
                    raise ValueError(f"Guarded materialized update mismatch: {update['candidate_result_id']}")
            register_table(connection, BRIDGE_TABLE, "canonical", __file__, "canonical_candidate_id",
                           "Certified canvass totals for Alabama 2018/2022 legislative contests; exact race/party bridge with name evidence",
                           "append", "Alabama canonical candidate to certified canvass cell bridge")
            # Validation: canonical frame differs only in the corrected votes.
            expected = canonical_before.copy()
            for image in before_images:
                mask = expected.canonical_candidate_id.eq(image["canonical_candidate_id"])
                expected.loc[mask, "canonical_votes"] = float(image["canonical_votes_after"])
            actual = pd.read_sql_query(f"SELECT * FROM {CANONICAL} ORDER BY canonical_candidate_id", connection)
            pd.testing.assert_frame_equal(actual, expected)
            live = pd.read_sql_query("""
                SELECT candidate_result_id, votes, vote_share FROM all_southern_legislative_candidate_election_observations
                WHERE source_family='alabama_canonical' AND cycle IN (%s) ORDER BY candidate_result_id
            """ % ",".join("?" for _ in cycles), connection, params=tuple(cycles))
            materialized_after = materialized_alabama(connection, cycles)[["candidate_result_id", "votes", "vote_share"]]
            pd.testing.assert_frame_equal(
                materialized_after.reset_index(drop=True), live.reset_index(drop=True),
                check_exact=False, atol=1e-12, check_dtype=False,
            )
            if readiness_snapshot(connection) != readiness_before:
                raise ValueError("Readiness states changed during the certified-total repair")
            details = {**summary, "before_images": before_images, "backup": str(backup), "not_rebuilt": STALE,
                       "readiness_before": readiness_before, "readiness_after": readiness_snapshot(connection),
                       "after_canonical_sha256": digest_rows(connection.execute(f"SELECT * FROM {CANONICAL} ORDER BY rowid")),
                       "after_bridge_sha256": digest_rows(connection.execute(f"SELECT * FROM {BRIDGE_TABLE} ORDER BY rowid")),
                       "report_status": "database commit evidence authoritative; report written after commit"}
            connection.execute(f"INSERT INTO {REPAIR} VALUES (?,?,?,?,?,?,?)",
                               ("WQA-ALCERT-" + run, run, CANONICAL,
                                "Alabama 2018/2022 canonical totals corrected to bridged certified canvass cells",
                                "repaired_with_bridge_evidence", encode(details), timestamp))
            after_counts = counts(connection, SNAPSHOT_TABLES)
            expected_deltas = {BUILD: 1, REPAIR: 1}
            for table, count in before_counts.items():
                if table in (VERSION, REGISTRY):
                    if after_counts[table] not in (count, count + 1):
                        raise ValueError(f"Unexpected control row change: {table}")
                    continue
                if after_counts[table] != count + expected_deltas.get(table, 0):
                    raise ValueError(f"Unexpected row-count change: {table}")
            for table in (BUILD, REPAIR):
                preserved = digest_rows(connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid LIMIT ?', (before_counts[table],)))
                if preserved != before[table]:
                    raise ValueError(f"Prior control rows changed: {table}")
            for table in ("source_southern_legislative_observation_set", "source_southern_legislative_candidate_result",
                          "warehouse_source_file", "mart_southern_war_outcome"):
                if digest_rows(connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid')) != before[table]:
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
            stream.write(json.dumps(report, indent=2) + "\n")
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
    parser.add_argument("--cycles", type=int, nargs="+", default=list(CYCLES),
                        help="Stage-only inspection may narrow cycles; application requires the full contract")
    args = parser.parse_args(argv)
    cycles = tuple(args.cycles)
    if args.apply and cycles != tuple(CYCLES):
        raise SystemExit("Application requires the complete cycle contract " + str(CYCLES))
    result = repair(args.database, apply=args.apply, expected_run=args.expected_run, backup=args.backup, cycles=cycles)
    print(json.dumps(result, indent=2, default=str))
    return 1 if result.get("report_status") == "failed_after_commit" else 0


if __name__ == "__main__":
    raise SystemExit(main())
