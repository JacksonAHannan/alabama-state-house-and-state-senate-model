#!/usr/bin/env python3
"""Apply non-negotiable integrity and coverage gates to Southern finance marts."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data/processed/elections/alabama_elections.sqlite"
OUTPUT = ROOT / "data/processed/source_audits/southern_finance_release_validation.json"


def validate(database: Path) -> dict[str, object]:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        schema_version = connection.execute(
            "SELECT max(version) FROM warehouse_schema_version"
        ).fetchone()[0]
        totals = dict(connection.execute("""
            SELECT count(*) AS source_rows,
                   sum(finance_observed) AS observed_source_rows,
                   sum(CASE WHEN finance_observed=0 AND total_fundraising IS NOT NULL
                            THEN 1 ELSE 0 END) AS unknown_with_total
            FROM source_southern_candidate_cycle_finance
        """).fetchone())
        identity = dict(connection.execute("""
            SELECT count(*) AS identity_rows,
                   sum(review_status='accepted') AS accepted_rows,
                   sum(review_status='review') AS review_rows,
                   sum(review_status='accepted' AND f.finance_observed=1) AS accepted_observed_rows
            FROM bridge_southern_finance_candidate_identity i
            JOIN source_southern_candidate_cycle_finance f USING(finance_candidate_cycle_id)
        """).fetchone())
        race = dict(connection.execute("""
            SELECT count(*) AS race_rows,
                   sum(finance_complete) AS complete_races,
                   sum(CASE WHEN finance_complete=0 AND log_fundraising_ratio_d_to_r IS NOT NULL
                            THEN 1 ELSE 0 END) AS incomplete_with_feature
            FROM mart_southern_race_finance
        """).fetchone())
        model_incomplete = 0
        if connection.execute("SELECT 1 FROM sqlite_master WHERE name='mart_southern_war_training_with_finance'").fetchone():
            model_incomplete = connection.execute("""SELECT COUNT(*) FROM mart_southern_war_training_with_finance
              WHERE finance_complete=0 AND (democratic_fundraising IS NOT NULL
                OR republican_fundraising IS NOT NULL OR log_fundraising_ratio_d_to_r IS NOT NULL)""").fetchone()[0]
        duplicate_source = connection.execute("""
            SELECT count(*) FROM (
              SELECT state_code,cycle,chamber,district,party_family,count(*) n
              FROM source_southern_candidate_cycle_finance
              GROUP BY 1,2,3,4,5 HAVING n>1
            )
        """).fetchone()[0]
        duplicate_mart = connection.execute("""
            SELECT count(*) FROM (
              SELECT candidate_result_id,count(*) n
              FROM mart_southern_candidate_cycle_finance
              GROUP BY 1 HAVING n>1
            )
        """).fetchone()[0]
        state_cycles = [dict(row) for row in connection.execute("""
            SELECT state_code,cycle,source_candidate_rows,observed_candidate_rows,
                   accepted_identity_matches,review_identity_matches,
                   observed_accepted_matches,democratic_republican_races,
                   finance_complete_races,candidate_finance_coverage,
                   identity_match_coverage,warehouse_observed_coverage,
                   race_finance_coverage
            FROM qa_southern_finance_coverage ORDER BY state_code,cycle
        """)]
    finally:
        connection.close()

    observed = int(totals["observed_source_rows"] or 0)
    accepted_observed = int(identity["accepted_observed_rows"] or 0)
    source_rows = int(totals["source_rows"] or 0)
    checks = {
        "schema_version_at_least_14": int(schema_version or 0) >= 14,
        "sqlite_integrity": integrity == "ok",
        "foreign_keys": len(foreign_keys) == 0,
        "source_key_unique": duplicate_source == 0,
        "mart_candidate_key_unique": duplicate_mart == 0,
        "unknown_is_not_zero_filled": int(totals["unknown_with_total"] or 0) == 0,
        "incomplete_races_have_no_numeric_feature": int(race["incomplete_with_feature"] or 0) == 0,
        "incomplete_model_inputs_have_no_numeric_amounts": model_incomplete == 0,
        "candidate_universe_loaded": source_rows >= 12_000,
        "accepted_identity_coverage_at_least_98_percent": (
            int(identity["accepted_rows"] or 0) / source_rows >= 0.98 if source_rows else False
        ),
        "observed_identity_retention_at_least_98_percent": (
            accepted_observed / observed >= 0.98 if observed else False
        ),
        "complete_races_available": int(race["complete_races"] or 0) >= 1_000,
    }
    result = {
        "status": "pass" if all(checks.values()) else "fail",
        "database": database.relative_to(ROOT).as_posix(),
        "schema_version": schema_version,
        "checks": checks,
        "totals": {**totals, **identity, **race},
        "state_cycle_coverage": state_cycles,
        "policy": "Missing finance remains null; model features publish only for complete D/R races.",
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    result = validate(args.database.resolve())
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], **result["totals"]}, indent=2))
    if result["status"] != "pass":
        failed = [name for name, passed in result["checks"].items() if not passed]
        raise SystemExit("Southern finance release gates failed: " + ", ".join(failed))


if __name__ == "__main__":
    main()
