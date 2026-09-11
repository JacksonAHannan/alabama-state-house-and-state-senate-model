#!/usr/bin/env python3
"""Load VEST 2016 presidential precinct results and geometry into SQLite."""
from __future__ import annotations

import argparse
import hashlib
import json
from contextlib import closing
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely import make_valid, union_all

from load_southern_context_warehouse import RESULT_COLUMNS, register_source, stable_id, text
from warehouse import ROOT, begin_run, connect, finish_run, initialize, register_table


SCHEMA = Path(__file__).with_name("warehouse_southern_vest_context_schema.sql")
MANIFEST = ROOT / "data/processed/source_audits/southern_2016_vest_manifest.csv"
OUT = ROOT / "data/processed/source_audits/southern_2016_vest_warehouse_validation.json"
DEM_FIELD = "G16PREDCLI"
REP_FIELD = "G16PRERTRU"
FIELDS = {
    "AL": ("COUNTYFP20", None, "GEOID16", "NAME16"),
    "AR": ("COUNTY_FIP", "COUNTY_NAM", "PRECINCT", "PRECINCT"),
    "FL": (None, "COUNTY", "PCT_STD", "PRECINCT"),
    "GA": ("FIPS2", "COUNTY", "PRECINCT_I", "PRECINCT_N"),
    "KY": ("COUNTYFP16", None, "GEOID16", "NAME16"),
    "LA": ("COUNTYFP10", None, "VTDST10", "NAME10"),
    "MO": ("COUNTYFP", None, "NAME", "NAME"),
    "MS": ("COUNTYFP16", None, "GEOID16", "NAME16"),
    "NC": ("COUNTY_ID", "COUNTY_NAM", "PREC_ID", "PREC_ID"),
    "OK": ("COUNTY", None, "PCT_CEB", "PRECINCT"),
    "SC": ("COUNTY", "COUNTYNAME", "PCODE", "NAME"),
    "TN": ("COUNTYFP", None, "VTD", "NAME"),
    "TX": ("CNTY", None, "PCTKEY", "PREC"),
    "VA": ("COUNTYFP", "LOCALITY", "VTDST", "PRECINCT"),
}


def scalar(value: object) -> str | None:
    result = text(value)
    return result or None


def county_fips(value: object) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    token = text(value)
    try:
        token = str(int(float(token)))
    except ValueError:
        return None
    return token.zfill(3)


def storage_geometry(shape):
    """Keep valid polygonal area after reprojection; discard collapsed debris."""
    if shape is None or shape.is_empty:
        raise ValueError("Null or empty storage geometry")
    if not shape.is_valid:
        shape = make_valid(shape)
        if shape.geom_type == "GeometryCollection":
            shape = union_all([part for part in shape.geoms
                               if part.geom_type in {"Polygon", "MultiPolygon"}])
    if not shape.is_valid or shape.is_empty or shape.geom_type not in {"Polygon", "MultiPolygon"}:
        raise ValueError("Storage geometry must be a valid nonempty polygon")
    return shape


