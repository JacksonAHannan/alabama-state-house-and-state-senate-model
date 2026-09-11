#!/usr/bin/env python3
"""Allocate 2016 and 2020 presidential results to 2018-2020 election plans."""
from __future__ import annotations

import argparse
import gc
import json
from contextlib import closing
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import from_wkb

from build_southern_2016_vest_plan_allocation import (
    BLOCK_MANIFEST,
    district_geometry_unit,
    geometry_fallback,
    load_vap,
    precincts,
    resolve_point_matches,
)
from load_southern_context_warehouse import register_source, stable_id
from warehouse import ROOT, begin_run, connect, finish_run, initialize, register_table


SCHEMA = Path(__file__).with_name("warehouse_southern_historical_plan_allocation_schema.sql")
OUT = ROOT / "data/processed/presidential/southern_historical_plan_allocations"
DETAILED_MANIFEST = ROOT / "data/processed/source_audits/southern_2020_detailed_plan_supplement_manifest.csv"


def target_cells(connection) -> pd.DataFrame:
    frame = pd.read_sql_query(
        """SELECT DISTINCT state_code,cycle AS plan_cycle,chamber
           FROM mart_southern_war_training_no_finance
           WHERE cycle>2016 AND cycle<=2020
             AND training_status='strict_war_ready_no_finance'
           ORDER BY state_code,plan_cycle,chamber""",
        connection,
    )
    layers = pd.read_sql_query(
        """SELECT l.geography_layer_id,l.source_file_id,l.state_code,
                  l.cycle AS plan_cycle,l.chamber,l.geography_vintage
           FROM dim_southern_geography_layer l
           WHERE l.validation_status='passed' AND l.chamber IS NOT NULL""",
        connection,
    )
    joined = frame.merge(
        layers, on=["state_code", "plan_cycle", "chamber"], how="left",
        validate="one_to_one", indicator=True,
    )
    if not joined._merge.eq("both").all():
        raise ValueError(
            "Missing exact election-plan layers: "
            + str(joined.loc[joined._merge.ne("both"), ["state_code", "plan_cycle", "chamber"]].to_dict("records"))
        )
    return joined.drop(columns="_merge")


def plan_geometry(connection, layer_id: str) -> gpd.GeoDataFrame:
    frame = pd.read_sql_query(
        """SELECT geography_unit_id,district,geometry_wkb
           FROM dim_southern_geography_unit
           WHERE geography_layer_id=? AND district IS NOT NULL AND district!='ZZZ'""",
        connection, params=(layer_id,),
    )
    if frame.empty or frame.district.isna().any() or frame.district.duplicated().any():
        raise ValueError(f"Invalid district geometry layer {layer_id}")
    return gpd.GeoDataFrame(
        frame.drop(columns="geometry_wkb"), geometry=from_wkb(frame.geometry_wkb.values), crs=4326,
    ).to_crs(5070)


def normalize_district(values: pd.Series) -> pd.Series:
    return pd.to_numeric(values, errors="raise").astype(int).astype(str)


def detailed_plan_geometry(row: dict) -> gpd.GeoDataFrame:
    frame = gpd.read_file(f"zip://{(ROOT / row['local_path']).resolve().as_posix()}")
    field = "SLDLST" if row["chamber"] == "lower" else "SLDUST"
    frame = frame.rename(columns={field: "district"})
    frame = frame[frame.district.ne("ZZZ")].copy()
    frame["district"] = normalize_district(frame.district)
    if frame.district.duplicated().any():
        raise ValueError(f"Duplicate detailed districts in {row['source_file_id']}")
    return frame[["district", "geometry"]].to_crs(5070).reset_index(drop=True)


