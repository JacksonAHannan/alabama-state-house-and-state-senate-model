#!/usr/bin/env python3
"""Load only district-complete Mississippi 2012 presidential context.

Every accepted precinct match is allocated through the exact 2019 plan using
2020 modified VAP.  An unresolved result may be assigned only when all of its
plausible 2012 donor geometries lie in one district for the chamber.  Districts
touched by any genuinely ambiguous result remain review-only and are excluded
from the central fact view.
"""
from __future__ import annotations

import argparse
import json
from contextlib import closing
from pathlib import Path

import geopandas as gpd
import pandas as pd

from audit_mississippi_2012_precinct_plan_readiness import (
    GEOMETRY, OUT as AUDIT_OUT, donor_rows, match_results, result_rows, validate_alias_source,
)
from build_southern_2016_vest_plan_allocation import BLOCK_MANIFEST, load_vap
from build_southern_historical_plan_allocations import assign_blocks_to_plan, plan_geometry
from load_southern_context_warehouse import register_source, stable_id
from warehouse import ROOT, begin_run, connect, finish_run, initialize, register_table


SCHEMA = Path(__file__).with_name("warehouse_mississippi_2012_district_readiness_schema.sql")
GEOMETRY_MANIFEST = ROOT / "data/processed/source_audits/southern_2012_precinct_geography_manifest.csv"
OUT = ROOT / "data/processed/presidential/mississippi_2012_partial_plan_allocations"


def plan_weights(blocks: gpd.GeoDataFrame, donors: gpd.GeoDataFrame,
                 districts: gpd.GeoDataFrame) -> tuple[pd.DataFrame, dict]:
    plan_match, plan_audit = assign_blocks_to_plan(blocks, districts)
    points = gpd.GeoDataFrame(
        blocks[["GEOID20", "VAP_MOD"]], geometry=blocks.geometry.representative_point(), crs=blocks.crs,
    )
    donor_shapes = donors[["donor_id", "geometry"]].to_crs(blocks.crs).copy()
    donor_shapes.geometry = donor_shapes.geometry.make_valid()
    joined = gpd.sjoin(points, donor_shapes, how="inner", predicate="within").reset_index(names="block_index")
    joined = joined.merge(plan_match, on="block_index", validate="many_to_one")
    primary = joined[joined.VAP_MOD.gt(0)].groupby(["donor_id", "district"], as_index=False).agg(
        basis=("VAP_MOD", "sum"), contributing_blocks=("GEOID20", "nunique")
    )
    primary["weight_basis"] = "2020_vap"
    missing = set(donor_shapes.donor_id) - set(primary.donor_id)
    fallback = []
    district_lookup = districts.set_index("district").geometry
    donor_lookup = donor_shapes.set_index("donor_id").geometry
    for donor_id in sorted(missing):
        shape = donor_lookup.loc[donor_id]
        for district, district_shape in district_lookup.items():
            area = shape.intersection(district_shape).area
            if area > 0:
                fallback.append({"donor_id": donor_id, "district": str(district), "basis": float(area),
                                 "contributing_blocks": 0, "weight_basis": "geometry_intersection_area"})
    weights = pd.concat([primary, pd.DataFrame(fallback)], ignore_index=True)
    if set(donor_shapes.donor_id) - set(weights.donor_id):
        raise ValueError("At least one Mississippi donor geometry has no plan weight")
    weights["allocation_weight"] = weights.basis / weights.groupby("donor_id").basis.transform("sum")
    error = float((weights.groupby("donor_id").allocation_weight.sum() - 1).abs().max())
    if error > 1e-10:
        raise ValueError(f"Mississippi donor weights do not sum to one: {error}")
    return weights, {**plan_audit, "max_donor_weight_error": error, "fallback_donors": len(missing)}


def geography_unit(connection, layer_id: str, district: str) -> str:
    row = connection.execute(
        "SELECT geography_unit_id FROM dim_southern_geography_unit WHERE geography_layer_id=? AND district=?",
        (layer_id, str(district)),
    ).fetchone()
    if row is None:
        raise ValueError(f"Missing geography unit for {layer_id}/{district}")
    return row[0]


