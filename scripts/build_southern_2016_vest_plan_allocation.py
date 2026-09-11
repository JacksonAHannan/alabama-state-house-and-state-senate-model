#!/usr/bin/env python3
"""Allocate VEST 2016 precinct votes to 2022 districts with 2020 block VAP."""
from __future__ import annotations

import argparse
import gc
import json
import zipfile
from contextlib import closing
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import from_wkb

from load_southern_context_warehouse import register_source, stable_id
from warehouse import ROOT, begin_run, connect, finish_run, initialize, register_table


SCHEMA = Path(__file__).with_name("warehouse_southern_vest_plan_allocation_schema.sql")
BLOCK_MANIFEST = ROOT / "data/processed/source_audits/southern_2020_census_block_manifest.csv"
RDH_BLOCKS = ROOT / "data/raw/historical_statewide_elections/national_block_2020_pres_results.zip"
OUT = ROOT / "data/processed/presidential/southern_vest_2016_allocations"
PLAN_CYCLE = 2022


def load_vap(states: set[str]) -> dict[str, pd.DataFrame]:
    pieces: dict[str, list[pd.DataFrame]] = {state: [] for state in states}
    with zipfile.ZipFile(RDH_BLOCKS) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(members) != 1:
            raise ValueError(f"Expected one RDH block result CSV, found {members}")
        with archive.open(members[0]) as stream:
            for chunk in pd.read_csv(
                stream, usecols=["GEOID20", "STATEAB", "VAP_MOD"],
                dtype={"GEOID20": str, "STATEAB": str}, chunksize=500_000,
            ):
                chunk = chunk[chunk.STATEAB.isin(states)].copy()
                if chunk.empty:
                    continue
                chunk["GEOID20"] = chunk.GEOID20.str.zfill(15)
                chunk["VAP_MOD"] = pd.to_numeric(chunk.VAP_MOD, errors="raise")
                for state, group in chunk.groupby("STATEAB", sort=False):
                    pieces[state].append(group[["GEOID20", "VAP_MOD"]])
    result = {state: pd.concat(groups, ignore_index=True) for state, groups in pieces.items()}
    if any(frame.GEOID20.duplicated().any() for frame in result.values()):
        raise ValueError("RDH block VAP contains duplicate state/GEOID rows")
    return result


def precincts(connection, state: str) -> gpd.GeoDataFrame:
    frame = pd.read_sql_query(
        """SELECT r.result_observation_id,r.source_file_id AS result_source_file_id,
                  r.geography_id,r.dem_votes,r.rep_votes,r.other_votes,r.total_votes,
                  u.geometry_wkb
           FROM source_southern_presidential_geography_result r
           JOIN bridge_southern_result_geography b USING(result_observation_id)
           JOIN dim_southern_geography_unit u USING(geography_unit_id)
           JOIN dim_southern_geography_layer l USING(geography_layer_id)
           WHERE r.source_file_id IN (SELECT source_file_id FROM source_southern_vest_context_file)
             AND r.state_code=? AND r.cycle=2016 AND r.geography_type='precinct'
             AND b.review_status='accepted' AND b.allocation_weight=1.0
             AND l.geography_type='precinct'""",
        connection, params=(state,),
    )
    if frame.empty or frame.result_observation_id.duplicated().any():
        raise ValueError(f"Missing or duplicate VEST precinct geometry for {state}")
    return gpd.GeoDataFrame(
        frame.drop(columns="geometry_wkb"), geometry=from_wkb(frame.geometry_wkb.values), crs=4326
    )


def assignments(connection, state: str) -> tuple[pd.DataFrame, str]:
    frame = pd.read_sql_query(
        """SELECT a.source_file_id,a.block_geoid AS GEOID20,
                  a.lower_district,a.upper_district
           FROM bridge_southern_block_district_assignment a
           JOIN source_southern_assignment_file f USING(source_file_id)
           WHERE f.manifest_source_file_id='RDH-NATIONAL-2022-SLD-BAF'
             AND a.state_code=?""",
        connection, params=(state,), dtype={"GEOID20": str},
    )
    sources = frame.source_file_id.unique()
    if len(sources) != 1 or frame.GEOID20.duplicated().any():
        raise ValueError(f"Invalid 2022 block assignment slice for {state}")
    return frame.drop(columns="source_file_id"), sources[0]