def load_state(connection, row: dict, run_id: str) -> dict:
    state = row["state_code"]
    path = ROOT / row["local_path"]
    frame = gpd.read_file(f"zip://{path.resolve().as_posix()}")
    if frame.crs is None:
        raise ValueError(f"VEST source has no CRS: {path}")
    county_field, county_name_field, precinct_field, precinct_name_field = FIELDS[state]
    required = {DEM_FIELD, REP_FIELD, precinct_field, precinct_name_field}
    required.update(value for value in (county_field, county_name_field) if value)
    if not required.issubset(frame.columns):
        raise ValueError(f"{state} VEST fields missing: {required - set(frame.columns)}")
    presidential_fields = sorted(
        column for column in frame.columns if str(column).upper().startswith("G16PRE")
    )
    other_fields = [column for column in presidential_fields if column not in {DEM_FIELD, REP_FIELD}]
    for column in presidential_fields:
        frame[column] = pd.to_numeric(frame[column], errors="raise").fillna(0.0)
        if (frame[column] < 0).any():
            raise ValueError(f"Negative VEST presidential vote in {state}/{column}")
    repaired = int((~frame.geometry.is_valid).sum())
    if frame.geometry.isna().any() or frame.geometry.is_empty.any():
        raise ValueError(f"Null or empty VEST geometry in {state}")
    if repaired:
        frame.geometry = frame.geometry.make_valid()
    frame["_county_fips"] = (
        frame[county_field].map(county_fips) if county_field else None
    )
    frame["_county_name"] = (
        frame[county_name_field].map(scalar) if county_name_field else None
    )
    raw_precinct = frame[precinct_field].map(text)
    precinct_names = frame[precinct_name_field].map(text)
    # Georgia's military precinct rows have a provider name but a blank ID.
    # The name is unique within county and is retained as the explicit fallback.
    raw_precinct = raw_precinct.mask(raw_precinct.eq(""), precinct_names)
    if raw_precinct.eq("").any():
        raise ValueError(f"Blank VEST precinct identifier and name in {state}")
    if state in {"GA", "TN", "VA"}:
        # Several provider IDs in Georgia and Tennessee, and Virginia precincts
        # split by congressional district, represent distinct named result rows
        # within the same county.
        raw_precinct = raw_precinct + "|" + precinct_names
    frame["_geography_id"] = [
        f"{state}|{cf or cn or 'UNKNOWN_COUNTY'}|{precinct}"
        for cf, cn, precinct in zip(
            frame["_county_fips"], frame["_county_name"], raw_precinct
        )
    ]
    frame["_precinct_name"] = precinct_names
    # Repeated identifiers are zero-vote geometry fragments in the source.
    # Require their vote records to agree before dissolving the fragments.
    for _, group in frame.groupby("_geography_id", sort=False):
        if len(group) > 1 and any(group[column].nunique(dropna=False) != 1 for column in presidential_fields):
            raise ValueError(f"Conflicting repeated VEST precinct vote rows in {state}")
    attributes = frame.drop(columns="geometry").drop_duplicates("_geography_id", keep="first")
    geometry = frame[["_geography_id", "geometry"]].dissolve(by="_geography_id", as_index=False)
    normalized = geometry.merge(attributes, on="_geography_id", how="left", validate="one_to_one")
    if (~normalized.geometry.is_valid).any() or normalized.geometry.is_empty.any():
        raise ValueError(f"Dissolved VEST geometry is invalid in {state}")

    source_crs = frame.crs.to_string()
    area = normalized.to_crs(5070).geometry.area / 1_000_000
    normalized = normalized.to_crs(4326)
    repaired_storage = int((~normalized.geometry.is_valid).sum())
    normalized.geometry = normalized.geometry.map(storage_geometry)
    layer_id = stable_id("GEOLAYER", row["source_file_id"], state, 2016, "precinct")
    connection.execute(
        "INSERT INTO dim_southern_geography_layer VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            layer_id, run_id, row["source_file_id"], 1, state, 2016, "precinct", None,
            row["geography_vintage"], source_crs, "EPSG:4326", len(normalized), "passed",
        ),
    )
    result_records = []
    geometry_records = []
    links = []
    dem_total = rep_total = other_total = 0.0
    for position, (_, item) in enumerate(normalized.iterrows()):
        values = item
        geography_id = values["_geography_id"]
        dem = float(values[DEM_FIELD])
        rep = float(values[REP_FIELD])
        others = {field: float(values[field]) for field in other_fields}
        other = sum(others.values())
        total = dem + rep + other
        dem_total += dem
        rep_total += rep
        other_total += other
        result_id = stable_id("PRESGEO", row["source_file_id"], state, 2016, geography_id)
        geometry_id = stable_id("GEOUNIT", layer_id, geography_id)
        result_values = {
            "result_observation_id": result_id, "build_run_id": run_id,
            "source_file_id": row["source_file_id"], "contract_version": 1,
            "state_code": state, "cycle": 2016, "election_date": "2016-11-08",
            "election_stage": "general", "office_code": "USP", "geography_type": "precinct",
            "geography_id": geography_id, "county_fips": values["_county_fips"],
            "county_name_original": values["_county_name"],
            "county_key": (values["_county_name"] or values["_county_fips"] or "").upper(),
            "precinct_name_original": values["_precinct_name"],
            "precinct_key": values["_precinct_name"].upper(),
            "dem_candidate": "Hillary Clinton", "rep_candidate": "Donald Trump",
            "other_candidates_json": json.dumps(others, sort_keys=True),
            "dem_votes": dem, "rep_votes": rep, "other_votes": other, "total_votes": total,
            "two_party_dem_margin": (dem - rep) / (dem + rep) if dem + rep else None,
            "vote_value_status": "observed", "allocation_method": "vest_harmonized_precinct",
            "validation_status": "passed",
        }
        result_records.append(tuple(result_values[column] for column in RESULT_COLUMNS))
        shape = values["geometry"]
        shape_wkb = bytes(shape.wkb)
        bounds = shape.bounds
        geometry_records.append((
            geometry_id, layer_id, state, 2016, "precinct", None, None, geography_id,
            values["_precinct_name"], values["_county_fips"], values["_county_name"],
            shape_wkb, "EPSG:4326", hashlib.sha256(shape_wkb).hexdigest(),
            *map(float, bounds), float(area.iloc[position]),
        ))
        links.append((result_id, geometry_id, "same_archive_precinct_identifier", 1.0, "accepted"))
    connection.executemany(
        f"INSERT INTO source_southern_presidential_geography_result ({','.join(RESULT_COLUMNS)}) "
        f"VALUES ({','.join('?' for _ in RESULT_COLUMNS)})",
        result_records,
    )
    connection.executemany(
        "INSERT INTO dim_southern_geography_unit VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        geometry_records,
    )
    connection.executemany(
        "INSERT INTO bridge_southern_result_geography VALUES (?,?,?,?,?)", links
    )
    return {
        "state_code": state, "input_features": len(frame),
        "normalized_precincts": len(normalized), "repaired_input_geometries": repaired,
        "dem_votes": dem_total, "rep_votes": rep_total, "other_votes": other_total,
        "result_geometry_links": len(links), "reconciliation_status": "exact",
        "note": ("Repeated zero-vote geometry fragments dissolved; vote fields required to agree; "
                 f"post-reprojection geometry repairs={repaired_storage}"),
    }


