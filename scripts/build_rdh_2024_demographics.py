"""Normalize and audit Redistricting Data Hub Alabama 2024 inputs.

Raw RDH archives remain immutable.  Outputs are validation/experimental marts;
this script does not replace production forecast features.
"""
from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "rdh"
CENSUS = ROOT / "data" / "raw" / "census"
MAPS = ROOT / "data" / "raw" / "alabama_elections_and_geography"
OUT = ROOT / "data" / "processed" / "demographics"
VALID = ROOT / "data" / "processed" / "elections" / "validation"

DISTRICTS = {
    "house": (MAPS / "tl_2025_01_sldl" / "tl_2025_01_sldl.shp", "SLDLST", 105),
    "senate": (MAPS / "tl_2025_01_sldu" / "tl_2025_01_sldu.shp", "SLDUST", 35),
}


def zipped_csv(archive: str, member: str) -> pd.DataFrame:
    with zipfile.ZipFile(RAW / archive) as bundle, bundle.open(member) as stream:
        return pd.read_csv(stream, low_memory=False)


def assignments() -> pd.DataFrame:
    blocks = gpd.read_file(f"zip://{(CENSUS / 'tl_2020_01_tabblock20.zip').resolve()}")
    blocks = blocks[["GEOID20", "geometry"]].to_crs(5070)
    points = blocks.copy()
    points.geometry = points.geometry.representative_point()
    parts = []
    for chamber, (path, field, expected) in DISTRICTS.items():
        districts = gpd.read_file(path)[[field, "LSY", "geometry"]].to_crs(5070)
        if len(districts) != expected or set(districts.LSY.astype(str)) != {"2024"}:
            raise ValueError(f"Unexpected {chamber} district vintage")
        joined = gpd.sjoin(points, districts[[field, "geometry"]], how="left", predicate="within")
        if joined[field].isna().any():
            missing = joined[field].isna()
            nearest = gpd.sjoin_nearest(points.loc[missing], districts[[field, "geometry"]],
                                        how="left", distance_col="snap_distance")
            nearest = nearest.sort_values("snap_distance").drop_duplicates("GEOID20").set_index("GEOID20")
            joined.loc[missing, field] = joined.loc[missing, "GEOID20"].map(nearest[field])
        part = joined[["GEOID20", field]].rename(columns={field: "district"})
        part["district"] = pd.to_numeric(part.district).astype(int)
        part["chamber"] = chamber
        parts.append(part)
    return pd.concat(parts, ignore_index=True)


def direct_cvap() -> pd.DataFrame:
    frames = []
    for chamber, archive, member, field in [
        ("house", "al_cvap_2024_sldl_csv.zip", "al_cvap_2024_sldl.csv", "SLDL24"),
        ("senate", "al_cvap_2024_sldu_csv.zip", "al_cvap_2024_sldu.csv", "SLDU24"),
    ]:
        x = zipped_csv(archive, member)
        x["chamber"] = chamber
        x["district"] = pd.to_numeric(x[field]).astype(int)
        frames.append(x)
    x = pd.concat(frames, ignore_index=True)
    x["cvap_white_nh_share"] = x.CVAP_WHT24 / x.CVAP_TOT24
    x["cvap_nonwhite_share"] = 1 - x.cvap_white_nh_share
    x["cvap_black_nh_share"] = x.CVAP_BLA24 / x.CVAP_TOT24
    x["cvap_hispanic_share"] = x.CVAP_HSP24 / x.CVAP_TOT24
    x["cvap_other_nonwhite_share"] = (
        x.CVAP_TOT24 - x.CVAP_WHT24 - x.CVAP_BLA24 - x.CVAP_HSP24) / x.CVAP_TOT24
    x["cvap_total_moe_ratio"] = x.CVAPTOTMOE / x.CVAP_TOT24
    x["cycle"] = 2026
    x["source"] = "RDH/Census 2020-2024 ACS CVAP special tabulation"
    columns = ["cycle", "chamber", "district", "NAME", "CVAP_TOT24", "CVAPTOTMOE",
               "cvap_total_moe_ratio", "cvap_white_nh_share", "cvap_nonwhite_share",
               "cvap_black_nh_share", "cvap_hispanic_share", "cvap_other_nonwhite_share", "source"]
    return x[columns]


