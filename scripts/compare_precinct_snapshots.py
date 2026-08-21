"""Compare two precinct snapshots and emit provenance-neutral inferred lineage."""
from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ALABAMA_EQUAL_AREA = 5070
COUNTY_FIELDS = ("county_fips", "COUNTYFP", "COUNTYFP20", "COUNTY", "county")
NAME_FIELDS = (
    "precinct_name",
    "NAME",
    "NAME20",
    "NAME18",
    "NAME16",
    "PRECINCT",
    "precinct",
    "VTDST",
)
CODE_FIELDS = (
    "precinct_code",
    "VTDST",
    "VTDST20",
    "VTDST18",
    "VTDST16",
    "PRECINCT",
    "precinct",
)


def choose_column(frame: pd.DataFrame, choices: tuple[str, ...], explicit: str | None) -> str:
    if explicit:
        if explicit not in frame: raise KeyError(f"Missing requested field {explicit}")
        return explicit
    for choice in choices:
        if choice in frame: return choice
    raise KeyError(f"Could not identify a field from {choices}; available={list(frame.columns)}")


def prepare(frame: gpd.GeoDataFrame, *, side: str, county_field: str | None = None,
            name_field: str | None = None, code_field: str | None = None) -> gpd.GeoDataFrame:
    if frame.crs is None: raise ValueError(f"{side} snapshot has no CRS")
    county = choose_column(frame, COUNTY_FIELDS, county_field)
    name = choose_column(frame, NAME_FIELDS, name_field)
    code = choose_column(frame, CODE_FIELDS, code_field)
    result = frame[[county, name, code, "geometry"]].copy().rename(
        columns={county:"county_fips", name:f"{side}_name", code:f"{side}_code"})
    result["county_fips"] = result.county_fips.astype(str).str.extract(r"(\d+)", expand=False).str[-3:].str.zfill(3)
    result[f"{side}_name"] = result[f"{side}_name"].astype(str).str.strip()
    result[f"{side}_code"] = result[f"{side}_code"].astype(str).str.strip()
    result = result[result.geometry.notna() & ~result.geometry.is_empty].copy().to_crs(ALABAMA_EQUAL_AREA)
    result.geometry = result.geometry.make_valid()
    result[f"{side}_id"] = [f"{side.upper()}-{i+1:06d}" for i in range(len(result))]
    result[f"{side}_area"] = result.geometry.area
    return result


def compare_frames(old: gpd.GeoDataFrame, new: gpd.GeoDataFrame, *, equivalent: float = .995,
                   minor: float = .95) -> pd.DataFrame:
    old = prepare(old, side="old") if "old_id" not in old else old
    new = prepare(new, side="new") if "new_id" not in new else new
    joined = gpd.sjoin(old, new, how="inner", predicate="intersects", lsuffix="old", rsuffix="new")
    records = []
    for row in joined.itertuples():
        old_row = old.loc[old.old_id.eq(row.old_id)].iloc[0]
        new_row = new.loc[new.new_id.eq(row.new_id)].iloc[0]
        if old_row.county_fips != new_row.county_fips: continue
        intersection = old_row.geometry.intersection(new_row.geometry).area
        if intersection <= 0: continue
        union = old_row.old_area + new_row.new_area - intersection
        records.append({"county_fips":old_row.county_fips,"old_id":row.old_id,"new_id":row.new_id,
          "old_name":old_row.old_name,"new_name":new_row.new_name,
          "old_code":old_row.old_code,"new_code":new_row.new_code,
          "intersection_area":intersection,"old_area":old_row.old_area,"new_area":new_row.new_area,
          "pct_old_in_new":intersection/old_row.old_area,"pct_new_from_old":intersection/new_row.new_area,
          "intersection_over_union":intersection/union,
          "symmetric_difference_area":union-intersection})
    overlap = pd.DataFrame(records)
    if overlap.empty: return overlap
    meaningful = overlap[(overlap.pct_old_in_new >= .005) | (overlap.pct_new_from_old >= .005)].copy()
    old_degree = meaningful.groupby("old_id").new_id.nunique()
    new_degree = meaningful.groupby("new_id").old_id.nunique()
    meaningful["old_degree"] = meaningful.old_id.map(old_degree)
    meaningful["new_degree"] = meaningful.new_id.map(new_degree)
    mutual = np.minimum(meaningful.pct_old_in_new, meaningful.pct_new_from_old)
    same_label = (meaningful.old_name.str.upper().eq(meaningful.new_name.str.upper()) |
                  meaningful.old_code.str.upper().eq(meaningful.new_code.str.upper()))
    meaningful["inferred_relationship"] = np.select([
      (mutual >= equivalent) & same_label,
      (mutual >= equivalent) & ~same_label,
      same_label & (mutual < minor),
      meaningful.old_degree.gt(1) & meaningful.new_degree.eq(1),
      meaningful.old_degree.eq(1) & meaningful.new_degree.gt(1),
      (mutual >= minor),
      meaningful.old_degree.gt(1) & meaningful.new_degree.gt(1),
    ],["unchanged","probable_rename_or_renumber","probable_boundary_adjustment","probable_split","probable_consolidation",
       "probable_minor_boundary_or_source_difference","probable_many_to_many_realignment"],
      default="probable_boundary_adjustment")
    meaningful["verification_status"] = "inferred_from_snapshot_diff"
    return meaningful.sort_values(["county_fips","old_id","intersection_area"],ascending=[True,True,False])


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument("old",type=Path);parser.add_argument("new",type=Path)
    parser.add_argument("--output",type=Path,required=True);parser.add_argument("--equivalent",type=float,default=.995)
    parser.add_argument("--minor",type=float,default=.95);args=parser.parse_args()
    result=compare_frames(gpd.read_file(args.old),gpd.read_file(args.new),equivalent=args.equivalent,minor=args.minor)
    args.output.parent.mkdir(parents=True,exist_ok=True);result.to_csv(args.output,index=False)
    print(result.inferred_relationship.value_counts(dropna=False).to_string())


if __name__=="__main__":main()