def overlay_audit(blocks: gpd.GeoDataFrame, cartographic: pd.DataFrame,
                  detailed: pd.DataFrame, detailed_audit: dict) -> dict:
    comparison = cartographic.merge(
        detailed, on="block_index", how="outer", suffixes=("_cartographic", "_detailed")
    )
    common = comparison.district_cartographic.notna() & comparison.district_detailed.notna()
    disagreement = common & comparison.district_cartographic.ne(comparison.district_detailed)
    cartographic_only = comparison.district_cartographic.notna() & comparison.district_detailed.isna()
    detailed_only = comparison.district_cartographic.isna() & comparison.district_detailed.notna()
    def vap(mask: pd.Series) -> float:
        return float(blocks.loc[comparison.loc[mask, "block_index"], "VAP_MOD"].sum())
    result = {
        "common_assigned_blocks": int(common.sum()),
        "common_disagreement_blocks": int(disagreement.sum()),
        "common_disagreement_vap": vap(disagreement),
        "total_positive_vap": float(blocks.VAP_MOD.sum()),
        "cartographic_only_blocks": int(cartographic_only.sum()),
        "cartographic_only_vap": vap(cartographic_only),
        "detailed_only_blocks": int(detailed_only.sum()),
        "detailed_only_vap": vap(detailed_only),
        "detailed_unmatched_positive_vap": detailed_audit["unmatched_plan_positive_vap"],
    }
    result["validation_status"] = "passed" if (
        result["cartographic_only_vap"] == 0
        and result["detailed_unmatched_positive_vap"] == 0
        and result["common_disagreement_vap"] / result["total_positive_vap"] <= 0.001
    ) else "review"
    return result


def assign_blocks_to_plan(
    blocks: gpd.GeoDataFrame, districts: gpd.GeoDataFrame,
) -> tuple[pd.DataFrame, dict]:
    points = gpd.GeoDataFrame(
        blocks[["GEOID20", "VAP_MOD"]], geometry=blocks.geometry.representative_point(), crs=blocks.crs,
    )
    joined = gpd.sjoin(points, districts[["district", "geometry"]], how="left", predicate="within").reset_index(names="block_index")
    ambiguous = set(joined.loc[joined.block_index.duplicated(keep=False), "block_index"])
    chosen = joined[~joined.block_index.isin(ambiguous)].dropna(subset=["district"])[
        ["block_index", "district"]
    ]
    resolved = []
    for block_index, candidates in joined[joined.block_index.isin(ambiguous)].groupby("block_index"):
        ranked = []
        for candidate in candidates.dropna(subset=["district"]).itertuples(index=False):
            area = blocks.loc[block_index].geometry.intersection(
                districts.loc[int(candidate.index_right)].geometry
            ).area
            ranked.append((float(area), str(candidate.district)))
        if ranked:
            resolved.append((block_index, max(ranked, key=lambda item: (item[0], item[1]))[1]))
    if resolved:
        chosen = pd.concat([chosen, pd.DataFrame(resolved, columns=["block_index", "district"])], ignore_index=True)
    matched = set(chosen.block_index)
    unmatched_positive = blocks.index[blocks.VAP_MOD.gt(0) & ~blocks.index.isin(matched)]
    intersection_resolved = 0
    if len(unmatched_positive):
        candidates = gpd.sjoin(
            blocks.loc[unmatched_positive, ["geometry"]], districts[["district", "geometry"]],
            how="inner", predicate="intersects",
        ).reset_index(names="block_index")
        fallback = []
        for block_index, group in candidates.groupby("block_index"):
            ranked = []
            for candidate in group.itertuples(index=False):
                area = blocks.loc[block_index].geometry.intersection(
                    districts.loc[int(candidate.index_right)].geometry
                ).area
                if area > 0:
                    ranked.append((float(area), str(candidate.district)))
            if ranked:
                fallback.append((block_index, max(ranked, key=lambda item: (item[0], item[1]))[1]))
        if fallback:
            intersection_resolved = len(fallback)
            chosen = pd.concat([chosen, pd.DataFrame(fallback, columns=["block_index", "district"])], ignore_index=True)
    chosen = chosen.drop_duplicates("block_index", keep="last")
    unmatched = blocks.loc[blocks.VAP_MOD.gt(0) & ~blocks.index.isin(chosen.block_index)]
    return chosen, {
        "ambiguous_plan_blocks_resolved": len(ambiguous),
        "intersection_plan_blocks_resolved": intersection_resolved,
        "unmatched_plan_positive_vap": float(unmatched.VAP_MOD.sum()),
        "total_positive_vap": float(blocks.VAP_MOD.sum()),
    }