def resolve_point_matches(blocks: gpd.GeoDataFrame, precinct: gpd.GeoDataFrame) -> tuple[pd.DataFrame, dict]:
    points = gpd.GeoDataFrame(
        blocks[["GEOID20", "VAP_MOD"]], geometry=blocks.geometry.representative_point(),
        crs=blocks.crs,
    )
    joined = gpd.sjoin(
        points, precinct[["result_observation_id", "geometry"]], how="left", predicate="within"
    ).reset_index(names="block_index")
    ambiguous_indexes = set(joined.loc[joined.block_index.duplicated(keep=False), "block_index"])
    chosen = joined[~joined.block_index.isin(ambiguous_indexes)].dropna(
        subset=["result_observation_id"]
    )[["block_index", "result_observation_id"]]
    resolved_rows = []
    for block_index, candidates in joined[joined.block_index.isin(ambiguous_indexes)].groupby("block_index"):
        ranked = []
        for candidate in candidates.itertuples(index=False):
            area = blocks.loc[block_index].geometry.intersection(
                precinct.loc[int(candidate.index_right)].geometry
            ).area
            ranked.append((float(area), str(candidate.result_observation_id)))
        resolved_rows.append((block_index, max(ranked, key=lambda value: (value[0], value[1]))[1]))
    if resolved_rows:
        chosen = pd.concat(
            [chosen, pd.DataFrame(resolved_rows, columns=["block_index", "result_observation_id"])],
            ignore_index=True,
        )
    matched_indexes = set(chosen.block_index)
    unmatched_positive = blocks.index[(blocks.VAP_MOD.gt(0)) & (~blocks.index.isin(matched_indexes))]
    intersection_resolved = 0
    if len(unmatched_positive):
        candidates = gpd.sjoin(
            blocks.loc[unmatched_positive, ["geometry"]],
            precinct[["result_observation_id", "geometry"]],
            how="inner", predicate="intersects",
        ).reset_index(names="block_index")
        fallback_rows = []
        for block_index, group in candidates.groupby("block_index"):
            ranked = []
            for candidate in group.itertuples(index=False):
                area = blocks.loc[block_index].geometry.intersection(
                    precinct.loc[int(candidate.index_right)].geometry
                ).area
                if area > 0:
                    ranked.append((float(area), str(candidate.result_observation_id)))
            if ranked:
                fallback_rows.append((block_index, max(ranked, key=lambda value: (value[0], value[1]))[1]))
        if fallback_rows:
            intersection_resolved = len(fallback_rows)
            chosen = pd.concat(
                [chosen, pd.DataFrame(fallback_rows, columns=["block_index", "result_observation_id"])],
                ignore_index=True,
            )
    chosen = chosen.drop_duplicates("block_index", keep="last")
    unmatched = blocks.loc[
        blocks.VAP_MOD.gt(0) & ~blocks.index.isin(chosen.block_index), ["GEOID20", "VAP_MOD"]
    ]
    return chosen, {
        "ambiguous_blocks_resolved": len(ambiguous_indexes),
        "intersection_blocks_resolved": intersection_resolved,
        "unmatched_positive_blocks": len(unmatched),
        "unmatched_positive_vap": float(unmatched.VAP_MOD.sum()),
        "total_positive_vap": float(blocks.VAP_MOD.sum()),
    }


def geometry_fallback(
    blocks: gpd.GeoDataFrame, precinct: gpd.GeoDataFrame, result_ids: set[str], chamber_field: str,
) -> pd.DataFrame:
    if not result_ids:
        return pd.DataFrame(columns=["result_observation_id", "district", "basis", "contributing_blocks"])
    target = precinct[precinct.result_observation_id.isin(result_ids)]
    candidates = gpd.sjoin(
        blocks[[chamber_field, "geometry"]],
        target[["result_observation_id", "geometry"]], how="inner", predicate="intersects",
    ).reset_index(names="block_index")
    rows = []
    for candidate in candidates.itertuples(index=False):
        district = getattr(candidate, chamber_field)
        if district is None or (isinstance(district, float) and pd.isna(district)):
            continue
        area = blocks.loc[candidate.block_index].geometry.intersection(
            target.loc[int(candidate.index_right)].geometry
        ).area
        if area > 0:
            rows.append((candidate.result_observation_id, str(district), candidate.block_index, float(area)))
    detail = pd.DataFrame(rows, columns=["result_observation_id", "district", "block_index", "area"])
    if detail.empty:
        return pd.DataFrame(columns=[
            "result_observation_id", "district", "basis", "contributing_blocks", "VAP_MOD"
        ])
    result = detail.groupby(["result_observation_id", "district"], as_index=False).agg(
        basis=("area", "sum"), contributing_blocks=("block_index", "nunique")
    )
    result["VAP_MOD"] = 0.0
    return result