def block_cvap_validation(assign: pd.DataFrame, direct: pd.DataFrame) -> pd.DataFrame:
    blocks = zipped_csv("al_cvap_2024_2020_b_csv.zip", "al_cvap_2024_2020_b.csv")
    blocks["GEOID20"] = blocks.GEOID20.astype(str).str.zfill(15)
    cols = [column for column in blocks if column.startswith("CVAP_")]
    allocated = assign.merge(blocks[["GEOID20", *cols]], on="GEOID20", how="left", validate="many_to_one")
    district = allocated.groupby(["chamber", "district"], as_index=False)[cols].sum()
    district["block_cvap_nonwhite_share"] = 1 - district.CVAP_WHT24 / district.CVAP_TOT24
    result = district.merge(direct[["chamber", "district", "CVAP_TOT24", "cvap_nonwhite_share"]],
                            on=["chamber", "district"], suffixes=("_block", "_direct"), validate="one_to_one")
    result["cvap_total_difference"] = result.CVAP_TOT24_block - result.CVAP_TOT24_direct
    result["nonwhite_share_difference"] = result.block_cvap_nonwhite_share - result.cvap_nonwhite_share
    return result


def education(assign: pd.DataFrame) -> pd.DataFrame:
    edu = zipped_csv("al_edu_2024_bg_csv.zip", "al_edu_2024_bg.csv")
    edu["block_group"] = edu.GEOID.astype(str).str.zfill(12)
    blocks = zipped_csv("al_cvap_2024_2020_b_csv.zip", "al_cvap_2024_2020_b.csv")
    blocks["GEOID20"] = blocks.GEOID20.astype(str).str.zfill(15)
    blocks["block_group"] = blocks.GEOID20.str[:12]
    weights = assign.merge(blocks[["GEOID20", "block_group", "CVAP_TOT24"]], on="GEOID20", how="left")
    weights["bg_cvap"] = weights.groupby(["chamber", "block_group"]).CVAP_TOT24.transform("sum")
    weights["allocation_weight"] = np.where(weights.bg_cvap.gt(0), weights.CVAP_TOT24 / weights.bg_cvap, 0)
    weights = weights.groupby(["chamber", "district", "block_group"], as_index=False).allocation_weight.sum()
    value_cols = ["POP_25OV24", "N_HSDIP24", "HS_DIP24", "SOM_COLL24", "ASSO_DEG24",
                  "BACH_DEG24", "MAST_DEG24", "PROF_DEG24", "DOCT_DEG24"]
    allocated = weights.merge(edu[["block_group", *value_cols]], on="block_group", how="left", validate="many_to_one")
    for column in value_cols:
        allocated[column] *= allocated.allocation_weight
    out = allocated.groupby(["chamber", "district"], as_index=False)[value_cols].sum()
    out["college_share_2024"] = out[["BACH_DEG24", "MAST_DEG24", "PROF_DEG24", "DOCT_DEG24"]].sum(axis=1) / out.POP_25OV24
    out["education_allocation_method"] = "block_group_to_2024_SLD_weighted_by_2024_CVAP_disaggregation"
    out["cycle"] = 2026
    return out


def current_comparison(direct: pd.DataFrame, edu: pd.DataFrame) -> pd.DataFrame:
    current = pd.read_csv(OUT / "acs_direct_sld_demographics.csv")
    current = current[current.cycle.eq(2022)][["chamber", "district", "nonwhite_share", "college_share", "white_college_share"]]
    result = direct.merge(edu[["chamber", "district", "college_share_2024"]], on=["chamber", "district"])
    result = result.merge(current, on=["chamber", "district"], how="left", validate="one_to_one")
    result["cvap_minus_total_population_nonwhite"] = result.cvap_nonwhite_share - result.nonwhite_share
    result["college_2024_minus_2022"] = result.college_share_2024 - result.college_share
    return result


