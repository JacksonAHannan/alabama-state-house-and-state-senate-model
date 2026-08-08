"""Enhance the 2014 name crosswalk with election and spatial validation."""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio
from rapidfuzz import fuzz, process

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_2014_precinct_crosswalk import normalize_name, read_vtds  # noqa: E402


def list_text(values: pd.Series) -> str:
    return ";".join(str(int(x)) for x in sorted(set(values.dropna().astype(int))))


def load_openelections(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = pd.read_csv(path, low_memory=False)
    data["county_norm"] = data["county"].map(normalize_name)
    data["precinct_norm"] = data["precinct"].map(normalize_name)
    units = data[["county_norm", "precinct_norm", "precinct"]].drop_duplicates(
        ["county_norm", "precinct_norm"]
    )

    legislative = data[data["office"].isin(["State House", "State Senate"])].copy()
    legislative["district"] = pd.to_numeric(legislative["district"], errors="coerce")
    legislative["votes"] = pd.to_numeric(legislative["votes"], errors="coerce").fillna(0)
    legislative = legislative.dropna(subset=["district"])
    totals = (
        legislative.groupby(
            ["county_norm", "precinct_norm", "office", "district"], as_index=False
        )["votes"]
        .sum()
        .rename(columns={"votes": "district_activity"})
    )
    totals["office_activity"] = totals.groupby(
        ["county_norm", "precinct_norm", "office"]
    )["district_activity"].transform("sum")
    totals["activity_share"] = totals["district_activity"] / totals["office_activity"].where(
        totals["office_activity"] > 0
    )
    return units, totals


def read_zip_geometry(path: Path) -> gpd.GeoDataFrame:
    with zipfile.ZipFile(path) as archive:
        layer = next(n for n in archive.namelist() if n.lower().endswith(".shp"))
    return pyogrio.read_dataframe(f"/vsizip/{path.as_posix()}/{layer}")


def spatial_membership(root: Path, geometry_source: str = "vtd10") -> pd.DataFrame:
    sources = root / "Results and Shapefiles"
    if geometry_source == "vtd10":
        vtd = read_zip_geometry(sources / "tl_2012_01_vtd10.zip").rename(
            columns={"GEOID10": "vtd_geoid"}
        )[["vtd_geoid", "geometry"]]
    elif geometry_source == "vest16":
        vtd = gpd.read_file(sources / "al_vest_16" / "al_vest_16.shp").rename(
            columns={"GEOID16": "vtd_geoid"}
        )[["vtd_geoid", "geometry"]]
    else:
        raise ValueError(f"Unknown geometry source: {geometry_source}")
    house = gpd.read_file(
        sources / "al_sldl_2012_to_2017" / "al_sldl_2012_to_2017.shp"
    )[["SLDLST", "geometry"]].rename(columns={"SLDLST": "district"})
    senate = gpd.read_file(
        sources / "al_sldu_2012_to_2017" / "al_sldu_2012_to_2017.shp"
    )[["LONGNAME", "geometry"]]
    senate["district"] = senate["LONGNAME"].str.extract(r"(\d+)").astype(int)
    senate = senate[["district", "geometry"]]

    vtd = vtd.to_crs(5070)
    vtd["vtd_area"] = vtd.geometry.area
    rows: list[pd.DataFrame] = []
    for chamber, districts in [("State House", house), ("State Senate", senate)]:
        districts = districts.to_crs(5070)
        intersections = gpd.overlay(vtd, districts, how="intersection", keep_geom_type=False)
        intersections["area_share"] = intersections.geometry.area / intersections["vtd_area"]
        intersections["district"] = pd.to_numeric(intersections["district"], errors="coerce")
        intersections["office"] = chamber
        rows.append(intersections[["vtd_geoid", "office", "district", "area_share"]])
    return pd.concat(rows, ignore_index=True)


def compatible(inferred: str, spatial: str) -> object:
    if not inferred:
        return pd.NA
    inferred_set = {int(x) for x in inferred.split(";") if x}
    spatial_set = {int(x) for x in spatial.split(";") if x}
    return bool(inferred_set & spatial_set)


def district_set(value: object) -> set[int]:
    if pd.isna(value) or not str(value):
        return set()
    return {int(x) for x in str(value).split(";") if x}


def add_constrained_recommendations(
    crosswalk: pd.DataFrame, targets: pd.DataFrame
) -> pd.DataFrame:
    fields = [
        "recommended_vtd_geoid",
        "recommended_vtd_name",
        "recommended_score",
        "recommended_margin",
        "recommendation_method",
        "constrained_candidate_count",
    ]
    for field in fields:
        crosswalk[field] = pd.NA

    by_county = {k: v.reset_index(drop=True) for k, v in targets.groupby("county")}
    for index, row in crosswalk[crosswalk["needs_review"]].iterrows():
        candidates = by_county.get(row["county"])
        if candidates is None:
            continue
        candidates = candidates.copy()
        house = district_set(row.get("house_inferred_districts"))
        senate = district_set(row.get("senate_inferred_districts"))
        if house:
            candidates = candidates[
                candidates["house_spatial_districts"].map(district_set).map(lambda x: bool(x & house))
            ]
        if senate:
            candidates = candidates[
                candidates["senate_spatial_districts"].map(district_set).map(lambda x: bool(x & senate))
            ]
        if candidates.empty:
            crosswalk.at[index, "recommendation_method"] = "no_district_compatible_vtd"
            crosswalk.at[index, "constrained_candidate_count"] = 0
            continue
        choices = candidates["vtd_name_norm"].fillna("").tolist()
        matches = process.extract(row["result_match_norm"], choices, scorer=fuzz.WRatio, limit=2)
        best_name, score, _ = matches[0]
        second = matches[1][1] if len(matches) > 1 else 0.0
        margin = float(score - second)
        best = candidates[candidates["vtd_name_norm"].fillna("") == best_name].iloc[0]
        method = "district_constrained_review"
        if score >= 94 and margin >= 5:
            method = "district_constrained_high"
        elif score >= 88 and margin >= 8:
            method = "district_constrained_medium"
        crosswalk.loc[index, fields] = [
            best["vtd_geoid"],
            best["vtd_name"],
            round(float(score), 2),
            round(margin, 2),
            method,
            len(candidates),
        ]
    return crosswalk


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output = root / "data" / "derived" / "crosswalks"
    crosswalk = pd.read_csv(output / "2014_precinct_vtd_crosswalk.csv", dtype={"vtd_geoid": "string"})
    oe_units, activity = load_openelections(
        root / "data" / "raw" / "openelections" / "20141104__al__general__precinct.csv"
    )
    activity.to_csv(output / "2014_precinct_legislative_district_activity.csv", index=False)

    oe_keys = set(zip(oe_units["county_norm"], oe_units["precinct_norm"]))
    crosswalk["openelections_unit_found"] = [
        (county, precinct) in oe_keys
        for county, precinct in zip(crosswalk["county"], crosswalk["result_precinct_norm"])
    ]

    activity_summary = (
        activity[activity["district_activity"] > 0]
        .groupby(["county_norm", "precinct_norm", "office"])
        .agg(
            inferred_districts=("district", list_text),
            inferred_district_count=("district", "nunique"),
            largest_activity_share=("activity_share", "max"),
        )
        .reset_index()
    )
    wide = activity_summary.pivot(
        index=["county_norm", "precinct_norm"], columns="office"
    )
    wide.columns = [
        ("house_" if office == "State House" else "senate_") + metric
        for metric, office in wide.columns
    ]
    wide = wide.reset_index().rename(
        columns={"county_norm": "county", "precinct_norm": "result_precinct_norm"}
    )
    crosswalk = crosswalk.merge(wide, on=["county", "result_precinct_norm"], how="left")

    spatial = spatial_membership(root)
    spatial = spatial[spatial["area_share"] >= 0.01].copy()
    spatial_summary = (
        spatial.groupby(["vtd_geoid", "office"])
        .agg(
            spatial_districts=("district", list_text),
            largest_spatial_share=("area_share", "max"),
        )
        .reset_index()
        .pivot(index="vtd_geoid", columns="office")
    )
    spatial_summary.columns = [
        ("house_" if office == "State House" else "senate_") + metric
        for metric, office in spatial_summary.columns
    ]
    spatial_summary = spatial_summary.reset_index()
    crosswalk = crosswalk.merge(spatial_summary, on="vtd_geoid", how="left")

    for chamber in ["house", "senate"]:
        inferred_col = f"{chamber}_inferred_districts"
        spatial_col = f"{chamber}_spatial_districts"
        crosswalk[inferred_col] = crosswalk[inferred_col].fillna("")
        crosswalk[spatial_col] = crosswalk[spatial_col].fillna("")
        crosswalk[f"{chamber}_district_compatible"] = [
            compatible(a, b) for a, b in zip(crosswalk[inferred_col], crosswalk[spatial_col])
        ]

    has_election_evidence = crosswalk[
        ["house_district_compatible", "senate_district_compatible"]
    ].notna().any(axis=1)
    any_conflict = (
        crosswalk[["house_district_compatible", "senate_district_compatible"]]
        .eq(False)
        .any(axis=1)
    )
    crosswalk["district_validation"] = "no_election_evidence"
    crosswalk.loc[has_election_evidence & ~any_conflict, "district_validation"] = "compatible"
    crosswalk.loc[any_conflict, "district_validation"] = "conflict"
    crosswalk["validated_match"] = crosswalk["accepted_match"] & (
        crosswalk["district_validation"] == "compatible"
    )
    crosswalk["accepted_unvalidated"] = crosswalk["accepted_match"] & (
        crosswalk["district_validation"] == "no_election_evidence"
    )
    crosswalk["accepted_conflict"] = crosswalk["accepted_match"] & (
        crosswalk["district_validation"] == "conflict"
    )

    sources = root / "Results and Shapefiles"
    targets = read_vtds(
        sources / "tl_2012_01_vtd10.zip",
        sources / "al_gen_22_prec" / "al_gen_22_st_prec.shp",
    )
    targets["vtd_geoid"] = targets["vtd_geoid"].astype("string")
    targets = targets.merge(spatial_summary, on="vtd_geoid", how="left")
    for column in ["house_spatial_districts", "senate_spatial_districts"]:
        targets[column] = targets[column].fillna("")
    crosswalk = add_constrained_recommendations(crosswalk, targets)
    crosswalk.to_csv(output / "2014_precinct_vtd_crosswalk_validated.csv", index=False)
    crosswalk[
        crosswalk["needs_review"] | crosswalk["accepted_conflict"]
    ].to_csv(output / "2014_precinct_vtd_review_enhanced.csv", index=False)

    geographic = crosswalk[~crosswalk["is_non_geographic"]]
    summary = pd.DataFrame(
        [
            {
                "geographic_units": len(geographic),
                "openelections_units_found": int(geographic["openelections_unit_found"].sum()),
                "openelections_coverage": round(float(geographic["openelections_unit_found"].mean()), 4),
                "accepted_name_matches": int(geographic["accepted_match"].sum()),
                "district_validated_matches": int(geographic["validated_match"].sum()),
                "accepted_district_conflicts": int(geographic["accepted_conflict"].sum()),
                "accepted_without_election_evidence": int(geographic["accepted_unvalidated"].sum()),
                "name_review_units": int(geographic["needs_review"].sum()),
                "district_constrained_high": int((geographic["recommendation_method"] == "district_constrained_high").sum()),
                "district_constrained_medium": int((geographic["recommendation_method"] == "district_constrained_medium").sum()),
            }
        ]
    )
    summary.to_csv(output / "2014_precinct_vtd_validation_summary.csv", index=False)

    county_summary = (
        geographic.groupby("county", as_index=False)
        .agg(
            geographic_units=("result_unit_id", "size"),
            openelections_found=("openelections_unit_found", "sum"),
            accepted_name=("accepted_match", "sum"),
            district_validated=("validated_match", "sum"),
            accepted_conflicts=("accepted_conflict", "sum"),
            needs_review=("needs_review", "sum"),
            constrained_medium=("recommendation_method", lambda x: (x == "district_constrained_medium").sum()),
        )
    )
    county_summary["district_validated_rate"] = (
        county_summary["district_validated"] / county_summary["geographic_units"]
    ).round(4)
    county_summary.to_csv(output / "2014_precinct_vtd_validation_by_county.csv", index=False)


if __name__ == "__main__":
    main()