def district_geometry_unit(connection, state: str, chamber: str, district: str) -> str | None:
    rows = connection.execute(
        """SELECT u.geography_unit_id FROM dim_southern_geography_unit u
           JOIN dim_southern_geography_layer l USING(geography_layer_id)
           WHERE l.validation_status='passed' AND u.state_code=? AND u.cycle=?
             AND u.chamber=? AND u.district=?""",
        (state, PLAN_CYCLE, chamber, district),
    ).fetchall()
    if len(rows) > 1:
        raise ValueError(f"Duplicate district geometry for {(state, chamber, district)}")
    return rows[0][0] if rows else None


def state_weights(
    blocks: gpd.GeoDataFrame, precinct: gpd.GeoDataFrame, matches: pd.DataFrame,
    chamber: str, assignment_source_file_id: str, block_source_file_id: str, run_id: str,
    match_audit: dict,
) -> tuple[pd.DataFrame, dict]:
    chamber_field = f"{chamber}_district"
    matched = matches.merge(
        blocks[["GEOID20", "VAP_MOD", chamber_field]], left_on="block_index", right_index=True,
        validate="one_to_one",
    )
    matched = matched[matched[chamber_field].notna()].copy()
    matched["district"] = matched[chamber_field].astype(str)
    primary = matched[matched.VAP_MOD.gt(0)].groupby(
        ["result_observation_id", "district"], as_index=False
    ).agg(basis=("VAP_MOD", "sum"), contributing_blocks=("GEOID20", "nunique"), VAP_MOD=("VAP_MOD", "sum"))
    primary_ids = set(primary.result_observation_id)
    positive_precincts = set(precinct.loc[precinct.total_votes.gt(0), "result_observation_id"])
    fallback_ids = positive_precincts - primary_ids
    fallback = geometry_fallback(blocks, precinct, fallback_ids, chamber_field)
    fallback["weight_basis"] = "geometry_intersection_area"
    primary["weight_basis"] = "2020_vap"
    combined = pd.concat([primary, fallback], ignore_index=True)
    if combined.empty:
        raise ValueError(f"No precinct weights for {precinct.iloc[0].result_source_file_id}/{chamber}")
    combined["allocation_weight"] = combined.basis / combined.groupby(
        "result_observation_id"
    ).basis.transform("sum")
    weighted_positive = positive_precincts.intersection(set(combined.result_observation_id))
    missing_positive = positive_precincts - weighted_positive
    sums = combined.groupby("result_observation_id").allocation_weight.sum()
    max_error = float((sums - 1.0).abs().max())
    district_counts = combined.groupby("result_observation_id").district.nunique()
    split_ids = set(district_counts[district_counts.gt(1)].index)
    result_source = precinct.result_source_file_id.unique()
    if len(result_source) != 1:
        raise ValueError("Expected one VEST result source per state")
    state = str(precinct.iloc[0].geography_id).split("|", 1)[0]
    result_source_file_id = result_source[0]
    combined["build_run_id"] = run_id
    combined["block_geometry_source_file_id"] = block_source_file_id
    combined["result_source_file_id"] = result_source_file_id
    combined["assignment_source_file_id"] = assignment_source_file_id
    combined["state_code"] = state
    combined["election_cycle"] = 2016
    combined["plan_cycle"] = PLAN_CYCLE
    combined["chamber"] = chamber
    fallback_votes = precinct.loc[
        precinct.result_observation_id.isin(fallback_ids), ["dem_votes", "rep_votes"]
    ].sum().sum()
    total_two_party = float((precinct.dem_votes + precinct.rep_votes).sum())
    unmatched_share = (
        match_audit["unmatched_positive_vap"] / match_audit["total_positive_vap"]
        if match_audit["total_positive_vap"] else 0.0
    )
    status = "passed" if (
        not missing_positive and max_error <= 1e-10 and unmatched_share <= 0.001
        and (float(fallback_votes) / total_two_party if total_two_party else 0.0) <= 0.001
    ) else "review"
    audit = {
        "result_source_file_id": result_source_file_id,
        "assignment_source_file_id": assignment_source_file_id,
        "block_geometry_source_file_id": block_source_file_id,
        "state_code": state, "chamber": chamber, "source_precincts": len(precinct),
        "positive_vote_precincts": len(positive_precincts),
        "weighted_positive_vote_precincts": len(weighted_positive),
        "vap_weighted_precincts": len(primary_ids),
        "geometry_fallback_precincts": len(fallback_ids.intersection(set(fallback.result_observation_id))),
        "split_precincts": len(split_ids),
        "fallback_two_party_votes": float(fallback_votes),
        "total_two_party_votes": total_two_party,
        "max_precinct_weight_error": max_error,
        "validation_status": status,
        "missing_positive_vote_precincts": len(missing_positive),
        **match_audit,
    }
    return combined, audit


