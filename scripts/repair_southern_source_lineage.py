"""Recover singleton official-result source lineage; no outcome or export rebuild."""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

import pandas as pd

from load_southern_war_preparation_warehouse import (
    observation_source_file, unique_official_candidate_sources,
)
from warehouse import ROOT, begin_run, database_path, file_sha256, finish_run, utcnow

OUTCOMES = "mart_southern_war_outcome"
CONTROLS = {"warehouse_build_run", "qa_warehouse_source_repair"}
SNAPSHOT_TABLES = (
    OUTCOMES, "source_southern_candidate_election", "bridge_southern_candidate_result_source",
    "warehouse_source_file", "warehouse_build_run", "qa_warehouse_source_repair",
)
TARGET = "southern_official_source_lineage_repair"
STALE = ["data/processed/war/finance_free_southern_war/ (eight existing bundle files)",
         "data/processed/war/southern_historical_war_v1/race_war.csv and candidate_cycle_war.csv",
         "Southern map sourceFileId/sourceFileStatus payload emitted by build_southern_war_map.py",
         "downstream manifests and publication provenance; not rebuilt or certified"]


def digest_rows(rows) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(json.dumps(tuple(row), ensure_ascii=False, separators=(",", ":")).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def snapshot(connection) -> dict[str, str]:
    return {name: digest_rows(connection.execute(f'SELECT * FROM "{name}" ORDER BY rowid'))
            for name in SNAPSHOT_TABLES}


def readiness_snapshot(connection) -> dict[str, str | None]:
    available = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
    return {
        name: digest_rows(connection.execute(
            f"SELECT war_outcome_id,{status} FROM {name} ORDER BY war_outcome_id"
        )) if name in available else None
        for name, status in (
            ("mart_southern_war_training_no_finance", "training_status"),
            ("mart_southern_war_training_with_finance", "evaluation_status"),
        )
    }


def stage(connection):
    outcomes = pd.read_sql_query(f"SELECT * FROM {OUTCOMES} ORDER BY war_outcome_id", connection)
    pending = outcomes[outcomes.source_family.eq("official_state") & outcomes.source_file_id.isna()]
    if pending.empty:
        return outcomes, {}, []
    observations = pd.read_sql_query(f"""
        SELECT r.*, r.candidate_election_id AS candidate_result_id,
               'OFFICIAL-' || r.contest_id AS observation_set_id,
               'official_state' AS source_family
        FROM source_southern_candidate_election r
        WHERE r.validation_status='passed' AND r.contest_id IN (
            SELECT substr(observation_set_id,10) FROM {OUTCOMES}
            WHERE source_family='official_state' AND source_file_id IS NULL
        )
    """, connection)
    groups = dict(tuple(observations.groupby("observation_set_id")))
    sources = unique_official_candidate_sources(connection)
    mapping, unresolved = {}, []
    for outcome in pending.itertuples(index=False):
        group = groups.get(outcome.observation_set_id)
        if group is None:
            raise ValueError(f"Missing contributing observations: {outcome.war_outcome_id}")
        for key in ("state_code", "cycle", "chamber", "district", "election_stage",
                    "election_date", "district_plan_id", "geography_vintage"):
            expected_value = getattr(outcome, key)
            matches = group[key].isna() if pd.isna(expected_value) else group[key].eq(expected_value)
            if not matches.all():
                raise ValueError(f"Observation scope mismatch ({key}): {outcome.war_outcome_id}")
        if group.candidate_result_id.duplicated().any():
            raise ValueError("Duplicate contributing candidate ID")
        for prefix, party in (("dem", "democratic"), ("rep", "republican")):
            major = group[group.party_family.eq(party) & group.votes.gt(0)]
            if (len(major) != 1 or major.iloc[0].candidate_result_id != getattr(outcome, prefix + "_candidate_result_id")
                    or major.iloc[0].votes != getattr(outcome, prefix + "_votes")):
                raise ValueError(f"Constituent mismatch: {outcome.war_outcome_id}")
        if group.votes.isna().any() or group.votes.sum() != outcome.two_party_votes + outcome.third_party_votes:
            raise ValueError(f"Contributing vote total mismatch: {outcome.war_outcome_id}")
        source = observation_source_file(group, sources)
        if source is None:
            unresolved.append(outcome.war_outcome_id)
        else:
            mapping[outcome.war_outcome_id] = source
    return outcomes, mapping, unresolved


def source_evidence(connection, identifiers):
    evidence = {}
    for identifier in sorted(set(identifiers)):
        row = connection.execute(
            "SELECT local_path,sha256 FROM warehouse_source_file WHERE source_file_id=?", (identifier,),
        ).fetchone()
        path = ROOT / row[0]
        if not path.is_file() or file_sha256(path) != row[1]:
            raise ValueError(f"Registered source hash mismatch or missing file: {identifier}")
        evidence[identifier] = {"local_path": row[0], "sha256": row[1]}
    return evidence


def authorize(action, table, column, database, trigger):
    if action == sqlite3.SQLITE_UPDATE:
        permitted = (table == OUTCOMES and column == "source_file_id") or table in CONTROLS
        return sqlite3.SQLITE_OK if permitted else sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_INSERT:
        return sqlite3.SQLITE_OK if table in CONTROLS else sqlite3.SQLITE_DENY
    if action in (sqlite3.SQLITE_DELETE, sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_DROP_TABLE,
                  sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_CREATE_VIEW, sqlite3.SQLITE_DROP_VIEW,
                  sqlite3.SQLITE_CREATE_TRIGGER, sqlite3.SQLITE_DROP_TRIGGER,
                  sqlite3.SQLITE_CREATE_INDEX, sqlite3.SQLITE_DROP_INDEX,
                  sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH):
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def validate(connection, expected):
    actual = pd.read_sql_query(f"SELECT * FROM {OUTCOMES} ORDER BY war_outcome_id", connection)
    pd.testing.assert_frame_equal(actual, expected)
    if connection.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("Foreign key violation")


def repair(database: Path, backup: Path):
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
            before, mapping, unresolved = stage(connection)
            if not mapping:
                connection.rollback()
                return {"warehouse_status": "unchanged", "repaired_rows": 0, "unresolved": unresolved}
            triggers = connection.execute("SELECT tbl_name FROM sqlite_master WHERE type='trigger'")
            if any(row[0] in CONTROLS | {OUTCOMES} for row in triggers):
                raise ValueError("Triggers on owned tables require separate review")
            connection.set_authorizer(authorize)
            sources = source_evidence(connection, mapping.values())
            before_snapshot = snapshot(connection)
            readiness_before = readiness_snapshot(connection)
            backup.parent.mkdir(parents=True, exist_ok=True)
            with backup.open("xb"):
                pass
            with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as source, closing(sqlite3.connect(backup)) as destination:
                source.execute("PRAGMA query_only=ON")
                source.backup(destination)
                if destination.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise ValueError("Backup quick_check failed")
                if snapshot(destination) != before_snapshot:
                    raise ValueError("Backup source/owned snapshot mismatch")
                if readiness_snapshot(destination) != readiness_before:
                    raise ValueError("Backup readiness snapshot mismatch")
            configuration = {"backup": str(backup), "source_files": sources,
                "contract": "all contributing rows require one registered agreeing bridge file; history view remains bridge-backed",
                "before_snapshot": before_snapshot, "application_code_sha256": file_sha256(Path(__file__)),
                "producer_code_sha256": file_sha256(Path(__file__).with_name("load_southern_war_preparation_warehouse.py"))}
            run = begin_run(connection, TARGET, configuration)
            expected = before.copy()
            for identifier, source in mapping.items():
                updated = connection.execute(f"""UPDATE {OUTCOMES} SET source_file_id=?
                    WHERE war_outcome_id=? AND source_file_id IS NULL AND source_family='official_state'""",
                    (source, identifier))
                if updated.rowcount != 1:
                    raise ValueError(f"Guarded lineage update mismatch: {identifier}")
                expected.loc[expected.war_outcome_id.eq(identifier), "source_file_id"] = source
            validate(connection, expected)
            readiness_after = readiness_snapshot(connection)
            if readiness_after != readiness_before:
                raise ValueError("Readiness states changed during provenance-only repair")
            details = {"repaired_rows": len(mapping), "source_file_mapping": mapping,
                "unresolved_official_outcomes": unresolved, "backup": str(backup), "not_rebuilt": STALE,
                "after_outcome_sha256": digest_rows(connection.execute(f"SELECT * FROM {OUTCOMES} ORDER BY rowid")),
                "readiness_before": readiness_before, "readiness_after": readiness_after,
                "report_status": "database commit evidence authoritative; report written after commit"}
            connection.execute("INSERT INTO qa_warehouse_source_repair VALUES (?,?,?,?,?,?,?)",
                ("WQA-LINEAGE-" + run, run, OUTCOMES, "NULL official_state singleton source-file lineage",
                 "repaired_with_review", json.dumps(details, sort_keys=True), utcnow()))
            finish_run(connection, run, details)
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
    report = {"warehouse_status": "committed", "build_run_id": run,
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
    parser.add_argument("--backup", type=Path, required=True)
    args = parser.parse_args(argv)
    result = repair(args.database, args.backup)
    print(json.dumps(result, indent=2))
    return 1 if result.get("report_status") == "failed_after_commit" else 0


if __name__ == "__main__":
    raise SystemExit(main())
