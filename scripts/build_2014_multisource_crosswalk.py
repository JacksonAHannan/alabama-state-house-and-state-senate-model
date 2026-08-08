"""Build a 2014 crosswalk against VEST 2016 and consolidate geometry sources."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pyogrio

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_2014_precinct_crosswalk import (  # noqa: E402
    build_crosswalk,
    normalize_name,
    normalize_vtd_name,
    read_result_units,
)
from validate_2014_precinct_crosswalk import (  # noqa: E402
    compatible,
    list_text,
    load_openelections,
    spatial_membership,
)


def fips3(value: object) -> str:
    try:
        return str(int(float(value))).zfill(3)
    except (TypeError, ValueError):
        return str(value).zfill(3)


def vest16_targets(root: Path) -> pd.DataFrame:
    sources = root / "Results and Shapefiles"
    vest = pyogrio.read_dataframe(
        sources / "al_vest_16" / "al_vest_16.shp", read_geometry=False
    )
    county_source = pyogrio.read_dataframe(
        sources / "al_gen_22_prec" / "al_gen_22_st_prec.shp", read_geometry=False
    )
    county_source["fips"] = county_source["COUNTYFP"].map(fips3)
    county_map = (
        county_source[["fips", "County"]]
        .dropna()
        .drop_duplicates("fips")
        .set_index("fips")["County"]
        .map(normalize_name)
        .to_dict()
    )
    target = pd.DataFrame(
        {
            "county": vest["COUNTYFP20"].map(fips3).map(county_map),
            "county_fips": vest["COUNTYFP20"].map(fips3),
            "vtd_code": vest["VTDST16"].astype(str),
            "vtd_geoid": vest["GEOID16"].astype(str),
            "vtd_name": vest["NAME16"].astype(str),
        }
    )
    target["vtd_name_norm"] = target["vtd_name"].map(normalize_vtd_name)
    return target


def validate_vest16(
    root: Path, crosswalk: pd.DataFrame, activity: pd.DataFrame
) -> pd.DataFrame:
    activity_summary = (
        activity[activity["district_activity"] > 0]
        .groupby(["county_norm", "precinct_norm", "office"])
        .agg(inferred_districts=("district", list_text))
        .reset_index()
        .pivot(index=["county_norm", "precinct_norm"], columns="office")
    )
    activity_summary.columns = [
        ("house_" if office == "State House" else "senate_") + metric
        for metric, office in activity_summary.columns
    ]
    activity_summary = activity_summary.reset_index().rename(
        columns={"county_norm": "county", "precinct_norm": "result_precinct_norm"}
    )
    crosswalk = crosswalk.merge(
        activity_summary, on=["county", "result_precinct_norm"], how="left"
    )

    spatial = spatial_membership(root, "vest16")
    spatial = spatial[spatial["area_share"] >= 0.01]
    spatial_summary = (
        spatial.groupby(["vtd_geoid", "office"])
        .agg(spatial_districts=("district", list_text))
        .reset_index()
        .pivot(index="vtd_geoid", columns="office")
    )
    spatial_summary.columns = [
        ("house_" if office == "State House" else "senate_") + metric
        for metric, office in spatial_summary.columns
    ]
    spatial_summary = spatial_summary.reset_index()
    crosswalk["vtd_geoid"] = crosswalk["vtd_geoid"].astype("string")
    spatial_summary["vtd_geoid"] = spatial_summary["vtd_geoid"].astype("string")
    crosswalk = crosswalk.merge(spatial_summary, on="vtd_geoid", how="left")

    for chamber in ["house", "senate"]:
        inferred = f"{chamber}_inferred_districts"
        spatial_col = f"{chamber}_spatial_districts"
        crosswalk[inferred] = crosswalk[inferred].fillna("")
        crosswalk[spatial_col] = crosswalk[spatial_col].fillna("")
        crosswalk[f"{chamber}_district_compatible"] = [
            compatible(a, b) for a, b in zip(crosswalk[inferred], crosswalk[spatial_col])
        ]
    evidence = crosswalk[["house_district_compatible", "senate_district_compatible"]].notna().any(axis=1)
    conflict = crosswalk[["house_district_compatible", "senate_district_compatible"]].eq(False).any(axis=1)
    crosswalk["district_validation"] = "no_election_evidence"
    crosswalk.loc[evidence & ~conflict, "district_validation"] = "compatible"
    crosswalk.loc[conflict, "district_validation"] = "conflict"
    crosswalk["validated_match"] = crosswalk["accepted_match"] & (
        crosswalk["district_validation"] == "compatible"
    )
    crosswalk["accepted_conflict"] = crosswalk["accepted_match"] & (
        crosswalk["district_validation"] == "conflict"
    )
    return crosswalk


def consolidate(vtd10: pd.DataFrame, vest16: pd.DataFrame, overrides: pd.DataFrame) -> pd.DataFrame:
    vest_columns = [
        "result_unit_id",
        "vtd_geoid",
        "vtd_name",
        "match_method",
        "match_score",
        "score_margin",
        "accepted_match",
        "validated_match",
        "accepted_conflict",
        "district_validation",
        "relationship_note",
    ]
    combined = vtd10.merge(
        vest16[vest_columns].rename(columns={c: f"vest16_{c}" for c in vest_columns if c != "result_unit_id"}),
        on="result_unit_id",
        how="left",
    )
    combined["selected_geometry_source"] = ""
    combined["selected_geoid"] = pd.NA
    combined["selected_name"] = pd.NA
    combined["selection_status"] = "unresolved"

    use_vest = combined["vest16_validated_match"].fillna(False)
    use_vtd = ~use_vest & combined["validated_match"].fillna(False)
    vest_provisional = (
        ~use_vest
        & ~use_vtd
        & combined["vest16_accepted_match"].fillna(False)
        & ~combined["vest16_accepted_conflict"].fillna(False)
    )
    vtd_provisional = (
        ~use_vest
        & ~use_vtd
        & ~vest_provisional
        & combined["accepted_match"].fillna(False)
        & ~combined["accepted_conflict"].fillna(False)
    )
    for mask, source, prefix, status in [
        (use_vest, "vest16", "vest16_", "district_validated"),
        (use_vtd, "vtd10", "", "district_validated"),
        (vest_provisional, "vest16", "vest16_", "name_accepted_unvalidated"),
        (vtd_provisional, "vtd10", "", "name_accepted_unvalidated"),
    ]:
        combined.loc[mask, "selected_geometry_source"] = source
        combined.loc[mask, "selected_geoid"] = combined.loc[mask, f"{prefix}vtd_geoid"]
        combined.loc[mask, "selected_name"] = combined.loc[mask, f"{prefix}vtd_name"]
        combined.loc[mask, "selection_status"] = status
    combined.loc[combined["is_non_geographic"], "selection_status"] = "non_geographic"

    constrained = (
        (combined["selection_status"] == "unresolved")
        & (combined["recommendation_method"] == "district_constrained_medium")
    )
    combined.loc[constrained, "selected_geometry_source"] = "vtd10"
    combined.loc[constrained, "selected_geoid"] = combined.loc[constrained, "recommended_vtd_geoid"]
    combined.loc[constrained, "selected_name"] = combined.loc[constrained, "recommended_vtd_name"]
    combined.loc[constrained, "selection_status"] = "district_constrained_accepted"

    if not overrides.empty:
        override_map = overrides.set_index("result_unit_id")
        overridden = combined["result_unit_id"].isin(override_map.index)
        for index in combined.index[overridden]:
            override = override_map.loc[combined.at[index, "result_unit_id"]]
            combined.at[index, "selected_geometry_source"] = override["geometry_source"]
            combined.at[index, "selected_geoid"] = override["geoid"]
            combined.at[index, "selected_name"] = override["geometry_name"]
            combined.at[index, "selection_status"] = "manual_override"
            combined.at[index, "manual_override_reason"] = override["override_reason"]
            combined.at[index, "manual_override_evidence"] = override["evidence"]

    selected = combined["selection_status"].isin(
        ["district_validated", "name_accepted_unvalidated", "district_constrained_accepted", "manual_override"]
    )
    combined["relationship_class"] = "unresolved"
    combined.loc[combined["is_non_geographic"], "relationship_class"] = "non_geographic"
    combined.loc[selected, "relationship_class"] = "one_to_one"
    machine_count = combined.groupby(["county", "result_match_norm"])["result_unit_id"].transform("size")
    combined.loc[selected & (machine_count > 1), "relationship_class"] = "multi_machine"
    distinct_names_per_geometry = (
        combined.loc[selected]
        .groupby(["selected_geometry_source", "selected_geoid"])["result_match_norm"]
        .transform("nunique")
    )
    combined.loc[selected, "distinct_result_names_for_geometry"] = distinct_names_per_geometry.values
    composite = selected & (pd.to_numeric(combined["distinct_result_names_for_geometry"], errors="coerce").fillna(0) > 1)
    combined.loc[composite, "relationship_class"] = "composite_geometry"
    return combined


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output = root / "data" / "derived" / "crosswalks"
    units = read_result_units(root / "Results and Shapefiles" / "2014General-precinctLevel")
    target = vest16_targets(root)
    vest_crosswalk = build_crosswalk(units, target)
    _, activity = load_openelections(
        root / "data" / "raw" / "openelections" / "20141104__al__general__precinct.csv"
    )
    vest_crosswalk = validate_vest16(root, vest_crosswalk, activity)
    vest_crosswalk.to_csv(output / "2014_precinct_vest16_crosswalk_validated.csv", index=False)

    vtd10 = pd.read_csv(output / "2014_precinct_vtd_crosswalk_validated.csv", low_memory=False)
    override_path = root / "data" / "manual" / "2014_precinct_geometry_overrides.csv"
    overrides = pd.read_csv(override_path, dtype={"geoid": "string"}) if override_path.exists() else pd.DataFrame()
    consolidated = consolidate(vtd10, vest_crosswalk, overrides)
    consolidated.to_csv(output / "2014_precinct_geometry_crosswalk_consolidated.csv", index=False)
    consolidated[consolidated["selection_status"] == "unresolved"].to_csv(
        output / "2014_precinct_geometry_unresolved.csv", index=False
    )
    geographic = consolidated[~consolidated["is_non_geographic"]]
    summary = pd.DataFrame(
        [
            {
                "geographic_units": len(geographic),
                "selected_units": int((geographic["selection_status"] != "unresolved").sum()),
                "selected_rate": round(float((geographic["selection_status"] != "unresolved").mean()), 4),
                "district_validated": int((geographic["selection_status"] == "district_validated").sum()),
                "name_accepted_unvalidated": int((geographic["selection_status"] == "name_accepted_unvalidated").sum()),
                "district_constrained_accepted": int((geographic["selection_status"] == "district_constrained_accepted").sum()),
                "manual_overrides": int((geographic["selection_status"] == "manual_override").sum()),
                "unresolved": int((geographic["selection_status"] == "unresolved").sum()),
                "vest16_selected": int((geographic["selected_geometry_source"] == "vest16").sum()),
                "vtd10_selected": int((geographic["selected_geometry_source"] == "vtd10").sum()),
                "one_to_one": int((geographic["relationship_class"] == "one_to_one").sum()),
                "multi_machine": int((geographic["relationship_class"] == "multi_machine").sum()),
                "composite_geometry": int((geographic["relationship_class"] == "composite_geometry").sum()),
            }
        ]
    )
    summary.to_csv(output / "2014_precinct_geometry_crosswalk_summary.csv", index=False)
    county_summary = (
        geographic.assign(selected=geographic["selection_status"] != "unresolved")
        .groupby("county", as_index=False)
        .agg(
            geographic_units=("result_unit_id", "size"),
            selected_units=("selected", "sum"),
            district_validated=("selection_status", lambda x: (x == "district_validated").sum()),
            constrained_or_manual=("selection_status", lambda x: x.isin(["district_constrained_accepted", "manual_override"]).sum()),
            unresolved=("selection_status", lambda x: (x == "unresolved").sum()),
        )
    )
    county_summary["selected_rate"] = (
        county_summary["selected_units"] / county_summary["geographic_units"]
    ).round(4)
    county_summary.to_csv(output / "2014_precinct_geometry_crosswalk_by_county.csv", index=False)


if __name__ == "__main__":
    main()
