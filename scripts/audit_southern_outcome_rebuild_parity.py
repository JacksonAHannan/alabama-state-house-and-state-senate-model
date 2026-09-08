"""Read-only parity audit of a rebuilt Southern WAR outcome mart against its backup.

After `load_southern_war_preparation_warehouse.py` replaces the outcome, context
and Alabama 2026 roster marts, this audit proves what changed.  Context and roster
rows must be identical apart from the build run; outcomes outside the expected
state/cycle set must be identical apart from the build run; changed outcomes are
listed field by field.  It never writes to either database.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3

import pandas as pd

from warehouse import database_path

OUTCOME = "mart_southern_war_outcome"
CONTEXT = "mart_southern_war_context_feature"
ROSTER = "mart_alabama_2026_incumbency_roster"
KEYS = {OUTCOME: "war_outcome_id", CONTEXT: "context_feature_id", ROSTER: "roster_id"}
IGNORED = {"build_run_id"}


def read_table(path: Path, table: str) -> pd.DataFrame:
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        connection.execute("PRAGMA query_only=ON")
        frame = pd.read_sql_query(f"SELECT * FROM {table} ORDER BY {KEYS[table]}", connection)
    return frame.set_index(KEYS[table])


def compare(before: pd.DataFrame, after: pd.DataFrame) -> dict:
    """Return added/removed keys and per-key changed fields, ignoring build run."""
    columns = [column for column in before.columns if column not in IGNORED]
    if columns != [column for column in after.columns if column not in IGNORED]:
        raise ValueError("Column sets differ between backup and current table")
    added = sorted(set(after.index) - set(before.index))
    removed = sorted(set(before.index) - set(after.index))
    shared = before.index.intersection(after.index)
    left, right = before.loc[shared, columns], after.loc[shared, columns]
    changed = {}
    for column in columns:
        differs = ~((left[column] == right[column]) | (left[column].isna() & right[column].isna()))
        for key in shared[differs.to_numpy()]:
            changed.setdefault(key, {})[column] = {"before": _native(left.at[key, column]),
                                                   "after": _native(right.at[key, column])}
    return {"rows_before": len(before), "rows_after": len(after), "added": added, "removed": removed,
            "changed": changed}


def _native(value):
    if pd.isna(value):
        return None
    return value.item() if hasattr(value, "item") else value


def audit(backup: Path, current: Path | None = None, expected_states: tuple[str, ...] = ("AL",)) -> dict:
    current = Path(current) if current else database_path()
    result = {"backup": str(backup), "current": str(current), "tables": {}}
    for table in (CONTEXT, ROSTER):
        result["tables"][table] = compare(read_table(backup, table), read_table(current, table))
    before, after = read_table(backup, OUTCOME), read_table(current, OUTCOME)
    outcomes = compare(before, after)
    changed_states = sorted({after.at[key, "state_code"] for key in outcomes["changed"] if key in after.index})
    result["tables"][OUTCOME] = {**outcomes, "changed_states": changed_states,
                                 "changed_fields": sorted({field for fields in outcomes["changed"].values() for field in fields})}
    result["identical_context_and_roster"] = all(
        not result["tables"][t]["added"] and not result["tables"][t]["removed"] and not result["tables"][t]["changed"]
        for t in (CONTEXT, ROSTER))
    result["outcome_changes_confined_to_expected_states"] = (
        not outcomes["added"] and not outcomes["removed"] and set(changed_states) <= set(expected_states))
    result["status"] = ("passed" if result["identical_context_and_roster"]
                        and result["outcome_changes_confined_to_expected_states"] else "review")
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--database", type=Path, default=None)
    parser.add_argument("--expected-states", nargs="+", default=["AL"])
    parser.add_argument("--report", type=Path, default=None, help="optional JSON report path")
    args = parser.parse_args(argv)
    result = audit(args.backup, args.database, tuple(args.expected_states))
    text = json.dumps(result, indent=2, default=str)
    if args.report:
        args.report.write_text(text + "\n", encoding="utf-8")
    summary = {key: value for key, value in result.items() if key != "tables"}
    summary["outcome_rows_changed"] = len(result["tables"][OUTCOME]["changed"])
    summary["changed_fields"] = result["tables"][OUTCOME]["changed_fields"]
    print(json.dumps(summary, indent=2, default=str))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