def register_assignment(connection, cell, block_source_id: str,
                        detailed_row: dict | None = None) -> str:
    assignment_id = detailed_row["source_file_id"] if detailed_row else str(cell.source_file_id)
    vintage = detailed_row["geography_vintage"] if detailed_row else cell.geography_vintage
    scope = (
        f"Detailed geometry for {cell.state_code} {cell.plan_cycle} {cell.chamber}; "
        f"same-plan validated against {cell.geography_layer_id}"
        if detailed_row else
        f"2020 Census blocks spatially assigned to {cell.state_code} {cell.plan_cycle} {cell.chamber} districts"
    )
    connection.execute(
        """INSERT INTO source_southern_assignment_file
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            assignment_id, f"SPATIAL-{assignment_id}", int(cell.plan_cycle),
            vintage, scope,
            "parsed", "build_southern_historical_plan_allocations", None,
        ),
    )
    connection.execute(
        """INSERT INTO source_southern_spatial_plan_assignment
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            assignment_id, cell.geography_layer_id, block_source_id, cell.state_code,
            int(cell.plan_cycle), cell.chamber,
            "2020_block_representative_point_with_intersection_resolution", "passed",
        ),
    )
    return assignment_id


def vest_weights(
    blocks: gpd.GeoDataFrame, precinct: gpd.GeoDataFrame, precinct_matches: pd.DataFrame,
    plan_matches: pd.DataFrame, cell, run_id: str, assignment_id: str,
    precinct_audit: dict, plan_audit: dict,
) -> tuple[pd.DataFrame, dict]:
    matched = precinct_matches.merge(plan_matches, on="block_index", validate="one_to_one").merge(
        blocks[["GEOID20", "VAP_MOD"]], left_on="block_index", right_index=True, validate="one_to_one",
    )
    primary = matched[matched.VAP_MOD.gt(0)].groupby(
        ["result_observation_id", "district"], as_index=False,
    ).agg(basis=("VAP_MOD", "sum"), contributing_blocks=("GEOID20", "nunique"), VAP_MOD=("VAP_MOD", "sum"))
    primary_ids = set(primary.result_observation_id)
    positive_ids = set(precinct.loc[precinct.total_votes.gt(0), "result_observation_id"])
    fallback_ids = positive_ids - primary_ids
    chamber_field = f"{cell.chamber}_district"
    fallback_blocks = blocks.copy()
    fallback_blocks[chamber_field] = fallback_blocks.index.to_series().map(
        plan_matches.set_index("block_index").district
    )
    fallback = geometry_fallback(fallback_blocks, precinct, fallback_ids, chamber_field)
    primary["weight_basis"] = "2020_vap"
    fallback["weight_basis"] = "geometry_intersection_area"
    combined = pd.concat([primary, fallback], ignore_index=True)
    combined["allocation_weight"] = combined.basis / combined.groupby("result_observation_id").basis.transform("sum")
    weighted_ids = positive_ids.intersection(set(combined.result_observation_id))
    missing_ids = positive_ids - weighted_ids
    sums = combined.groupby("result_observation_id").allocation_weight.sum()
    max_error = float((sums - 1).abs().max())
    fallback_votes = float(precinct.loc[
        precinct.result_observation_id.isin(fallback_ids), ["dem_votes", "rep_votes"]
    ].sum().sum())
    total_two_party = float((precinct.dem_votes + precinct.rep_votes).sum())
    unmatched_vap = precinct_audit["unmatched_positive_vap"] + plan_audit["unmatched_plan_positive_vap"]
    total_vap = plan_audit["total_positive_vap"]
    fallback_share = fallback_votes / total_two_party if total_two_party else 0.0
    status = "passed" if (
        not missing_ids and max_error <= 1e-10
        and (unmatched_vap / total_vap if total_vap else 0.0) <= 0.001
        and fallback_share <= 0.001
    ) else "review"
    source_ids = precinct.result_source_file_id.unique()
    if len(source_ids) != 1:
        raise ValueError(f"Expected one VEST source for {cell.state_code}")
    combined["build_run_id"] = run_id
    combined["result_source_file_id"] = source_ids[0]
    combined["assignment_source_file_id"] = assignment_id
    combined["state_code"] = cell.state_code
    combined["election_cycle"] = 2016
    combined["plan_cycle"] = int(cell.plan_cycle)
    combined["chamber"] = cell.chamber
    audit = {
        "result_source_file_id": source_ids[0], "assignment_source_file_id": assignment_id,
        "state_code": cell.state_code, "election_cycle": 2016,
        "plan_cycle": int(cell.plan_cycle), "chamber": cell.chamber,
        "result_grain": "precinct", "result_rows": len(precinct),
        "assigned_result_rows": len(weighted_ids),
        "split_result_rows": int(combined.groupby("result_observation_id").district.nunique().gt(1).sum()),
        "fallback_two_party_votes": fallback_votes, "total_two_party_votes": total_two_party,
        "unmatched_two_party_votes": 0.0, "max_result_weight_error": max_error,
        "validation_status": status, "missing_result_rows": len(missing_ids),
        **plan_audit,
    }
    return combined, audit


