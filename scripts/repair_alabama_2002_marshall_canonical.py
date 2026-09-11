"""Apply the owner-adjudicated 2002 Marshall County canonical corrections.

Evidence: ``project_docs/audits/SOURCE_COLLISION_ADJUDICATION_PACKET_2026_09_11.md``
and the scratch identity rebuild under
``artifacts/war/canonical_identity_rebuild_20260911/``.  The legacy 2002 parse
stored the registered SOS workbook's MARSHALL sheet with a column offset, so
Marshall County segments never reached ``canonical_candidates``.  The 2026-09-05
repair (``RUN-40A033B9854141F6B05A76173E66D17B``) re-parsed the sheet with
physical locators, but the canonical identity table predates it.  A full
identity rebuild would also revert the 21 certified 2018/2022 canvass
corrections, so this script applies only the 2002 differences that rebuild
produced:

* House 26: DeKalb-only totals replaced by the DeKalb + Marshall district totals.
* Senate 9: Blount + Madison totals replaced by Blount + Madison + Marshall
  totals; the recorded winner flips to the actual winner.
* House 27 (Marshall-only district): the missing D and R rows are inserted.

Owner decisions 2026-09-11: House 26 option A1 (adopt district total), House 27
option B1 (rebuild identity/canonical from the repaired source); Senate 9 is the
same defect surfaced by that rebuild and follows the same rule.  Dry run by
default; ``--apply`` requires the exact latest warehouse run, a new separate
backup path and an authorization reference.  Nothing downstream is rebuilt here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from warehouse import ROOT, begin_run, database_path, file_sha256, finish_run, utcnow

TARGET = "alabama_2002_marshall_canonical_repair"
CANONICAL = "canonical_candidates"
MATERIALIZED = "canonical_southern_legislative_candidate_election"
ADJUDICATION = "warehouse_manual_adjudication"
BUILD = "warehouse_build_run"
REPAIR = "qa_warehouse_source_repair"
OWNED_INSERT = {CANONICAL, MATERIALIZED, ADJUDICATION, BUILD, REPAIR}
CONTROL_TABLES = (BUILD, REPAIR, ADJUDICATION, "warehouse_source_file", "warehouse_table_registry",
                  "warehouse_schema_version", "vote_observations", "mart_southern_war_outcome",
                  "mart_southern_war_context_feature")
PACKET = "project_docs/audits/SOURCE_COLLISION_ADJUDICATION_PACKET_2026_09_11.md"
SOURCE_FILE_ID = "SRC-9E0F7297AEB976F98688"
WORKBOOK = "2002-GeneralElection-PrecinctLevel_0.xls"
REPAIR_RUN = "RUN-40A033B9854141F6B05A76173E66D17B"

# Expected before-images and after-images, per the scratch identity rebuild and
# the raw workbook cells (sheet, 1-based row) recorded here as evidence.
UPDATES = [
    {"id": "AL-2002-house-26-D-MCDANIEL-FRANK", "before": 1102.0, "after": 7069.0, "winner_after": 1,
     "cells": "DEKALB!r71 1,102 + MARSHALL!r68 5,967"},
    {"id": "AL-2002-house-26-R-PATTERSON-JEFFREY", "before": 598.0, "after": 4459.0, "winner_after": 0,
     "cells": "DEKALB!r72 598 + MARSHALL!r69 3,861"},
    {"id": "AL-2002-senate-9-D-MITCHEM-HINTON", "before": 8914.0, "after": 24603.0, "winner_after": 1,
     "cells": "BLOUNT!r65 2,029 + MADISON!r79 precinct cells 6,885 (printed total 6,725) + MARSHALL!r65 15,689"},
    {"id": "AL-2002-senate-9-R-EDMONDS-DORIS", "before": 9438.0, "after": 16995.0, "winner_after": 0,
     "cells": "BLOUNT!r66 1,232 + MADISON!r80 precinct cells 8,206 (printed total 7,959) + MARSHALL!r66 7,557"},
]
INSERTS = [
    {"year": 2002, "chamber": "house", "district": 27, "canonical_party": "D", "canonical_votes": 7724.0,
     "canonical_name": "McLaughlin, Jeffrey", "canonical_source": "alabama_sos",
     "person_id": "ALPERSON-MCLAUGHLIN-JEFFREY", "canonical_candidate_id": "AL-2002-house-27-D-MCLAUGHLIN-JEFFREY",
     "incumbent": 0, "winner": 1, "cells": "MARSHALL!r71 7,724"},
    {"year": 2002, "chamber": "house", "district": 27, "canonical_party": "R", "canonical_votes": 4789.0,
     "canonical_name": "Hawkins, Gerald (Jerry)", "canonical_source": "alabama_sos",
     "person_id": "ALPERSON-HAWKINS-GERALD-JERRY", "canonical_candidate_id": "AL-2002-house-27-R-HAWKINS-GERALD-JERRY",
     "incumbent": 0, "winner": 0, "cells": "MARSHALL!r73 4,789"},
]
ADJUDICATIONS = [
    ("ADJ-2002-AL-HD26-COUNTY-COMPLEMENT", "AL-2002-house-26", "district_total=dekalb_plus_marshall",
     "Owner option A1. The two stored observation sets are complementary county segments (DeKalb, Marshall) of one contest in the same registered workbook, not competing versions; the canonical total is their sum."),
    ("ADJ-2002-AL-HD27-MARSHALL-PARSE", "AL-2002-house-27", "insert_from_repaired_source",
     "Owner option B1. The Marshall-only district was absent from canonical because the legacy 2002 parse mis-stored the sheet; the 2026-09-05 repair stored it correctly and the identity rebuild on the repaired source yields these rows. Klarner records the same totals (D 7,724 / R 4,789)."),
    ("ADJ-2002-AL-SD9-MARSHALL-SEGMENT", "AL-2002-senate-9", "district_total=blount_plus_madison_plus_marshall",
     "Same defect surfaced by the identity rebuild: the Marshall segment (D 15,689 / R 7,557) was missing, which also inverted the recorded winner. Madison's sheet is internally inconsistent (precinct cells sum 160/247 above its printed totals); canonical practice sums precinct cells and the discrepancy is recorded, not adjusted."),
]
MADISON_DISCREPANCY = {"sheet": "MADISON", "rows": [79, 80], "printed_totals": [6725, 7959],
                       "precinct_cell_sums": [6885, 8206], "difference": [160, 247],
                       "disposition": "recorded; precinct-cell sum retained per canonical rule"}


def digest_rows(rows) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(json.dumps(row, default=str).encode("utf-8")); digest.update(b"\n")
    return digest.hexdigest()


def counts(connection, tables):
    available = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return {n: connection.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in tables if n in available}


def control_snapshot(connection):
    available = {r[0] for r in connection.execute("SELECT name FROM sqlite_master")}
    return {n: digest_rows(connection.execute(f'SELECT * FROM "{n}" ORDER BY rowid')) for n in CONTROL_TABLES if n in available}


def canonical_digest_excluding(connection, ids):
    marks = ",".join("?" for _ in ids)
    return digest_rows(connection.execute(
        f"SELECT * FROM {CANONICAL} WHERE canonical_candidate_id NOT IN ({marks}) ORDER BY rowid", ids))


def materialized_digest_excluding(connection, ids):
    marks = ",".join("?" for _ in ids)
    return digest_rows(connection.execute(
        f"SELECT * FROM {MATERIALIZED} WHERE candidate_result_id NOT IN ({marks}) ORDER BY rowid", ids))


def stage(connection) -> dict:
    ids = [u["id"] for u in UPDATES]
    marks = ",".join("?" for _ in ids)
    live = {r[0]: r for r in connection.execute(
        f"SELECT canonical_candidate_id, canonical_votes, winner FROM {CANONICAL} WHERE canonical_candidate_id IN ({marks})", ids)}
    existing_inserts = connection.execute(
        f"SELECT canonical_candidate_id FROM {CANONICAL} WHERE year=2002 AND chamber='house' AND district=27").fetchall()
    materialized = {r[0]: r for r in connection.execute(
        f"SELECT candidate_result_id, votes, vote_share, observation_set_id FROM {MATERIALIZED} WHERE candidate_result_id IN ({marks})", ids)}
    template = connection.execute(
        f"SELECT * FROM {MATERIALIZED} WHERE candidate_result_id=?", ("AL-2002-house-26-D-MCDANIEL-FRANK",)).fetchone()
    template_columns = [d[1] for d in connection.execute(f"PRAGMA table_info({MATERIALIZED})")]
    existing_adj = connection.execute(
        f"SELECT adjudication_id FROM {ADJUDICATION} WHERE adjudication_id IN (?,?,?)", tuple(a[0] for a in ADJUDICATIONS)).fetchall()
    # Source evidence: the repaired Marshall rows must still sum to the segments used.
    segments = connection.execute("""
        SELECT office, CAST(district AS INTEGER), county_key, party_norm, ROUND(SUM(votes))
        FROM vote_observations WHERE source='alabama_sos' AND year=2002
          AND ((office='State Senate' AND district=9) OR (office='State House' AND district IN (26,27)))
          AND party_norm IN ('D','R') GROUP BY 1,2,3,4 ORDER BY 1,2,3,4""").fetchall()
    return {"live": live, "existing_hd27": existing_inserts, "materialized": materialized,
            "materialized_template": dict(zip(template_columns, template)) if template else None,
            "template_columns": template_columns, "existing_adjudications": existing_adj, "segments": segments}


def expected_segments():
    return {("State House", 26, "DEKALB", "D"): 1102, ("State House", 26, "DEKALB", "R"): 598,
            ("State House", 26, "MARSHALL", "D"): 5967, ("State House", 26, "MARSHALL", "R"): 3861,
            ("State House", 27, "MARSHALL", "D"): 7724, ("State House", 27, "MARSHALL", "R"): 4789,
            ("State Senate", 9, "BLOUNT", "D"): 2029, ("State Senate", 9, "BLOUNT", "R"): 1232,
            ("State Senate", 9, "MADISON", "D"): 6885, ("State Senate", 9, "MADISON", "R"): 8206,
            ("State Senate", 9, "MARSHALL", "D"): 15689, ("State Senate", 9, "MARSHALL", "R"): 7557}


def authorize(action, table, column, database, trigger):
    if action in (sqlite3.SQLITE_READ, sqlite3.SQLITE_SELECT, sqlite3.SQLITE_FUNCTION):
        return sqlite3.SQLITE_OK
    if trigger:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_INSERT:
        return sqlite3.SQLITE_OK if table in OWNED_INSERT else sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_UPDATE:
        if table == CANONICAL and column in {"canonical_votes", "winner"}:
            return sqlite3.SQLITE_OK
        if table == MATERIALIZED and column in {"votes", "vote_share"}:
            return sqlite3.SQLITE_OK
        if table == BUILD:
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY
    if action in (sqlite3.SQLITE_DELETE, sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_ALTER_TABLE,
                  sqlite3.SQLITE_CREATE_VIEW, sqlite3.SQLITE_DROP_VIEW, sqlite3.SQLITE_CREATE_TRIGGER, sqlite3.SQLITE_DROP_TRIGGER,
                  sqlite3.SQLITE_CREATE_INDEX, sqlite3.SQLITE_DROP_INDEX, sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH):
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def repair(database: Path, *, apply=False, expected_run=None, backup=None, authorized_by=None) -> dict:
    database = database.resolve()
    if apply and (not expected_run or backup is None or not authorized_by):
        raise ValueError("Application requires --expected-run, --backup and --authorized-by")
    if not database.is_file():
        raise FileNotFoundError(database)
    report_path = None
    if apply:
        backup = backup.resolve(); report_path = backup.with_name(backup.name + ".application.json")
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
            observed = {(o, d, c, p): int(v) for o, d, c, p, v in staged["segments"]}
            if observed != expected_segments():
                raise ValueError(f"Source segments differ from the reviewed evidence: {observed}")
            if staged["existing_adjudications"] or staged["existing_hd27"]:
                connection.rollback()
                return {"warehouse_status": "unchanged", "latest_run": latest, "staged": staged}
            for u in UPDATES:
                row = staged["live"].get(u["id"])
                if row is None or float(row[1]) != u["before"]:
                    raise ValueError(f"Before-image mismatch for {u['id']}: {row}")
                if u["id"] not in staged["materialized"] or int(staged["materialized"][u["id"]][1]) != int(u["before"]):
                    raise ValueError(f"Materialized before-image mismatch for {u['id']}")
            if staged["materialized_template"] is None:
                raise ValueError("No materialized Alabama canonical template row for 2002")
            proposal = {"updates": UPDATES, "inserts": INSERTS, "adjudications": [a[0] for a in ADJUDICATIONS],
                        "madison_discrepancy": MADISON_DISCREPANCY}
            if not apply:
                connection.rollback()
                return {"warehouse_status": "dry_run", "latest_run": latest, "proposal": proposal}
            if any(r[0] in {CANONICAL, MATERIALIZED, *OWNED_INSERT}
                   for r in connection.execute("SELECT tbl_name FROM sqlite_master WHERE type='trigger'")):
                raise ValueError("Triggers on owned tables require separate review")
            ids = [u["id"] for u in UPDATES]
            before_controls = control_snapshot(connection)
            before_counts = counts(connection, (CANONICAL, MATERIALIZED, *CONTROL_TABLES))
            before_canonical_others = canonical_digest_excluding(connection, ids)
            before_materialized_others = materialized_digest_excluding(connection, ids)
            code_paths = [Path(__file__), Path(__file__).with_name("warehouse.py")]
            application_code = {str(p.resolve().relative_to(ROOT)).replace("\\", "/"): file_sha256(p) for p in code_paths}
            backup.parent.mkdir(parents=True, exist_ok=True)
            with backup.open("xb"):
                pass
            with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as source, closing(sqlite3.connect(backup)) as destination:
                source.execute("PRAGMA query_only=ON"); source.backup(destination)
                if destination.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                    raise ValueError("Backup quick_check failed")
                if control_snapshot(destination) != before_controls:
                    raise ValueError("Separate backup validation failed")
            if {p: file_sha256(ROOT / p) for p in application_code} != application_code:
                raise ValueError("Application code changed during repair")
            connection.set_authorizer(authorize)
            configuration = {"backup": str(backup), "expected_run": expected_run, "source_file_id": SOURCE_FILE_ID,
                             "workbook": WORKBOOK, "repair_run_for_marshall_rows": REPAIR_RUN, "packet": PACKET,
                             "before_controls": before_controls, "before_counts": before_counts,
                             "canonical_digest_excluding_targets": before_canonical_others,
                             "materialized_digest_excluding_targets": before_materialized_others,
                             "application_code_sha256": application_code, "authorized_by": authorized_by,
                             "proposal": proposal}
            run = begin_run(connection, TARGET, configuration)
            timestamp = utcnow()
            for adj_id, subject, decision, rationale in ADJUDICATIONS:
                connection.execute(
                    f"INSERT INTO {ADJUDICATION} (adjudication_id, domain, subject_type, subject_id, decision, rationale, "
                    "evidence_locator, review_status, decided_at_utc, supersedes_adjudication_id) VALUES (?,?,?,?,?,?,?,?,?,NULL)",
                    (adj_id, "elections_canonical", "canonical_contest", subject, decision, rationale,
                     json.dumps({"packet": PACKET, "source_file_id": SOURCE_FILE_ID, "workbook": WORKBOOK,
                                 "build_run_id": run, "authorized_by": authorized_by,
                                 "madison_discrepancy": MADISON_DISCREPANCY if "SD9" in adj_id else None}, sort_keys=True),
                     "approved", timestamp))
            for u in UPDATES:
                updated = connection.execute(
                    f"UPDATE {CANONICAL} SET canonical_votes=?, winner=? WHERE canonical_candidate_id=? AND canonical_votes=?",
                    (u["after"], u["winner_after"], u["id"], u["before"]))
                if updated.rowcount != 1:
                    raise ValueError(f"Guarded canonical update mismatch: {u['id']}")
            for ins in INSERTS:
                fields = [k for k in ins if k != "cells"]
                connection.execute(
                    f"INSERT INTO {CANONICAL} ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
                    [ins[k] for k in fields])
            # Materialized Alabama canonical rows: votes and shares within each contest.
            totals = {"AL-2002-house-26": 7069.0 + 4459.0, "AL-2002-senate-9": 24603.0 + 16995.0, "AL-2002-house-27": 7724.0 + 4789.0}
            for u in UPDATES:
                contest = u["id"].rsplit("-", 3)[0]
                updated = connection.execute(
                    f"UPDATE {MATERIALIZED} SET votes=?, vote_share=? WHERE candidate_result_id=? AND votes=?",
                    (int(u["after"]), u["after"] / totals[contest], u["id"], int(u["before"])))
                if updated.rowcount != 1:
                    raise ValueError(f"Guarded materialized update mismatch: {u['id']}")
            template = staged["materialized_template"]
            for ins in INSERTS:
                row = dict(template)
                row.update({"candidate_result_id": ins["canonical_candidate_id"], "observation_set_id": "ALCANON-2002-house-27",
                            "build_run_id": run, "district": "27", "candidate_name": ins["canonical_name"],
                            "candidate_name_original": ins["canonical_name"],
                            "party_family": "democratic" if ins["canonical_party"] == "D" else "republican",
                            "party_original": ins["canonical_party"], "votes": int(ins["canonical_votes"]),
                            "vote_share": ins["canonical_votes"] / totals["AL-2002-house-27"], "as_of_utc": timestamp})
                cols = staged["template_columns"]
                connection.execute(f"INSERT INTO {MATERIALIZED} ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",
                                   [row[c] for c in cols])
            # Validation.
            if canonical_digest_excluding(connection, ids + [i["canonical_candidate_id"] for i in INSERTS]) != before_canonical_others:
                raise ValueError("Other canonical rows changed")
            if materialized_digest_excluding(connection, ids + [i["canonical_candidate_id"] for i in INSERTS]) != before_materialized_others:
                raise ValueError("Other materialized rows changed")
            after = {r[0]: (r[1], r[2]) for r in connection.execute(
                f"SELECT canonical_candidate_id, canonical_votes, winner FROM {CANONICAL} WHERE year=2002 AND ((chamber='house' AND district IN (26,27)) OR (chamber='senate' AND district=9))")}
            for u in UPDATES:
                if after[u["id"]] != (u["after"], u["winner_after"]):
                    raise ValueError(f"After-image mismatch {u['id']}: {after[u['id']]}")
            for ins in INSERTS:
                if after[ins["canonical_candidate_id"]] != (ins["canonical_votes"], ins["winner"]):
                    raise ValueError(f"Insert after-image mismatch {ins['canonical_candidate_id']}")
            for contest in totals:
                share = connection.execute(f"SELECT ROUND(SUM(vote_share), 9) FROM {MATERIALIZED} WHERE observation_set_id=?",
                                           ("ALCANON-" + contest[3:],)).fetchone()[0]
                if share != 1.0:
                    raise ValueError(f"Vote shares do not sum to one for {contest}: {share}")
            details = {"updates": UPDATES, "inserts": INSERTS, "adjudications": [a[0] for a in ADJUDICATIONS],
                       "madison_discrepancy": MADISON_DISCREPANCY, "backup": str(backup),
                       "not_rebuilt": [
                           "candidate_aliases, candidate_party_affiliations, candidate_party_switches, candidate_alias_match_candidates (identity-build copies; HD27 absent, SD9/HD26 votes stale)",
                           "canonical_southern_legislative_candidate_election: Klarner HD27 rows LCAND-B1A8473C428DB3E46D37 / LCAND-9BD17D79BFA93F9EFC32 (set LSET-120E9CDFC994B713A780, rank 30) remain beside the new ALCANON-2002-house-27 set until load_southern_legislative_history_warehouse.py re-materializes from the resolved view; the final-candidate view already prefers ALCANON and the 2016-2024 outcome mart is unaffected",
                           "build_1998_2006_context_features.py outputs (1998_2006_candidate_incumbency.csv, 1998_2006_cmo_context_features.csv, mart_historical_cmo_context_feature_v2)",
                           "build_dime_finance_features.py and build_multisource_finance_features.py candidate/race finance matches (new HD27 candidates absent)",
                           "canonical_cmo_features.csv, canonical_cmo_candidates.csv, canonical_cmo_district_office_baselines.csv, historical_cmo_extension.csv", "cmo_v5_*",
                           "southern_war_panel_v1 (Alabama 2002 backcast rows; outside the v3 training frame)", "alabama_historical_war_v1",
                           "docs/cmo.html, ideology pages"],
                       "report_status": "database commit evidence authoritative; report written after commit"}
            connection.execute(f"INSERT INTO {REPAIR} VALUES (?,?,?,?,?,?,?)",
                               ("WQA-2002-MARSHALL-CANONICAL-" + run, run, CANONICAL,
                                "2002 Alabama House 26/27 and Senate 9 canonical totals from the repaired Marshall parse",
                                "repaired_with_adjudication", json.dumps(details, sort_keys=True, default=str), timestamp))
            after_counts = counts(connection, (CANONICAL, MATERIALIZED, *CONTROL_TABLES))
            expected = {BUILD: 1, REPAIR: 1, ADJUDICATION: 3, CANONICAL: 2, MATERIALIZED: 2}
            for table, count in before_counts.items():
                if after_counts[table] != count + expected.get(table, 0):
                    raise ValueError(f"Unexpected row-count change: {table}")
            for table in (BUILD, REPAIR, ADJUDICATION):
                preserved = digest_rows(connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid LIMIT ?', (before_counts[table],)))
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
            connection.rollback(); raise
    report = {"warehouse_status": "committed", "build_run_id": run, "latest_run_before": latest,
              "configuration": configuration, "validation": details}
    try:
        with report_path.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(report, indent=2, default=str) + "\n")
        report["report_status"] = "written"
    except OSError as exc:
        report["report_status"] = "failed_after_commit"; report["report_error"] = str(exc)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=database_path())
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-run")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--authorized-by")
    args = parser.parse_args(argv)
    result = repair(args.database, apply=args.apply, expected_run=args.expected_run, backup=args.backup, authorized_by=args.authorized_by)
    print(json.dumps(result, indent=2, default=str))
    return 1 if result.get("report_status") == "failed_after_commit" else 0


if __name__ == "__main__":
    raise SystemExit(main())
