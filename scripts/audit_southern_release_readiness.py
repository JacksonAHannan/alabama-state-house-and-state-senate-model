"""Read-only inventory of existing source eligibility; never certify a release.

No scores, margins, vote totals or analytical model outputs are selected.
The outcome mart is the inventory universe, not all scheduled election contests.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from southern_war_map_contract import scheduled_keys_2016_2024
from warehouse import database_path

VIEW = "mart_southern_war_training_no_finance"
STRICT = "strict_war_ready_no_finance"
KEY = ("state_code", "cycle", "chamber", "district")
FIELDS = ("war_outcome_id", "build_run_id", *KEY, "training_status", "context_feature_id",
          "baseline_source", "baseline_class", "baseline_quality", "baseline_source_path",
          "strict_baseline_eligible", "research_baseline_eligible", "incumbency_source",
          "incumbency_quality", "strict_incumbency_eligible", "source_file_id")


def reasons(row):
    """Describe recorded flags/missing metadata, without changing eligibility."""
    result = []
    if row["training_status"] != STRICT:
        result.append("training_status:" + row["training_status"])
    for name in ("context_feature_id", "baseline_source", "baseline_class",
                 "baseline_quality", "baseline_source_path", "incumbency_source",
                 "incumbency_quality", "source_file_id"):
        if row[name] is None or row[name] == "":
            result.append("missing:" + name)
    for name in ("strict_baseline_eligible", "research_baseline_eligible", "strict_incumbency_eligible"):
        if row[name] != 1:
            result.append("not_enabled:" + name)
    return result


def inventory(connection, schedule=None):
    schedule = scheduled_keys_2016_2024() if schedule is None else set(schedule)
    cursor = connection.execute(f"SELECT {','.join(FIELDS)} FROM {VIEW} ORDER BY state_code,cycle,chamber,district,war_outcome_id")
    rows = [dict(zip(FIELDS, values)) for values in cursor]
    context_rows = connection.execute("SELECT context_feature_id,build_run_id,state_code,cycle,chamber,district FROM mart_southern_war_context_feature").fetchall()
    contexts = {}
    context_keys = set()
    for identifier, run, *key in context_rows:
        if not identifier or identifier in contexts or tuple(key) in context_keys:
            raise ValueError("Duplicate or missing context ID/key")
        contexts[identifier] = (run, tuple(key))
        context_keys.add(tuple(key))
    ids, keys = set(), set()
    slices = {key: {"state_code": key[0], "cycle": key[1], "chamber": key[2],
                   "total": 0, "strict": 0, "excluded": 0,
                   "excluded_reason_counts": Counter(), "missing_source_file_id": 0}
              for key in sorted(schedule)}
    excluded = []
    for row in rows:
        identifier = row["war_outcome_id"]
        key = tuple(row[k] for k in KEY)
        if not identifier or any(value is None or value == "" for value in key):
            raise ValueError("Missing outcome ID or key")
        if identifier in ids or key in keys:
            raise ValueError("Duplicate outcome ID or key")
        ids.add(identifier); keys.add(key)
        if key[:3] not in schedule:
            raise ValueError("Outcome outside declared schedule")
        context_id = row["context_feature_id"]
        if context_id is not None:
            if context_id not in contexts or contexts[context_id][1] != key:
                raise ValueError("Context metadata join mismatch")
            row["context_build_run_id"] = contexts[context_id][0]
        else:
            if key in context_keys:
                raise ValueError("Context disappeared from eligibility view")
            row["context_build_run_id"] = None
        if not isinstance(row["training_status"], str) or not row["training_status"]:
            raise ValueError("Missing recorded training status")
        bucket = slices[key[:3]]
        bucket["total"] += 1
        bucket["missing_source_file_id"] += int(not row["source_file_id"])
        if row["training_status"] == STRICT:
            bucket["strict"] += 1
        else:
            reason_codes = reasons(row)
            excluded.append(row | {"reason_codes": reason_codes})
            bucket["excluded"] += 1
            bucket["excluded_reason_counts"].update(reason_codes)
    # Compare against the base outcome table, including stable IDs and keys;
    # a filtered or multiplying view must never hide observations.
    base = connection.execute("SELECT war_outcome_id,state_code,cycle,chamber,district FROM mart_southern_war_outcome").fetchall()
    expected = {(row[0], tuple(row[1:])) for row in base}
    if len(expected) != len(base) or expected != {(r["war_outcome_id"], tuple(r[k] for k in KEY)) for r in rows}:
        raise ValueError("Outcome universe differs from eligibility view")
    strict = sum(s["strict"] for s in slices.values())
    assert len(rows) == strict + len(excluded)
    return {"status": "source_eligibility_inventory_only", "scope": "Existing outcome mart; not all elections or publication certification",
            "reason_count_semantics": "Overlapping recorded metadata flags; not mutually exclusive adjudicated exclusion reasons",
            "outcome_build_run_ids": sorted({r["build_run_id"] for r in rows if r["build_run_id"] is not None}),
            "context_build_run_ids": sorted({r["context_build_run_id"] for r in rows if r["context_build_run_id"] is not None}),
            "missing_outcome_build_run_id_rows": sum(r["build_run_id"] is None for r in rows),
            "missing_context_rows": sum(r["context_feature_id"] is None for r in rows),
            "missing_context_build_run_id_rows": sum(r["context_feature_id"] is not None and r["context_build_run_id"] is None for r in rows),
            "scheduled_slices": len(schedule), "total": len(rows), "strict": strict,
            "excluded": len(excluded), "missing_source_file_id": sum(s["missing_source_file_id"] for s in slices.values()),
            "slices": list(slices.values()), "excluded_outcomes": excluded}


def audit(database):
    path = Path(database).resolve()
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        result = inventory(connection)
        has_runs = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='warehouse_build_run'").fetchone()
        latest = connection.execute("SELECT build_run_id FROM warehouse_build_run ORDER BY rowid DESC LIMIT 1").fetchone() if has_runs else None
        result["latest_warehouse_build_run_id"] = latest[0] if latest else None
        # Pin deployed definitions, including every view so indirect view
        # dependencies remain evidenced without attempting to parse SQLite SQL.
        definitions = connection.execute("SELECT name,type,sql FROM sqlite_master WHERE type='view' OR name IN (?,?,?) ORDER BY name", (VIEW, "mart_southern_war_context_feature", "mart_southern_war_outcome")).fetchall()
        result["sqlite_definition_sha256"] = {name: {"type": kind, "sha256": hashlib.sha256(sql.encode()).hexdigest()} for name, kind, sql in definitions}
        connection.rollback()
    code = [Path(__file__), Path(__file__).with_name("southern_war_map_contract.py"),
            Path(__file__).with_name("load_southern_war_preparation_warehouse.py")]
    return result | {"database": str(path), "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                     "code_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in code}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=database_path())
    args = parser.parse_args(argv)
    print(json.dumps(audit(args.database), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
