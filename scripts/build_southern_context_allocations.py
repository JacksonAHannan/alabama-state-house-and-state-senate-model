#!/usr/bin/env python3
"""Load national block assignments and aggregate warehouse presidential results."""
from __future__ import annotations

import argparse
import json
import re
import zipfile
from contextlib import closing
from pathlib import Path

import pandas as pd

from load_southern_context_warehouse import SOUTHERN_STATES, register_source, stable_id
from warehouse import ROOT, begin_run, connect, finish_run, initialize, register_table


SCHEMA = Path(__file__).with_name("warehouse_southern_context_allocation_schema.sql")
MANIFEST = ROOT / "data/processed/source_audits/southern_context_assignment_manifest.csv"
OUT = ROOT / "data/processed/presidential/southern_context_allocations"
RESULT_MANIFEST_ID = "RDH-NATIONAL-2020-PRES-BLOCKS"


def normalize_district(values: pd.Series) -> pd.Series:
    result = values.fillna("").astype(str).str.strip()
    invalid = result.str.upper().isin({"", "NO VALUE", "NO SLDL", "N/A", "NONE"})
    numeric = pd.to_numeric(result, errors="coerce")
    numeric_mask = numeric.notna() & numeric.mod(1).eq(0)
    result.loc[numeric_mask] = numeric.loc[numeric_mask].astype("Int64").astype(str)
    result.loc[invalid] = ""
    return result


def assignment_member(archive: zipfile.ZipFile) -> str:
    members = [name for name in archive.namelist() if name.lower().endswith("_baf.csv")]
    if len(members) != 1:
        raise ValueError(f"Expected exactly one block-assignment CSV, found {members}")
    return members[0]


def load_assignments(connection, row: dict, run_id: str) -> dict:
    path = ROOT / row["local_path"]
    source_file_id = row["source_file_id"]
    input_rows = output_rows = 0
    seen_states: set[str] = set()
    with zipfile.ZipFile(path) as archive:
        member = assignment_member(archive)
        with archive.open(member) as stream:
            for chunk in pd.read_csv(
                stream, usecols=["GEOID20", "STATE", "SLDU", "SLDL"], dtype=str,
                chunksize=150_000, low_memory=False,
            ):
                input_rows += len(chunk)
                chunk = chunk[chunk.STATE.isin(SOUTHERN_STATES)].copy()
                if chunk.empty:
                    continue
                chunk["GEOID20"] = chunk.GEOID20.str.zfill(15)
                if chunk.duplicated(["STATE", "GEOID20"]).any():
                    raise ValueError(f"Duplicate state/block assignment in {path}")
                chunk["lower"] = normalize_district(chunk.SLDL)
                chunk["upper"] = normalize_district(chunk.SLDU)
                records = [
                    (
                        source_file_id, run_id, int(row["cycle"]), item.STATE, item.GEOID20,
                        item.lower or None, item.upper or None,
                        "assigned" if item.lower else "unassigned",
                        "assigned" if item.upper else "unassigned",
                    )
                    for item in chunk[["STATE", "GEOID20", "lower", "upper"]].itertuples(index=False)
                ]
                connection.executemany(
                    "INSERT INTO bridge_southern_block_district_assignment VALUES (?,?,?,?,?,?,?,?,?)",
                    records,
                )
                output_rows += len(records)
                seen_states.update(chunk.STATE.unique())
    return {"national_input_rows": input_rows, "southern_rows": output_rows, "states": len(seen_states)}


def geometry_unit(connection, state: str, cycle: int, chamber: str, district: str) -> str | None:
    rows = connection.execute(
        """SELECT u.geography_unit_id
           FROM dim_southern_geography_unit u
           JOIN dim_southern_geography_layer l USING(geography_layer_id)
           WHERE u.state_code=? AND u.cycle=? AND u.chamber=? AND u.district=?
             AND l.validation_status='passed'""",
        (state, cycle, chamber, district),
    ).fetchall()
    if len(rows) > 1:
        raise ValueError(f"Multiple geometry units for {(state, cycle, chamber, district)}")
    return rows[0][0] if rows else None