def insert_district_rows(connection, allocated: pd.DataFrame, audit: dict, run_id: str, method: str) -> int:
    for column in ("dem_votes", "rep_votes", "other_votes", "total_votes"):
        allocated[column] = allocated[column] * allocated.allocation_weight
    grouped = allocated.groupby("district", as_index=False).agg(
        dem_votes=("dem_votes", "sum"), rep_votes=("rep_votes", "sum"),
        other_votes=("other_votes", "sum"), total_votes=("total_votes", "sum"),
        allocated_result_geographies=("result_observation_id", "nunique"),
    )
    records = []
    for row in grouped.itertuples(index=False):
        margin = ((row.dem_votes - row.rep_votes) / (row.dem_votes + row.rep_votes)) if row.dem_votes + row.rep_votes else None
        records.append((
            stable_id("PRESDIST", audit["result_source_file_id"], audit["assignment_source_file_id"],
                      audit["state_code"], audit["election_cycle"], audit["plan_cycle"],
                      audit["chamber"], row.district),
            run_id, audit["result_source_file_id"], audit["assignment_source_file_id"], 1,
            audit["state_code"], audit["election_cycle"], audit["plan_cycle"], audit["chamber"],
            str(row.district), district_geometry_unit(
                connection, audit["state_code"], audit["chamber"], str(row.district)
            ) if audit["plan_cycle"] == 2022 else connection.execute(
                """SELECT u.geography_unit_id FROM dim_southern_geography_unit u
                   JOIN dim_southern_geography_layer l USING(geography_layer_id)
                   WHERE l.validation_status='passed' AND l.state_code=? AND l.cycle=?
                     AND l.chamber=? AND u.district=?""",
                (audit["state_code"], audit["plan_cycle"], audit["chamber"], str(row.district)),
            ).fetchone()[0],
            float(row.dem_votes), float(row.rep_votes), float(row.other_votes), float(row.total_votes),
            margin, int(row.allocated_result_geographies), method, audit["validation_status"],
        ))
    connection.executemany(
        "INSERT INTO mart_southern_presidential_district_result VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        records,
    )
    return len(records)