def turnout(assign: pd.DataFrame) -> pd.DataFrame:
    x = zipped_csv("AL_l2_2024_gen_stats_2020block.zip",
                   "AL_l2_2024_gen_stats_2020block/AL_l2_2024_gen_stats_2020block.csv")
    x["GEOID20"] = x.geoid20.astype(str).str.zfill(15)
    count_cols = [column for column in x if column.startswith(("voted_", "reg_"))]
    out = assign.merge(x[["GEOID20", *count_cols]], on="GEOID20", how="left")
    out = out.groupby(["chamber", "district"], as_index=False)[count_cols].sum()
    out["l2_general_turnout_rate"] = out.voted_all / out.reg_all.replace(0, np.nan)
    out["cycle"] = 2026
    out["status"] = "experimental_L2_derived_not_forecast_promoted"
    return out


def projected_vap(assign: pd.DataFrame) -> pd.DataFrame:
    x = zipped_csv("al_vap_proj_2026_2035_b.zip", "al_vap_proj_2026_2035_b.csv")
    x["GEOID20"] = x.GEOID.astype(str).str.zfill(15)
    value_cols = [column for column in x if column.endswith("_2026")]
    out = assign.merge(x[["GEOID20", *value_cols]], on="GEOID20", how="left", validate="many_to_one")
    out = out.groupby(["chamber", "district"], as_index=False)[value_cols].sum()
    total = out.Projected_TotalPop_VAP_2026
    out["projected_vap_white_nh_share"] = out.Projected_WhiteAloneNotHisp_VAP_2026 / total
    out["projected_vap_nonwhite_share"] = 1 - out.projected_vap_white_nh_share
    out["projected_vap_black_share"] = out.Projected_BlackOrAfAmAlone_VAP_2026 / total
    out["projected_vap_hispanic_share"] = out.Projected_HispanicOrLatino_VAP_2026 / total
    out["cycle"] = 2026
    out["status"] = "experimental_RDH_population_projection"
    return out


def manifest() -> pd.DataFrame:
    rows = []
    for path in sorted(RAW.glob("*.zip")):
        with zipfile.ZipFile(path) as bundle:
            bad = bundle.testzip()
            members = len(bundle.namelist())
        rows.append({"source_file": str(path.relative_to(ROOT)), "bytes": path.stat().st_size,
                     "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "zip_members": members,
                     "integrity_ok": bad is None, "provider": "Redistricting Data Hub",
                     "retrieved_by": "user account download", "retrieval_date": "2026-08-17"})
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    VALID.mkdir(parents=True, exist_ok=True)
    assign = assignments()
    direct = direct_cvap()
    cvap_qa = block_cvap_validation(assign, direct)
    edu = education(assign)
    comparison = current_comparison(direct, edu)
    l2 = turnout(assign)
    vap = projected_vap(assign)
    direct.to_csv(OUT / "rdh_2024_sld_cvap.csv", index=False)
    edu.to_csv(OUT / "rdh_2024_sld_education_experimental.csv", index=False)
    l2.to_csv(OUT / "rdh_2024_l2_sld_turnout_experimental.csv", index=False)
    vap.to_csv(OUT / "rdh_2026_projected_vap_sld_experimental.csv", index=False)
    comparison.to_csv(VALID / "rdh_2024_current_demographic_comparison.csv", index=False)
    cvap_qa.to_csv(VALID / "rdh_2024_block_to_direct_sld_cvap_validation.csv", index=False)
    manifest().to_csv(RAW / "source_manifest.csv", index=False)
    print("Current comparison")
    print(comparison.groupby("chamber")[["cvap_minus_total_population_nonwhite", "college_2024_minus_2022"]]
          .agg(["mean", "median", "min", "max"]).to_string())
    print("\nBlock CVAP validation")
    print(cvap_qa.groupby("chamber")[["cvap_total_difference", "nonwhite_share_difference"]]
          .agg(["mean", "min", "max"]).to_string())


if __name__ == "__main__":
    main()
