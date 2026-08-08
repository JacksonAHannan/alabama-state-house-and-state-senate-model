"""Aggregate partial 2012 presidential returns onto the 2018 remedial maps."""

from pathlib import Path
import geopandas as gpd
import pandas as pd
from build_2014_precinct_crosswalk import normalize_name

ROOT = Path(__file__).resolve().parents[1]
PRES = ROOT / "data" / "processed" / "presidential"
CW = ROOT / "data" / "derived" / "crosswalks"


def main() -> None:
    vote_qa = pd.read_csv(CW / "2012_president_vtd_vote_qa.csv")
    accepted = vote_qa[vote_qa.accepted_match.fillna(False)].copy()
    accepted["vtd_geoid"] = accepted.vtd_geoid.astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(11)
    vtd_votes = (accepted.groupby(["county", "vtd_geoid"], as_index=False)
                 [["dem_votes", "rep_votes"]].sum())
    county_total = vote_qa.groupby("county", as_index=False)[["dem_votes", "rep_votes"]].sum()
    county_direct = vtd_votes.groupby("county", as_index=False)[["dem_votes", "rep_votes"]].sum()
    residual = county_total.merge(county_direct, on="county", how="left", suffixes=("_total", "_direct"))
    residual[["dem_votes_direct", "rep_votes_direct"]] = residual[
        ["dem_votes_direct", "rep_votes_direct"]].fillna(0)
    residual["dem_residual"] = residual.dem_votes_total - residual.dem_votes_direct
    residual["rep_residual"] = residual.rep_votes_total - residual.rep_votes_direct

    vtd = gpd.read_file(f"zip://{(ROOT / 'Results and Shapefiles' / 'tl_2012_01_vtd10.zip').as_posix()}")
    vtd["vtd_geoid"] = vtd.GEOID10.astype(str).str.zfill(11)
    vtd_all = vtd.to_crs(5070)
    vtd = vtd.merge(vtd_votes, on="vtd_geoid", how="inner", validate="one_to_one").to_crs(5070)
    county_source = gpd.read_file(ROOT / "Results and Shapefiles" / "al_gen_22_prec" /
                                  "al_gen_22_st_prec.shp", ignore_geometry=True)
    county_fips = county_source[["County", "COUNTYFP"]].dropna().drop_duplicates("COUNTYFP")
    county_fips["county"] = county_fips.County.map(normalize_name)
    county_fips["county_fips"] = county_fips.COUNTYFP.astype(str).str.zfill(3)
    configs = [("house", "al_sldl_2017_to_2021.zip", "SLDLST"),
               ("senate", "al_sldu_2017_to_2021.zip", "SLDUST")]
    outputs = []
    qa = []
    for chamber, filename, field in configs:
        districts = gpd.read_file(f"zip://{(ROOT / 'Results and Shapefiles' / filename).as_posix()}").to_crs(5070)
        districts["district"] = pd.to_numeric(districts[field]).astype(int)
        inter = gpd.overlay(vtd[["vtd_geoid", "county", "dem_votes", "rep_votes", "geometry"]],
                            districts[["district", "geometry"]], how="intersection",
                            keep_geom_type=False)
        inter["area"] = inter.geometry.area
        inter["covered"] = inter.groupby("vtd_geoid").area.transform("sum")
        inter["weight"] = inter.area / inter.covered
        inter["dem_direct"] = inter.dem_votes * inter.weight
        inter["rep_direct"] = inter.rep_votes * inter.weight
        distribution = inter.groupby(["county", "district"], as_index=False)[
            ["dem_direct", "rep_direct"]].sum()
        distribution["activity"] = distribution.dem_direct + distribution.rep_direct
        distribution["county_activity"] = distribution.groupby("county").activity.transform("sum")
        distribution["fallback_share"] = distribution.activity / distribution.county_activity
        missing_counties = sorted(set(residual.county) - set(distribution.county))
        for county in missing_counties:
            fips_row = county_fips[county_fips.county.eq(county)]
            if fips_row.empty:
                continue
            fips = str(int(float(fips_row.iloc[0].county_fips))).zfill(3)
            county_vtd = vtd_all[vtd_all.COUNTYFP10.astype(str).str.zfill(3).eq(fips)]
            area_inter = gpd.overlay(county_vtd[["geometry"]], districts[["district", "geometry"]],
                                     how="intersection", keep_geom_type=False)
            by_district = area_inter.assign(area=area_inter.geometry.area).groupby(
                "district", as_index=False).area.sum()
            by_district["fallback_share"] = by_district.area / by_district.area.sum()
            by_district["county"] = county
            distribution = pd.concat([distribution, by_district[
                ["county", "district", "fallback_share"]]], ignore_index=True, sort=False)
        fallback = residual.merge(distribution[["county", "district", "fallback_share"]],
                                  on="county", how="inner")
        fallback["dem_fallback"] = fallback.dem_residual * fallback.fallback_share
        fallback["rep_fallback"] = fallback.rep_residual * fallback.fallback_share
        direct_d = inter.groupby("district", as_index=False)[["dem_direct", "rep_direct"]].sum()
        fallback_d = fallback.groupby("district", as_index=False)[["dem_fallback", "rep_fallback"]].sum()
        result = direct_d.merge(fallback_d, on="district", how="outer").fillna(0)
        result["pres_2012_dem_votes"] = result.dem_direct + result.dem_fallback
        result["pres_2012_rep_votes"] = result.rep_direct + result.rep_fallback
        result["pres_2012_two_party_votes"] = result.pres_2012_dem_votes + result.pres_2012_rep_votes
        result["pres_2012_dem_margin"] = 100 * (
            result.pres_2012_dem_votes - result.pres_2012_rep_votes) / result.pres_2012_two_party_votes
        result["pres_2012_fallback_share"] = (
            result.dem_fallback + result.rep_fallback) / result.pres_2012_two_party_votes
        result["pres_2012_source_complete"] = False
        result["chamber"] = chamber
        result["cycle"] = 2018
        outputs.append(result[["cycle", "chamber", "district", "pres_2012_dem_votes",
                               "pres_2012_rep_votes", "pres_2012_two_party_votes",
                               "pres_2012_dem_margin", "pres_2012_fallback_share",
                               "pres_2012_source_complete"]])
        qa.append({"chamber": chamber, "districts": len(result),
                   "dem_allocated": result.pres_2012_dem_votes.sum(),
                   "rep_allocated": result.pres_2012_rep_votes.sum(),
                   "dem_source": vote_qa.dem_votes.sum(), "rep_source": vote_qa.rep_votes.sum()})
    out = pd.concat(outputs, ignore_index=True)
    out.to_csv(PRES / "2018_district_presidential_2012_features.csv", index=False)
    d16 = pd.read_csv(PRES / "2018_district_presidential_2016_features.csv").drop(
        columns=["office"], errors="ignore")
    combined = d16.merge(out, on=["cycle", "chamber", "district"], how="left",
                         validate="one_to_one")
    combined["pres_swing_2012_2016"] = (
        combined.pres_2016_dem_margin - combined.pres_2012_dem_margin)
    combined.to_csv(PRES / "2018_district_presidential_features.csv", index=False)
    pd.DataFrame(qa).to_csv(PRES / "2012_on_2018_spatial_qa.csv", index=False)
    print(pd.DataFrame(qa).to_string(index=False))


if __name__ == "__main__":
    main()
