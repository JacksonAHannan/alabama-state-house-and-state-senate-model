#!/usr/bin/env python3
"""Correct the documented Harrison County D/R transposition in normalized data."""
from __future__ import annotations

import argparse
import json
from contextlib import closing
from pathlib import Path

import pandas as pd

from load_southern_context_warehouse import register_source, stable_id
from warehouse import ROOT, begin_run, connect, finish_run, initialize, register_table, utcnow


SCHEMA = Path(__file__).with_name("warehouse_southern_presidential_correction_schema.sql")
MANIFEST = ROOT / "data/processed/source_audits/mississippi_2012_county_results_manifest.csv"


def evidence_totals(path: Path) -> tuple[float, float]:
    frame = pd.read_csv(path)
    selected = frame[
        frame.office.eq("President") & frame.county.eq("Harrison")
        & frame.party.isin(["Democrat", "Republican"])
    ]
    totals = selected.groupby("party").votes.sum()
    if set(totals.index) != {"Democrat", "Republican"}:
        raise ValueError("Harrison county evidence lacks both major parties")
    return float(totals["Democrat"]), float(totals["Republican"])


def repair(database: Path | None = None) -> dict[str, object]:
    manifest = pd.read_csv(MANIFEST, dtype=str).fillna("").iloc[0].to_dict()
    expected_dem, expected_rep = evidence_totals(ROOT / manifest["local_path"])
    with closing(connect(database)) as connection:
        initialize(connection)
        connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        evidence_source = register_source(connection, manifest, normalized=False)
        source_row = connection.execute(
            """SELECT source_file_id FROM source_southern_context_file
               WHERE manifest_source_file_id='OPENELECTIONS-2012-MS-PRECINCT'"""
        ).fetchone()
        if source_row is None:
            raise ValueError("Mississippi 2012 precinct source is not registered")
        result_source = source_row[0]
        current = connection.execute(
            """SELECT COUNT(*),SUM(dem_votes),SUM(rep_votes)
               FROM source_southern_presidential_geography_result
               WHERE source_file_id=? AND state_code='MS' AND cycle=2012
                 AND county_key='HARRISON'""", (result_source,),
        ).fetchone()
        affected, pre_dem, pre_rep = int(current[0]), float(current[1]), float(current[2])
        already_correct = abs(pre_dem - expected_dem) < 0.01 and abs(pre_rep - expected_rep) < 0.01
        transposed = abs(pre_dem - expected_rep) < 0.01 and abs(pre_rep - expected_dem) < 0.01
        if not already_correct and not transposed:
            raise ValueError(
                f"Harrison totals are neither corrected nor transposed: D={pre_dem}, R={pre_rep}"
            )
        connection.execute(
            """UPDATE warehouse_build_run
               SET completed_at_utc=?,status='failed',validation_json=?
               WHERE target='mississippi_2012_presidential_party_correction'
                 AND status='running'""",
            (utcnow(), json.dumps({"reason": "superseded after an aborted correction transaction"})),
        )
        run_id = begin_run(connection, "mississippi_2012_presidential_party_correction", {
            "contract_version": 1,
            "result_source_file_id": result_source,
            "evidence_source_file_id": evidence_source,
            "county_key": "HARRISON",
        })
        connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        if transposed:
            connection.execute(
                """UPDATE source_southern_presidential_geography_result
                   SET dem_votes=rep_votes,
                       rep_votes=dem_votes,
                       two_party_dem_margin=(rep_votes-dem_votes)/(dem_votes+rep_votes),
                       allocation_method='provider_precinct_corrected_harrison_dr_transposition',
                       build_run_id=?
                   WHERE source_file_id=? AND state_code='MS' AND cycle=2012
                     AND county_key='HARRISON'""", (run_id, result_source),
            )
        post = connection.execute(
            """SELECT SUM(dem_votes),SUM(rep_votes)
               FROM source_southern_presidential_geography_result
               WHERE source_file_id=? AND state_code='MS' AND cycle=2012
                 AND county_key='HARRISON'""", (result_source,),
        ).fetchone()
        post_dem, post_rep = float(post[0]), float(post[1])
        statewide = connection.execute(
            """SELECT SUM(dem_votes),SUM(rep_votes)
               FROM fact_southern_presidential_geography_result
               WHERE source_file_id=? AND state_code='MS' AND cycle=2012""", (result_source,),
        ).fetchone()
        status = "passed" if (
            abs(post_dem - expected_dem) < 0.01 and abs(post_rep - expected_rep) < 0.01
            and abs(float(statewide[0]) - 562_949) < 0.01
            and abs(float(statewide[1]) - 710_746) < 0.01
        ) else "review"
        correction_id = stable_id("PRESCORR", result_source, evidence_source, "MS", 2012, "HARRISON")
        connection.execute("DELETE FROM qa_southern_presidential_result_correction WHERE correction_id=?", (correction_id,))
        connection.execute(
            """INSERT INTO qa_southern_presidential_result_correction
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (correction_id, run_id, result_source, evidence_source, "MS", 2012, "HARRISON",
             "swap_dem_rep_vote_values_within_each_precinct", affected, pre_dem, pre_rep,
             post_dem, post_rep, expected_dem, expected_rep, status,
             "Companion county result and certified statewide totals identify a complete D/R transposition."),
        )
        if status != "passed":
            raise ValueError(f"Mississippi correction did not reconcile: statewide={tuple(statewide)}")
        validation = {
            "affected_result_rows": affected,
            "harrison_dem_votes": post_dem,
            "harrison_rep_votes": post_rep,
            "statewide_dem_votes": float(statewide[0]),
            "statewide_rep_votes": float(statewide[1]),
            "validation_status": status,
        }
        register_table(
            connection, "qa_southern_presidential_result_correction", "qa",
            "scripts/repair_mississippi_2012_presidential_party_assignment.py",
            "correction_id", "one evidence-backed correction audit", "replace",
            "Provider conversion correction with pre/post and evidence totals",
        )
        finish_run(connection, run_id, validation)
        connection.commit()
    return validation


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path)
    args = parser.parse_args()
    print(json.dumps(repair(args.database), indent=2))