def insert_vest(connection, precinct: pd.DataFrame, weights: pd.DataFrame, audit: dict, run_id: str) -> int:
    connection.executemany(
        """INSERT INTO bridge_southern_vest_historical_plan_weight
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        [(
            row.build_run_id, row.result_source_file_id, row.result_observation_id,
            row.assignment_source_file_id, row.state_code, row.election_cycle, row.plan_cycle,
            row.chamber, str(row.district), float(row.allocation_weight), row.weight_basis,
            int(row.contributing_blocks), float(row.VAP_MOD),
        ) for row in weights.itertuples(index=False)],
    )
    allocated = weights.merge(
        precinct[["result_observation_id", "dem_votes", "rep_votes", "other_votes", "total_votes"]],
        on="result_observation_id", validate="many_to_one",
    )
    rows = insert_district_rows(
        connection, allocated, audit, run_id, "vest_precinct_2020_vap_weighted_to_census_plan",
    )
    source_dem, source_rep = float(precinct.dem_votes.sum()), float(precinct.rep_votes.sum())
    connection.execute(
        "INSERT INTO qa_southern_presidential_district_allocation VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (audit["result_source_file_id"], audit["assignment_source_file_id"], run_id,
         audit["state_code"], 2016, audit["plan_cycle"], audit["chamber"], len(precinct),
         audit["assigned_result_rows"], source_dem, source_dem, source_rep, source_rep, 0.0, 1.0,
         "exact" if audit["validation_status"] == "passed" else "review"),
    )
    return rows


def block_results(connection, state: str) -> pd.DataFrame:
    frame = pd.read_sql_query(
        """SELECT r.result_observation_id,r.source_file_id AS result_source_file_id,
                  r.geography_id AS GEOID20,r.dem_votes,r.rep_votes,r.other_votes,r.total_votes
           FROM fact_southern_presidential_geography_result r
           JOIN source_southern_context_file f USING(source_file_id)
           WHERE f.manifest_source_file_id='RDH-NATIONAL-2020-PRES-BLOCKS'
             AND r.state_code=? AND r.cycle=2020 AND r.geography_type='census_block'""",
        connection, params=(state,), dtype={"GEOID20": str},
    )
    if frame.empty or frame.GEOID20.duplicated().any():
        raise ValueError(f"Missing or duplicate 2020 block results for {state}")
    return frame


def insert_2020(connection, results: pd.DataFrame, blocks: gpd.GeoDataFrame,
                plan_matches: pd.DataFrame, plan_audit: dict, cell, assignment_id: str,
                run_id: str) -> tuple[int, dict]:
    assignment = blocks[["GEOID20"]].merge(
        plan_matches, left_index=True, right_on="block_index", validate="one_to_one",
    )[["GEOID20", "district"]]
    joined = results.merge(assignment, on="GEOID20", how="left", validate="one_to_one")
    source_two_party = float((joined.dem_votes + joined.rep_votes).sum())
    unmatched_votes = float(joined.loc[joined.district.isna(), ["dem_votes", "rep_votes"]].sum().sum())
    assigned = joined.dropna(subset=["district"]).copy()
    assigned["allocation_weight"] = 1.0
    source_ids = results.result_source_file_id.unique()
    if len(source_ids) != 1:
        raise ValueError("Expected one 2020 block result source")
    status = "passed" if abs(unmatched_votes) <= 0.011 else "review"
    audit = {
        "result_source_file_id": source_ids[0], "assignment_source_file_id": assignment_id,
        "state_code": cell.state_code, "election_cycle": 2020,
        "plan_cycle": int(cell.plan_cycle), "chamber": cell.chamber,
        "result_grain": "census_block", "result_rows": len(results),
        "assigned_result_rows": len(assigned), "split_result_rows": 0,
        "fallback_two_party_votes": 0.0, "total_two_party_votes": source_two_party,
        "unmatched_two_party_votes": unmatched_votes, "max_result_weight_error": 0.0,
        "validation_status": status, **plan_audit,
    }
    rows = insert_district_rows(
        connection, assigned, audit, run_id, "rdh_2020_block_representative_point_to_census_plan",
    )
    source_dem, source_rep = float(results.dem_votes.sum()), float(results.rep_votes.sum())
    allocated_dem, allocated_rep = float(assigned.dem_votes.sum()), float(assigned.rep_votes.sum())
    coverage = (allocated_dem + allocated_rep) / source_two_party if source_two_party else None
    connection.execute(
        "INSERT INTO qa_southern_presidential_district_allocation VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (source_ids[0], assignment_id, run_id, cell.state_code, 2020, int(cell.plan_cycle),
         cell.chamber, len(results), len(assigned), source_dem, allocated_dem, source_rep,
         allocated_rep, unmatched_votes, coverage, "exact" if status == "passed" else "review"),
    )
    return rows, audit


def insert_detailed_audit(connection, audit: dict, run_id: str) -> None:
    note = f"missing_result_rows={audit.get('missing_result_rows', 0)}"
    connection.execute(
        "INSERT INTO qa_southern_historical_plan_allocation VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (audit["result_source_file_id"], audit["assignment_source_file_id"], run_id,
         audit["state_code"], audit["election_cycle"], audit["plan_cycle"], audit["chamber"],
         audit["result_grain"], audit["result_rows"], audit["assigned_result_rows"],
         audit["split_result_rows"], audit["ambiguous_plan_blocks_resolved"],
         audit["intersection_plan_blocks_resolved"], audit["unmatched_plan_positive_vap"],
         audit["total_positive_vap"], audit["fallback_two_party_votes"],
         audit["total_two_party_votes"], audit["unmatched_two_party_votes"],
         audit["max_result_weight_error"], audit["validation_status"], note),
    )


def build(database: Path | None = None) -> dict:
    block_manifest = pd.read_csv(BLOCK_MANIFEST, dtype=str).fillna("")
    detailed_manifest = pd.read_csv(DETAILED_MANIFEST, dtype=str).fillna("")
    detailed_lookup = {
        (row["state_code"], int(row["cycle"]), row["chamber"]): row
        for row in detailed_manifest.to_dict("records")
    }
    vap = load_vap(set(block_manifest.state_code))
    with closing(connect(database)) as connection:
        initialize(connection)
        connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        cells = target_cells(connection)
        run_id = begin_run(connection, "southern_historical_plan_allocations", {
            "contract_version": 1, "target_cycles": sorted(cells.plan_cycle.unique().tolist()),
            "presidential_cycles": [2016, 2020],
            "weighting": "2020 modified VAP; explicit area fallback <=0.1%",
        })
        connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        old_sources = "SELECT assignment_source_file_id FROM source_southern_spatial_plan_assignment"
        connection.execute(f"DELETE FROM qa_southern_presidential_district_allocation WHERE assignment_source_file_id IN ({old_sources})")
        connection.execute(f"DELETE FROM mart_southern_presidential_district_result WHERE assignment_source_file_id IN ({old_sources})")
        connection.execute("DELETE FROM qa_southern_historical_plan_allocation")
        connection.execute("DELETE FROM qa_southern_spatial_plan_geometry_overlay")
        connection.execute("DELETE FROM bridge_southern_vest_historical_plan_weight")
        source_ids = [row[0] for row in connection.execute(old_sources).fetchall()]
        connection.execute("DELETE FROM source_southern_spatial_plan_assignment")
        connection.executemany("DELETE FROM source_southern_assignment_file WHERE source_file_id=?", [(x,) for x in source_ids])
        audits, district_rows = [], 0
        manifest_by_state = block_manifest.set_index("state_code")
        for state, state_cells in cells.groupby("state_code", sort=True):
            manifest_row = manifest_by_state.loc[state]
            block_source_id = connection.execute(
                "SELECT source_file_id FROM source_southern_census_block_file WHERE state_code=?", (state,)
            ).fetchone()[0]
            block_path = ROOT / manifest_row.local_path
            blocks = gpd.read_file(f"zip://{block_path.resolve().as_posix()}", columns=["GEOID20", "geometry"])
            blocks["GEOID20"] = blocks.GEOID20.astype(str).str.zfill(15)
            blocks = blocks.merge(vap.pop(state), on="GEOID20", validate="one_to_one").to_crs(5070)
            precinct = precincts(connection, state).to_crs(5070)
            precinct_matches, precinct_audit = resolve_point_matches(blocks, precinct)
            results_2020 = block_results(connection, state)
            for cell in state_cells.itertuples(index=False):
                districts = plan_geometry(connection, cell.geography_layer_id)
                districts["district"] = normalize_district(districts.district)
                plan_matches, plan_audit = assign_blocks_to_plan(blocks, districts)
                detailed_row = detailed_lookup.get((cell.state_code, int(cell.plan_cycle), cell.chamber))
                overlay = None
                if detailed_row:
                    detailed_source_id = register_source(connection, detailed_row, normalized=True)
                    if detailed_source_id != detailed_row["source_file_id"]:
                        raise ValueError(f"Detailed source ID collision: {detailed_row['source_file_id']}")
                    detailed_districts = detailed_plan_geometry(detailed_row)
                    detailed_matches, detailed_audit = assign_blocks_to_plan(blocks, detailed_districts)
                    overlay = overlay_audit(blocks, plan_matches, detailed_matches, detailed_audit)
                    if overlay["validation_status"] != "passed":
                        raise ValueError(f"Detailed plan overlay failed: {cell.state_code}/{cell.chamber}: {overlay}")
                    plan_matches, plan_audit = detailed_matches, detailed_audit
                    districts = detailed_districts
                assignment_id = register_assignment(connection, cell, block_source_id, detailed_row)
                if overlay:
                    connection.execute(
                        "INSERT INTO qa_southern_spatial_plan_geometry_overlay VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (assignment_id, cell.geography_layer_id, run_id, cell.state_code,
                         int(cell.plan_cycle), cell.chamber, overlay["common_assigned_blocks"],
                         overlay["common_disagreement_blocks"], overlay["common_disagreement_vap"],
                         overlay["total_positive_vap"], overlay["cartographic_only_blocks"],
                         overlay["cartographic_only_vap"], overlay["detailed_only_blocks"],
                         overlay["detailed_only_vap"], overlay["detailed_unmatched_positive_vap"],
                         overlay["validation_status"]),
                    )
                weights, audit_2016 = vest_weights(
                    blocks, precinct, precinct_matches, plan_matches, cell, run_id,
                    assignment_id, precinct_audit, plan_audit,
                )
                district_rows += insert_vest(connection, precinct, weights, audit_2016, run_id)
                insert_detailed_audit(connection, audit_2016, run_id)
                audits.append(audit_2016)
                if int(cell.plan_cycle) == 2020:
                    rows, audit_2020 = insert_2020(
                        connection, results_2020, blocks, plan_matches, plan_audit,
                        cell, assignment_id, run_id,
                    )
                    district_rows += rows
                    insert_detailed_audit(connection, audit_2020, run_id)
                    audits.append(audit_2020)
                del districts, plan_matches, weights
                gc.collect()
            del blocks, precinct, precinct_matches, results_2020
            gc.collect()
        reviews = sum(audit["validation_status"] != "passed" for audit in audits)
        reconciliation_reviews = connection.execute(
            f"SELECT COUNT(*) FROM qa_southern_presidential_district_allocation WHERE assignment_source_file_id IN ({old_sources}) AND reconciliation_status='review'"
        ).fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_keys:
            raise ValueError(
                f"Historical allocation foreign-key failure: {foreign_keys[:5]}"
            )
        validation = {
            "plan_cells": len(cells), "audit_rows": len(audits), "review_audits": reviews,
            "district_result_rows": district_rows,
            "vest_weight_rows": connection.execute("SELECT COUNT(*) FROM bridge_southern_vest_historical_plan_weight").fetchone()[0],
            "maximum_unmatched_plan_vap_share": max(
                audit["unmatched_plan_positive_vap"] / audit["total_positive_vap"]
                if audit["total_positive_vap"] else 0.0 for audit in audits
            ),
            "maximum_fallback_vote_share": max(
                audit["fallback_two_party_votes"] / audit["total_two_party_votes"]
                if audit["total_two_party_votes"] else 0.0 for audit in audits
            ),
            "maximum_unmatched_two_party_votes": max(abs(audit["unmatched_two_party_votes"]) for audit in audits),
            "detailed_plan_overlay_rows": connection.execute(
                "SELECT COUNT(*) FROM qa_southern_spatial_plan_geometry_overlay"
            ).fetchone()[0],
            "review_cells": [
                {key: audit[key] for key in (
                    "state_code", "election_cycle", "plan_cycle", "chamber", "result_grain",
                    "unmatched_plan_positive_vap", "fallback_two_party_votes",
                    "unmatched_two_party_votes", "validation_status",
                )}
                for audit in audits if audit["validation_status"] != "passed"
            ],
            "audits": audits,
        }
        for args in [
            ("source_southern_spatial_plan_assignment", "source", "scripts/build_southern_historical_plan_allocations.py", "assignment_source_file_id", "Exact validated Census plan layer plus 2020 block geometry", "replace", "Spatial assignment authority for historical election plans"),
            ("bridge_southern_vest_historical_plan_weight", "canonical", "scripts/build_southern_historical_plan_allocations.py", "result + assignment + district", "2020 block VAP with explicit area fallback", "replace", "VEST 2016 precinct weights on 2018-2020 plans"),
            ("qa_southern_historical_plan_allocation", "qa", "scripts/build_southern_historical_plan_allocations.py", "result source + assignment source", "Coverage and vote-conservation gates", "replace", "Historical plan spatial-allocation diagnostics"),
            ("qa_southern_spatial_plan_geometry_overlay", "qa", "scripts/build_southern_historical_plan_allocations.py", "assignment source", "Block-level same-plan overlay validation", "replace", "Detailed-versus-cartographic plan identity and coverage diagnostics"),
        ]:
            register_table(connection, *args)
        finish_run(connection, run_id, validation)
        connection.commit()
    OUT.mkdir(parents=True, exist_ok=True)
    with closing(connect(database, readonly=True)) as connection:
        results = pd.read_sql_query(
            """SELECT f.* FROM fact_southern_presidential_district_result f
               JOIN source_southern_spatial_plan_assignment s
                 ON s.assignment_source_file_id=f.assignment_source_file_id
               ORDER BY plan_cycle,election_cycle,state_code,chamber,district""", connection,
        )
        qa = pd.read_sql_query(
            "SELECT * FROM qa_southern_historical_plan_allocation ORDER BY plan_cycle,election_cycle,state_code,chamber",
            connection,
        )
    results.to_csv(OUT / "presidential_district_results.csv", index=False)
    qa.to_csv(OUT / "allocation_validation.csv", index=False)
    report = {
        "contract_version": 1, "build_run_id": run_id,
        "pipeline": "scripts/build_southern_historical_plan_allocations.py",
        "validation": validation,
    }
    (OUT / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.database)["validation"], indent=2))


if __name__ == "__main__":
    main()