def aggregate_results(connection, assignment_row: dict, result_source_file_id: str,
                      run_id: str) -> tuple[int, list[dict]]:
    assignment_source_file_id = assignment_row["source_file_id"]
    plan_cycle = int(assignment_row["cycle"])
    source = {
        row[0]: {"rows": row[1], "dem": row[2], "rep": row[3]}
        for row in connection.execute(
            """SELECT state_code,COUNT(*),SUM(dem_votes),SUM(rep_votes)
               FROM source_southern_presidential_geography_result
               WHERE source_file_id=? AND cycle=2020 AND geography_type='census_block'
               GROUP BY state_code""",
            (result_source_file_id,),
        )
    }
    inserted = 0
    audits: list[dict] = []
    for chamber, field in (("lower", "lower_district"), ("upper", "upper_district")):
        groups = connection.execute(
            f"""SELECT a.state_code,a.{field},COUNT(r.result_observation_id),
                       SUM(r.dem_votes),SUM(r.rep_votes),SUM(r.other_votes),SUM(r.total_votes)
                FROM bridge_southern_block_district_assignment a
                JOIN source_southern_presidential_geography_result r
                  ON r.source_file_id=? AND r.cycle=2020 AND r.geography_type='census_block'
                 AND r.state_code=a.state_code AND r.geography_id=a.block_geoid
                WHERE a.source_file_id=? AND a.{field} IS NOT NULL
                GROUP BY a.state_code,a.{field}
                ORDER BY a.state_code,a.{field}""",
            (result_source_file_id, assignment_source_file_id),
        ).fetchall()
        by_state: dict[str, dict[str, float]] = {}
        district_records = []
        for state, district, count, dem, rep, other, total in groups:
            stats = by_state.setdefault(state, {"rows": 0, "dem": 0.0, "rep": 0.0})
            stats["rows"] += int(count)
            stats["dem"] += float(dem)
            stats["rep"] += float(rep)
            margin = (float(dem) - float(rep)) / (float(dem) + float(rep)) if dem + rep else None
            unit = geometry_unit(connection, state, plan_cycle, chamber, district)
            district_records.append((
                stable_id(
                    "PRESDIST", result_source_file_id, assignment_source_file_id,
                    state, 2020, plan_cycle, chamber, district,
                ),
                run_id, result_source_file_id, assignment_source_file_id, 1, state, 2020,
                plan_cycle, chamber, district, unit, float(dem), float(rep), float(other),
                float(total), margin, int(count), "exact_2020_census_block_assignment", "passed",
            ))
        connection.executemany(
            "INSERT INTO mart_southern_presidential_district_result VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            district_records,
        )
        inserted += len(district_records)
        for state in sorted(source):
            assigned = by_state.get(state, {"rows": 0, "dem": 0.0, "rep": 0.0})
            source_two_party = float(source[state]["dem"] + source[state]["rep"])
            assigned_two_party = float(assigned["dem"] + assigned["rep"])
            unmatched = source_two_party - assigned_two_party
            coverage = assigned_two_party / source_two_party if source_two_party else None
            status = "exact" if abs(unmatched) <= 0.011 else (
                "within_rounding" if coverage is not None and coverage >= 0.999999 else "review"
            )
            connection.execute(
                "INSERT INTO qa_southern_presidential_district_allocation VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    result_source_file_id, assignment_source_file_id, run_id, state, 2020,
                    plan_cycle, chamber, int(source[state]["rows"]), int(assigned["rows"]),
                    float(source[state]["dem"]), float(assigned["dem"]), float(source[state]["rep"]),
                    float(assigned["rep"]), unmatched, coverage, status,
                ),
            )
            audits.append({
                "state_code": state, "plan_cycle": plan_cycle, "chamber": chamber,
                "coverage": coverage, "unmatched_two_party_votes": unmatched,
                "reconciliation_status": status,
            })
            if status == "review":
                connection.execute(
                    """UPDATE mart_southern_presidential_district_result
                       SET allocation_status='review'
                       WHERE result_source_file_id=? AND assignment_source_file_id=?
                         AND state_code=? AND chamber=?""",
                    (result_source_file_id, assignment_source_file_id, state, chamber),
                )
    return inserted, audits