def insert_allocation(connection, precinct: pd.DataFrame, weights: pd.DataFrame, audit: dict,
                      run_id: str) -> int:
    state, chamber = audit["state_code"], audit["chamber"]
    connection.executemany(
        """INSERT INTO bridge_southern_vest_precinct_district_weight
           (build_run_id,block_geometry_source_file_id,result_source_file_id,result_observation_id,
            assignment_source_file_id,state_code,election_cycle,plan_cycle,chamber,district,
            allocation_weight,weight_basis,contributing_blocks,contributing_vap)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        [
            (
                row.build_run_id, row.block_geometry_source_file_id, row.result_source_file_id,
                row.result_observation_id, row.assignment_source_file_id, row.state_code,
                row.election_cycle, row.plan_cycle, row.chamber, row.district,
                float(row.allocation_weight), row.weight_basis, int(row.contributing_blocks),
                float(row.VAP_MOD),
            )
            for row in weights.itertuples(index=False)
        ],
    )
    allocated = weights.merge(
        precinct[["result_observation_id", "dem_votes", "rep_votes", "other_votes", "total_votes"]],
        on="result_observation_id", validate="many_to_one",
    )
    for column in ("dem_votes", "rep_votes", "other_votes", "total_votes"):
        allocated[column] *= allocated.allocation_weight
    grouped = allocated.groupby("district", as_index=False).agg(
        dem_votes=("dem_votes", "sum"), rep_votes=("rep_votes", "sum"),
        other_votes=("other_votes", "sum"), total_votes=("total_votes", "sum"),
        allocated_result_geographies=("result_observation_id", "nunique"),
    )
    records = []
    for item in grouped.itertuples(index=False):
        margin = (
            (item.dem_votes - item.rep_votes) / (item.dem_votes + item.rep_votes)
            if item.dem_votes + item.rep_votes else None
        )
        records.append((
            stable_id(
                "PRESDIST", audit["result_source_file_id"], audit["assignment_source_file_id"],
                state, 2016, PLAN_CYCLE, chamber, item.district,
            ),
            run_id, audit["result_source_file_id"], audit["assignment_source_file_id"], 1,
            state, 2016, PLAN_CYCLE, chamber, item.district,
            district_geometry_unit(connection, state, chamber, item.district),
            float(item.dem_votes), float(item.rep_votes), float(item.other_votes),
            float(item.total_votes), margin, int(item.allocated_result_geographies),
            "vest_precinct_2020_vap_weighted_to_rdh_baf", audit["validation_status"],
        ))
    connection.executemany(
        "INSERT INTO mart_southern_presidential_district_result VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        records,
    )
    source_dem = float(precinct.dem_votes.sum())
    source_rep = float(precinct.rep_votes.sum())
    allocated_dem = float(grouped.dem_votes.sum())
    allocated_rep = float(grouped.rep_votes.sum())
    source_two_party = source_dem + source_rep
    unmatched_votes = source_two_party - allocated_dem - allocated_rep
    coverage = (allocated_dem + allocated_rep) / source_two_party if source_two_party else None
    reconciliation = "exact" if abs(unmatched_votes) <= 0.011 else "review"
    connection.execute(
        "INSERT INTO qa_southern_presidential_district_allocation VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            audit["result_source_file_id"], audit["assignment_source_file_id"], run_id,
            state, 2016, PLAN_CYCLE, chamber, len(precinct),
            audit["weighted_positive_vote_precincts"], source_dem, allocated_dem,
            source_rep, allocated_rep, unmatched_votes, coverage, reconciliation,
        ),
    )
    if reconciliation == "review":
        connection.execute(
            """UPDATE mart_southern_presidential_district_result SET allocation_status='review'
               WHERE result_source_file_id=? AND assignment_source_file_id=? AND chamber=?""",
            (audit["result_source_file_id"], audit["assignment_source_file_id"], chamber),
        )
    note = (
        f"intersection_resolved={audit['intersection_blocks_resolved']};"
        f"unmatched_positive_blocks={audit['unmatched_positive_blocks']};"
        f"missing_positive_vote_precincts={audit['missing_positive_vote_precincts']}"
    )
    connection.execute(
        "INSERT INTO qa_southern_vest_precinct_plan_allocation VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            audit["result_source_file_id"], audit["assignment_source_file_id"],
            audit["block_geometry_source_file_id"], run_id, state, 2016, PLAN_CYCLE, chamber,
            audit["source_precincts"], audit["positive_vote_precincts"],
            audit["weighted_positive_vote_precincts"], audit["vap_weighted_precincts"],
            audit["geometry_fallback_precincts"], audit["split_precincts"],
            audit["ambiguous_blocks_resolved"], audit["unmatched_positive_vap"],
            audit["total_positive_vap"], audit["fallback_two_party_votes"],
            audit["total_two_party_votes"], audit["max_precinct_weight_error"],
            audit["validation_status"], note,
        ),
    )
    return len(records)


def build(database: Path | None = None) -> dict:
    manifest = pd.read_csv(BLOCK_MANIFEST, dtype=str).fillna("")
    if len(manifest) != 14 or manifest.state_code.duplicated().any():
        raise ValueError("Census block manifest must contain all 14 states")
    vap = load_vap(set(manifest.state_code))
    with closing(connect(database)) as connection:
        initialize(connection)
        connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        run_id = begin_run(connection, "southern_2016_vest_plan_allocation", {
            "contract_version": 1, "election_cycle": 2016, "plan_cycle": PLAN_CYCLE,
            "weighting": "2020 RDH modified VAP by Census block; geometry area only for <=0.1% fallback votes",
            "block_manifest": BLOCK_MANIFEST.relative_to(ROOT).as_posix(),
        })
        connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        vest_sources = "SELECT source_file_id FROM source_southern_vest_context_file"
        connection.execute(
            f"DELETE FROM qa_southern_presidential_district_allocation WHERE result_source_file_id IN ({vest_sources})"
        )
        connection.execute(
            f"DELETE FROM mart_southern_presidential_district_result WHERE result_source_file_id IN ({vest_sources})"
        )
        connection.execute("DELETE FROM qa_southern_vest_precinct_plan_allocation")
        connection.execute("DELETE FROM bridge_southern_vest_precinct_district_weight")
        connection.execute("DELETE FROM source_southern_census_block_file")
        audits = []
        district_rows = 0
        for manifest_row in manifest.to_dict("records"):
            state = manifest_row["state_code"]
            manifest_id = manifest_row["source_file_id"]
            block_source_id = register_source(connection, manifest_row, normalized=True)
            connection.execute(
                "INSERT INTO source_southern_census_block_file VALUES (?,?,?,?,?,?,?,?)",
                (
                    block_source_id, manifest_id, state, int(manifest_row["cycle"]),
                    manifest_row["geography_vintage"], manifest_row["authoritative_scope"],
                    "build_southern_2016_vest_plan_allocation", "used_for_crosswalk",
                ),
            )
            block_path = ROOT / manifest_row["local_path"]
            blocks = gpd.read_file(
                f"zip://{block_path.resolve().as_posix()}",
                columns=["GEOID20", "ALAND20", "AWATER20", "geometry"],
            )
            blocks["GEOID20"] = blocks.GEOID20.astype(str).str.zfill(15)
            blocks = blocks.merge(vap.pop(state), on="GEOID20", how="left", validate="one_to_one")
            if blocks.VAP_MOD.isna().any():
                raise ValueError(f"RDH VAP missing for Census blocks in {state}")
            assignment, assignment_source_id = assignments(connection, state)
            blocks = blocks.merge(assignment, on="GEOID20", how="left", validate="one_to_one")
            missing_assignment = blocks[["lower_district", "upper_district"]].isna().all(axis=1)
            if (missing_assignment & blocks.VAP_MOD.gt(0)).any():
                raise ValueError(
                    f"2022 plan assignment missing for positive-VAP Census blocks in {state}"
                )
            # BAF files can omit water-only or otherwise unassigned zero-VAP blocks. They cannot
            # affect the population-weighted crosswalk and are excluded explicitly, not imputed.
            blocks = blocks.loc[~missing_assignment].copy()
            blocks = blocks.to_crs(5070)
            precinct = precincts(connection, state).to_crs(5070)
            matches, match_audit = resolve_point_matches(blocks, precinct)
            for chamber in ("lower", "upper"):
                weights, audit = state_weights(
                    blocks, precinct, matches, chamber, assignment_source_id,
                    block_source_id, run_id, match_audit,
                )
                district_rows += insert_allocation(connection, precinct, weights, audit, run_id)
                audits.append(audit)
            del blocks, precinct, matches
            gc.collect()
        review_audits = sum(item["validation_status"] == "review" for item in audits)
        bad_reconciliations = connection.execute(
            f"""SELECT COUNT(*) FROM qa_southern_presidential_district_allocation
                 WHERE result_source_file_id IN ({vest_sources}) AND reconciliation_status='review'"""
        ).fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        if review_audits or bad_reconciliations or foreign_keys:
            raise ValueError(
                f"VEST plan allocation failed: review={review_audits}, "
                f"reconciliation={bad_reconciliations}, foreign_keys={foreign_keys[:5]}"
            )
        validation = {
            "states": 14, "plan_cycle": PLAN_CYCLE,
            "precinct_district_weight_rows": connection.execute(
                "SELECT COUNT(*) FROM bridge_southern_vest_precinct_district_weight"
            ).fetchone()[0],
            "district_result_rows": district_rows, "state_chamber_audits": len(audits),
            "review_audits": review_audits,
            "total_fallback_two_party_votes": sum(item["fallback_two_party_votes"] for item in audits) / 2,
            "maximum_fallback_vote_share": max(
                item["fallback_two_party_votes"] / item["total_two_party_votes"]
                if item["total_two_party_votes"] else 0.0 for item in audits
            ),
            "maximum_unmatched_vap_share": max(
                item["unmatched_positive_vap"] / item["total_positive_vap"]
                if item["total_positive_vap"] else 0.0 for item in audits
            ),
            "maximum_precinct_weight_error": max(item["max_precinct_weight_error"] for item in audits),
            "audits": audits,
        }
        for name, layer, key_value, authority, lifecycle, description in [
            ("source_southern_census_block_file", "source", "source_file_id",
             "Manifest-backed Census 2020 TIGER/Line archives", "replace",
             "Block geometry sources used without duplicating polygon bytes in SQLite"),
            ("bridge_southern_vest_precinct_district_weight", "canonical",
             "result_observation_id + assignment_source_file_id + chamber + district",
             "2020 block VAP; explicit geometry-area fallback under 0.1% of votes", "replace",
             "VEST precinct allocation weights onto the enacted 2022 plan"),
            ("qa_southern_vest_precinct_plan_allocation", "qa",
             "result source + assignment source + chamber",
             "Coverage, split, fallback, and weight-sum validation", "replace",
             "State/chamber VEST crosswalk diagnostics"),
        ]:
            register_table(connection, name, layer, "scripts/build_southern_2016_vest_plan_allocation.py",
                           key_value, authority, lifecycle, description)
        finish_run(connection, run_id, validation)
        connection.commit()
    OUT.mkdir(parents=True, exist_ok=True)
    with closing(connect(database, readonly=True)) as connection:
        district = pd.read_sql_query(
            """SELECT * FROM fact_southern_presidential_district_result
               WHERE election_cycle=2016 AND plan_cycle=2022
               ORDER BY state_code,chamber,district""", connection,
        )
        qa = pd.read_sql_query(
            "SELECT * FROM qa_southern_vest_precinct_plan_allocation ORDER BY state_code,chamber",
            connection,
        )
    district.to_csv(OUT / "presidential_district_results.csv", index=False)
    qa.to_csv(OUT / "crosswalk_validation.csv", index=False)
    report = {
        "contract_version": 1, "build_run_id": run_id,
        "pipeline": "scripts/build_southern_2016_vest_plan_allocation.py",
        "validation": validation,
        "outputs": [
            "data/processed/presidential/southern_vest_2016_allocations/presidential_district_results.csv",
            "data/processed/presidential/southern_vest_2016_allocations/crosswalk_validation.csv",
        ],
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