def build(database: Path | None = None) -> dict:
    geometry_manifest = pd.read_csv(GEOMETRY_MANIFEST, dtype=str).fillna("")
    geometry_row = geometry_manifest[geometry_manifest.state_code.eq("MS")]
    if len(geometry_row) != 1:
        raise ValueError("Expected one registered Mississippi 2012 geometry source")
    geometry_row = geometry_row.iloc[0].to_dict()
    alias_row = validate_alias_source()
    block_manifest = pd.read_csv(BLOCK_MANIFEST, dtype=str).fillna("").set_index("state_code")
    vap = load_vap({"MS"})["MS"]
    block_path = (ROOT / block_manifest.loc["MS"].local_path).resolve()
    blocks = gpd.read_file(f"zip://{block_path.as_posix()}", columns=["GEOID20", "geometry"])
    blocks["GEOID20"] = blocks.GEOID20.astype(str).str.zfill(15)
    blocks = blocks.merge(vap, on="GEOID20", validate="one_to_one").to_crs(5070)

    with closing(connect(database)) as connection:
        initialize(connection)
        connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        results = result_rows(connection)
        donors = donor_rows(results)
        matches = match_results(results, donors)
        source_ids = pd.read_sql_query(
            "SELECT DISTINCT source_file_id FROM fact_southern_presidential_geography_result "
            "WHERE state_code='MS' AND cycle=2012", connection,
        ).source_file_id.tolist()
        if len(source_ids) != 1:
            raise ValueError(f"Expected one Mississippi result source, found {source_ids}")
        result_source_id = source_ids[0]
        geometry_source_id = register_source(connection, geometry_row, normalized=True)
        alias_source_id = register_source(connection, alias_row, normalized=False)
        cells = pd.read_sql_query(
            """SELECT assignment_source_file_id,geography_layer_id,chamber,plan_cycle
               FROM source_southern_spatial_plan_assignment
               WHERE state_code='MS' AND plan_cycle=2019 ORDER BY chamber""", connection,
        )
        if len(cells) != 2:
            raise ValueError("Expected exact Mississippi 2019 House and Senate plans")
        run_id = begin_run(connection, "mississippi_2012_partial_plan_allocations", {
            "contract_version": 1,
            "match_policy": "within-county one-to-one; exact native/same-code aliases; conservative fuzzy",
            "readiness_policy": "passed only when no unresolved plausible donor crosses into district",
            "spatial_weight": "2020 modified VAP; geometry-area fallback only without positive-VAP blocks",
            "alias_source_file_id": alias_source_id,
        })
        connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        assignment_ids = cells.assignment_source_file_id.tolist()
        marks = ",".join("?" for _ in assignment_ids)
        connection.execute(
            f"DELETE FROM mart_southern_presidential_district_result WHERE state_code='MS' "
            f"AND election_cycle=2012 AND assignment_source_file_id IN ({marks})", assignment_ids,
        )
        connection.execute(
            f"DELETE FROM qa_southern_presidential_district_allocation WHERE state_code='MS' "
            f"AND election_cycle=2012 AND assignment_source_file_id IN ({marks})", assignment_ids,
        )
        connection.execute("DELETE FROM qa_southern_presidential_precinct_match")
        connection.execute("DELETE FROM qa_southern_presidential_district_readiness WHERE state_code='MS' AND election_cycle=2012")
        connection.execute(
            """INSERT INTO source_southern_precinct_geometry_file VALUES (?,?,?,?,?,?)
               ON CONFLICT(source_file_id) DO UPDATE SET geography_vintage=excluded.geography_vintage,
                 shapefile_member=excluded.shapefile_member,validation_status=excluded.validation_status""",
            (geometry_source_id, "MS", 2012, geometry_row["geography_vintage"], "precincts_12.shp", "review"),
        )
        match_records = []
        for row in matches.itertuples(index=False):
            match_records.append((
                run_id, row.result_observation_id, result_source_id, geometry_source_id, "MS", 2012,
                row.county_key, row.precinct_name_original, row.donor_id, row.donor_name,
                row.match_method, float(row.match_score), float(row.row_score_margin),
                row.plausible_donor_ids_json, float(row.two_party_votes),
                "passed" if pd.notna(row.donor_id) else "review",
            ))
        connection.executemany(
            "INSERT INTO qa_southern_presidential_precinct_match VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            match_records,
        )

        district_records = []
        readiness_records = []
        cell_audits = []
        passed_districts = 0
        for cell in cells.itertuples(index=False):
            districts = plan_geometry(connection, cell.geography_layer_id)
            weights, spatial_audit = plan_weights(blocks, donors, districts)
            accepted = matches[matches.donor_id.notna()].merge(
                weights, on="donor_id", how="left", validate="many_to_many",
            )
            accepted["assignment_kind"] = "accepted_precinct_match"
            deterministic = []
            ambiguous = []
            for row in matches[matches.donor_id.isna()].itertuples(index=False):
                plausible_ids = json.loads(row.plausible_donor_ids_json)
                candidate_weights = weights[weights.donor_id.isin(plausible_ids)]
                plausible_districts = sorted(set(candidate_weights.district), key=lambda value: int(value))
                if len(plausible_districts) == 1:
                    deterministic.append({**row._asdict(), "district": plausible_districts[0],
                                          "allocation_weight": 1.0,
                                          "assignment_kind": "unresolved_name_single_plausible_district"})
                else:
                    for district in plausible_districts:
                        ambiguous.append({"district": str(district), "result_observation_id": row.result_observation_id,
                                          "two_party_votes": float(row.two_party_votes)})
            allocated = pd.concat([accepted, pd.DataFrame(deterministic)], ignore_index=True, sort=False)
            allocated["weighted_dem"] = allocated.dem_votes * allocated.allocation_weight
            allocated["weighted_rep"] = allocated.rep_votes * allocated.allocation_weight
            allocated["weighted_other"] = allocated.other_votes * allocated.allocation_weight
            grouped = allocated.groupby("district", as_index=False).agg(
                dem_votes=("weighted_dem", "sum"), rep_votes=("weighted_rep", "sum"),
                other_votes=("weighted_other", "sum"),
                allocated_result_geographies=("result_observation_id", "nunique"),
            )
            grouped["total_votes"] = grouped.dem_votes + grouped.rep_votes + grouped.other_votes
            ambiguous_frame = pd.DataFrame(ambiguous)
            if ambiguous_frame.empty:
                ambiguous_summary = pd.DataFrame(columns=["district", "ambiguous_result_rows", "ambiguous_two_party_votes"])
            else:
                ambiguous_summary = ambiguous_frame.groupby("district", as_index=False).agg(
                    ambiguous_result_rows=("result_observation_id", "nunique"),
                    ambiguous_two_party_votes=("two_party_votes", "sum"),
                )
            readiness = pd.DataFrame({"district": districts.district.astype(str).sort_values().unique()})
            readiness = readiness.merge(ambiguous_summary, on="district", how="left", validate="one_to_one").fillna(0)
            readiness["validation_status"] = readiness.ambiguous_result_rows.eq(0).map({True: "passed", False: "review"})
            passed_districts += int(readiness.validation_status.eq("passed").sum())
            status_lookup = readiness.set_index("district").validation_status.to_dict()
            grouped["district"] = grouped.district.astype(str)
            for row in grouped.itertuples(index=False):
                status = status_lookup[row.district]
                denominator = row.dem_votes + row.rep_votes
                margin = (row.dem_votes - row.rep_votes) / denominator if denominator else None
                district_records.append((
                    stable_id("PRESDIST", result_source_id, cell.assignment_source_file_id, "MS", 2012,
                              int(cell.plan_cycle), cell.chamber, row.district),
                    run_id, result_source_id, cell.assignment_source_file_id, 1, "MS", 2012,
                    int(cell.plan_cycle), cell.chamber, row.district,
                    geography_unit(connection, cell.geography_layer_id, row.district),
                    float(row.dem_votes), float(row.rep_votes), float(row.other_votes), float(row.total_votes),
                    margin, int(row.allocated_result_geographies),
                    "2012_precinct_match_vap_weighted_with_district_specific_readiness", status,
                ))
            for row in readiness.itertuples(index=False):
                readiness_records.append((
                    run_id, result_source_id, geometry_source_id, cell.assignment_source_file_id, "MS", 2012,
                    int(cell.plan_cycle), cell.chamber, row.district, int(row.ambiguous_result_rows),
                    float(row.ambiguous_two_party_votes), row.validation_status,
                    "Passed means no unresolved 2012 result has a plausible donor geometry in this district.",
                ))
            allocated_dem = float(grouped.dem_votes.sum())
            allocated_rep = float(grouped.rep_votes.sum())
            source_dem = float(matches.dem_votes.sum())
            source_rep = float(matches.rep_votes.sum())
            unmatched = (source_dem + source_rep) - (allocated_dem + allocated_rep)
            connection.execute(
                "INSERT INTO qa_southern_presidential_district_allocation VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (result_source_id, cell.assignment_source_file_id, run_id, "MS", 2012, int(cell.plan_cycle),
                 cell.chamber, len(matches), allocated.result_observation_id.nunique(), source_dem, allocated_dem,
                 source_rep, allocated_rep, unmatched, (allocated_dem + allocated_rep) / (source_dem + source_rep),
                 "review"),
            )
            cell_audits.append({
                "chamber": cell.chamber, "districts": len(readiness),
                "passed_districts": int(readiness.validation_status.eq("passed").sum()),
                "review_districts": int(readiness.validation_status.eq("review").sum()),
                "unallocated_two_party_votes": unmatched, **spatial_audit,
            })
        connection.executemany(
            "INSERT INTO mart_southern_presidential_district_result VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            district_records,
        )
        connection.executemany(
            "INSERT INTO qa_southern_presidential_district_readiness VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            readiness_records,
        )
        for args in [
            ("qa_southern_presidential_precinct_match", "qa", "scripts/build_mississippi_2012_partial_plan_allocations.py",
             "build run + result observation", "one audited match per 2012 Mississippi result", "replace",
             "Conservative result-name to exact-vintage donor-geometry audit"),
            ("qa_southern_presidential_district_readiness", "qa", "scripts/build_mississippi_2012_partial_plan_allocations.py",
             "source + assignment + district", "district may pass only with zero plausible ambiguous exposure", "replace",
             "District-level gate for partial historical presidential allocation"),
        ]:
            register_table(connection, *args)
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_keys:
            raise ValueError(f"Foreign-key failure: {foreign_keys[:5]}")
        validation = {
            "result_rows": len(matches), "matched_rows": int(matches.donor_id.notna().sum()),
            "unresolved_rows": int(matches.donor_id.isna().sum()),
            "district_rows": len(district_records), "passed_districts": passed_districts,
            "review_districts": len(readiness_records) - passed_districts,
            "alias_source_file_id": alias_source_id, "cells": cell_audits,
        }
        finish_run(connection, run_id, validation)
        connection.commit()
        readiness_export = pd.read_sql_query(
            """SELECT build_run_id,state_code,election_cycle,plan_cycle,chamber,district,
                      ambiguous_result_rows,ambiguous_two_party_votes,validation_status,note
               FROM qa_southern_presidential_district_readiness
               WHERE build_run_id=? ORDER BY chamber,CAST(district AS INTEGER)""",
            connection, params=(run_id,),
        )
        blocked_races = pd.read_sql_query(
            """SELECT r.war_outcome_id,r.state_code,r.cycle,r.chamber,r.district,
                      r.dem_candidate_name,r.rep_candidate_name,
                      d.ambiguous_result_rows,d.ambiguous_two_party_votes,
                      d.validation_status,d.build_run_id
               FROM mart_southern_war_training_no_finance r
               JOIN qa_southern_presidential_district_readiness d
                 ON d.state_code=r.state_code AND d.plan_cycle=r.cycle
                AND d.chamber=r.chamber AND d.district=r.district
               WHERE r.state_code='MS' AND r.cycle=2019
                 AND r.training_status='strict_war_ready_no_finance'
                 AND d.build_run_id=? AND d.validation_status='review'
               ORDER BY r.chamber,CAST(r.district AS INTEGER)""",
            connection, params=(run_id,),
        )
        blocked_races["blocking_reason"] = (
            "unresolved 2012 result has plausible donor geometry in multiple 2019-plan districts"
        )
        blocked_races["resolution_needed"] = (
            "official precinct identity evidence or validated 2012 result-to-precinct crosswalk"
        )

    OUT.mkdir(parents=True, exist_ok=True)
    AUDIT_OUT.mkdir(parents=True, exist_ok=True)
    matches.drop(columns="county_name_original").to_csv(AUDIT_OUT / "precinct_matches.csv", index=False)
    manifest = {"contract_version": 2, "build_run_id": run_id,
                "pipeline": "scripts/build_mississippi_2012_partial_plan_allocations.py",
                "alias_source_file_id": alias_source_id,
                "validation": validation}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    pd.DataFrame(cell_audits).to_csv(OUT / "allocation_validation.csv", index=False)
    readiness_export.to_csv(OUT / "district_readiness.csv", index=False)
    blocked_races.to_csv(OUT / "war_blocked_races.csv", index=False)
    return validation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.database), indent=2))


if __name__ == "__main__":
    main()