def build(database: Path | None = None) -> dict:
    manifest = pd.read_csv(MANIFEST, dtype=str).fillna("")
    if len(manifest) != 2 or manifest.source_file_id.duplicated().any():
        raise ValueError("Assignment manifest must contain unique 2022 and 2024 sources")
    with closing(connect(database)) as connection:
        initialize(connection)
        connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        result_row = connection.execute(
            """SELECT source_file_id FROM source_southern_context_file
               WHERE manifest_source_file_id=? AND normalization_status='normalized'""",
            (RESULT_MANIFEST_ID,),
        ).fetchone()
        if result_row is None:
            raise ValueError("Normalized national 2020 block results are not present in the warehouse")
        result_source_file_id = result_row[0]
        run_id = begin_run(connection, "southern_presidential_district_allocations", {
            "contract_version": 1, "election_cycle": 2020,
            "plan_cycles": sorted(manifest.cycle.astype(int).tolist()),
            "assignment_manifest": MANIFEST.relative_to(ROOT).as_posix(),
        })
        connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DELETE FROM qa_southern_presidential_district_allocation")
        connection.execute("DELETE FROM mart_southern_presidential_district_result")
        connection.execute("DELETE FROM bridge_southern_block_district_assignment")
        connection.execute("DELETE FROM source_southern_assignment_file")
        assignment_rows = []
        assignment_stats = []
        for manifest_row in manifest.to_dict("records"):
            manifest_id = manifest_row["source_file_id"]
            warehouse_id = register_source(connection, manifest_row, normalized=True)
            row = {**manifest_row, "manifest_source_file_id": manifest_id, "source_file_id": warehouse_id}
            connection.execute(
                "INSERT INTO source_southern_assignment_file VALUES (?,?,?,?,?,?,?,?)",
                (
                    warehouse_id, manifest_id, int(row["cycle"]), row["geography_vintage"],
                    row["authoritative_scope"], "parsed", "load_assignments", None,
                ),
            )
            stats = load_assignments(connection, row, run_id)
            assignment_stats.append({"plan_cycle": int(row["cycle"]), **stats})
            assignment_rows.append(row)
        allocation_rows = 0
        all_audits = []
        for row in assignment_rows:
            count, audits = aggregate_results(connection, row, result_source_file_id, run_id)
            allocation_rows += count
            all_audits.extend(audits)
        duplicates = connection.execute(
            """SELECT COUNT(*) FROM (
              SELECT source_file_id,state_code,block_geoid,COUNT(*) n
              FROM bridge_southern_block_district_assignment
              GROUP BY 1,2,3 HAVING n>1)"""
        ).fetchone()[0]
        review_audits = sum(row["reconciliation_status"] == "review" for row in all_audits)
        bad_math = connection.execute(
            """SELECT COUNT(*) FROM mart_southern_presidential_district_result
               WHERE ABS(total_votes-(dem_votes+rep_votes+other_votes))>0.011"""
        ).fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        if duplicates or review_audits or bad_math or foreign_keys:
            raise ValueError(
                f"Allocation validation failed: duplicates={duplicates}, review={review_audits}, "
                f"vote_math={bad_math}, foreign_keys={foreign_keys[:5]}"
            )
        assignment_count = connection.execute(
            "SELECT COUNT(*) FROM bridge_southern_block_district_assignment"
        ).fetchone()[0]
        geometry_links = connection.execute(
            "SELECT COUNT(*) FROM mart_southern_presidential_district_result WHERE geography_unit_id IS NOT NULL"
        ).fetchone()[0]
        validation = {
            "assignment_sources": len(assignment_rows), "block_assignment_rows": assignment_count,
            "district_result_rows": allocation_rows, "geometry_linked_district_results": geometry_links,
            "allocation_audits": len(all_audits), "review_audits": review_audits,
            "minimum_two_party_vote_coverage": min(row["coverage"] for row in all_audits),
            "assignment_stats": assignment_stats,
        }
        for name, layer, key_value, authority, lifecycle, description in [
            ("source_southern_assignment_file", "source", "source_file_id",
             "Manifest-backed RDH national assignment archives", "replace",
             "Block assignment source metadata and parser status"),
            ("bridge_southern_block_district_assignment", "canonical",
             "source_file_id + state_code + block_geoid",
             "Provider assignment retained exactly; unassigned remains explicit", "replace",
             "Compact one-row-per-block lower/upper legislative assignment bridge"),
            ("mart_southern_presidential_district_result", "mart",
             "result source + assignment source + state/election/plan/chamber/district",
             "Only reconciled block results and explicit BAF assignments", "replace",
             "Presidential totals aggregated onto versioned legislative plans"),
            ("fact_southern_presidential_district_result", "canonical", "district_result_id",
             "Only allocation_status passed", "view",
             "Validated plan-aware presidential district results"),
            ("qa_southern_presidential_district_allocation", "qa",
             "result source + assignment source + state + chamber",
             "Statewide vote conservation by plan and chamber", "replace",
             "Block allocation coverage and reconciliation diagnostics"),
        ]:
            register_table(connection, name, layer, "scripts/build_southern_context_allocations.py",
                           key_value, authority, lifecycle, description)
        finish_run(connection, run_id, validation)
        connection.commit()

    OUT.mkdir(parents=True, exist_ok=True)
    with closing(connect(database, readonly=True)) as connection:
        districts = pd.read_sql_query(
            "SELECT * FROM fact_southern_presidential_district_result ORDER BY plan_cycle,state_code,chamber,district",
            connection,
        )
        audit = pd.read_sql_query(
            "SELECT * FROM qa_southern_presidential_district_allocation ORDER BY plan_cycle,state_code,chamber",
            connection,
        )
    districts.to_csv(OUT / "presidential_district_results.csv", index=False)
    audit.to_csv(OUT / "allocation_reconciliation.csv", index=False)
    output_manifest = {
        "contract_version": 1, "build_run_id": run_id,
        "pipeline": "scripts/build_southern_context_allocations.py", "validation": validation,
        "outputs": [
            "data/processed/presidential/southern_context_allocations/presidential_district_results.csv",
            "data/processed/presidential/southern_context_allocations/allocation_reconciliation.csv",
        ],
    }
    (OUT / "manifest.json").write_text(json.dumps(output_manifest, indent=2) + "\n", encoding="utf-8")
    return output_manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.database)["validation"], indent=2))


if __name__ == "__main__":
    main()