def build(database: Path | None = None) -> dict:
    manifest = pd.read_csv(MANIFEST, dtype=str).fillna("")
    if len(manifest) != 14 or manifest.state_code.duplicated().any():
        raise ValueError("VEST manifest must contain one unique archive for each Southern state")
    with closing(connect(database)) as connection:
        initialize(connection)
        connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        run_id = begin_run(connection, "southern_2016_vest_context", {
            "contract_version": 1,
            "manifest": MANIFEST.relative_to(ROOT).as_posix(),
            "election_cycle": 2016,
        })
        connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """DELETE FROM bridge_southern_result_geography
               WHERE result_observation_id IN (
                 SELECT result_observation_id FROM source_southern_presidential_geography_result
                 WHERE source_file_id IN (SELECT source_file_id FROM source_southern_vest_context_file)
               ) OR geography_unit_id IN (
                 SELECT u.geography_unit_id FROM dim_southern_geography_unit u
                 JOIN dim_southern_geography_layer l USING(geography_layer_id)
                 WHERE l.source_file_id IN (SELECT source_file_id FROM source_southern_vest_context_file)
               )"""
        )
        connection.execute(
            """DELETE FROM source_southern_presidential_geography_result
               WHERE source_file_id IN (SELECT source_file_id FROM source_southern_vest_context_file)"""
        )
        connection.execute(
            """DELETE FROM dim_southern_geography_layer
               WHERE source_file_id IN (SELECT source_file_id FROM source_southern_vest_context_file)"""
        )
        connection.execute("DELETE FROM qa_southern_vest_context_ingest")
        connection.execute("DELETE FROM source_southern_vest_context_file")
        audits = []
        for manifest_row in manifest.to_dict("records"):
            manifest_id = manifest_row["source_file_id"]
            warehouse_id = register_source(connection, manifest_row, normalized=True)
            row = {**manifest_row, "source_file_id": warehouse_id}
            connection.execute(
                "INSERT INTO source_southern_vest_context_file VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    warehouse_id, manifest_id, row["dataset_doi"], row["dataset_version"],
                    int(row["dataverse_file_id"]), row["state_code"], int(row["election_cycle"]),
                    row["geography_vintage"], row["authoritative_scope"],
                    "load_southern_2016_vest_warehouse", "normalized",
                ),
            )
            audit = load_state(connection, row, run_id)
            audits.append(audit)
            connection.execute(
                "INSERT INTO qa_southern_vest_context_ingest VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    warehouse_id, run_id, audit["state_code"], audit["input_features"],
                    audit["normalized_precincts"], audit["repaired_input_geometries"],
                    audit["dem_votes"], audit["rep_votes"], audit["other_votes"],
                    audit["result_geometry_links"], audit["reconciliation_status"], audit["note"],
                ),
            )
        duplicate_results = connection.execute(
            """SELECT COUNT(*) FROM (
                 SELECT source_file_id,state_code,cycle,geography_type,geography_id,COUNT(*) n
                 FROM source_southern_presidential_geography_result
                 WHERE source_file_id IN (SELECT source_file_id FROM source_southern_vest_context_file)
                 GROUP BY 1,2,3,4,5 HAVING n>1)"""
        ).fetchone()[0]
        unmatched = connection.execute(
            """SELECT COUNT(*) FROM source_southern_presidential_geography_result r
               LEFT JOIN bridge_southern_result_geography b USING(result_observation_id)
               WHERE r.source_file_id IN (SELECT source_file_id FROM source_southern_vest_context_file)
                 AND b.geography_unit_id IS NULL"""
        ).fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        if duplicate_results or unmatched or foreign_keys:
            raise ValueError(
                f"VEST validation failed: duplicates={duplicate_results}, unmatched={unmatched}, "
                f"foreign_keys={foreign_keys[:5]}"
            )
        validation = {
            "states": len(audits),
            "input_features": sum(item["input_features"] for item in audits),
            "normalized_precincts": sum(item["normalized_precincts"] for item in audits),
            "repaired_input_geometries": sum(item["repaired_input_geometries"] for item in audits),
            "result_geometry_links": sum(item["result_geometry_links"] for item in audits),
            "review_states": sum(item["reconciliation_status"] == "review" for item in audits),
            "state_audits": audits,
        }
        for name, layer, key_value, authority, lifecycle, description in [
            ("source_southern_vest_context_file", "source", "source_file_id",
             "Manifest-backed Harvard Dataverse VEST archives", "replace",
             "VEST 2016 result/geometry archive registrations"),
            ("qa_southern_vest_context_ingest", "qa", "source_file_id",
             "Per-state result and geometry reconciliation", "replace",
             "VEST precinct normalization and one-to-one link audit"),
        ]:
            register_table(connection, name, layer, "scripts/load_southern_2016_vest_warehouse.py",
                           key_value, authority, lifecycle, description)
        finish_run(connection, run_id, validation)
        connection.commit()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"build_run_id": run_id, "validation": validation}, indent=2) + "\n",
                   encoding="utf-8")
    return {"build_run_id": run_id, "validation": validation}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.database), indent=2))


if __name__ == "__main__":
    main()
