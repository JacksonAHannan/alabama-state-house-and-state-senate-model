"""Aggregate VEST presidential returns to the following legislative cycle."""

from pathlib import Path
import sys

import geopandas as gpd
import pandas as pd
from rapidfuzz import fuzz, process

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_2014_precinct_crosswalk import normalize_for_match, normalize_name  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WAR = ROOT / "data" / "processed" / "war"
OUT = ROOT / "data" / "processed" / "presidential"


def county_map() -> dict[str, str]:
    source = gpd.read_file(ROOT / "Results and Shapefiles" / "al_gen_22_prec" /
                           "al_gen_22_st_prec.shp", ignore_geometry=True)
    return (source[["COUNTYFP", "County"]].dropna().drop_duplicates("COUNTYFP")
            .assign(COUNTYFP=lambda x: x.COUNTYFP.astype(str).str.zfill(3))
            .set_index("COUNTYFP").County.map(normalize_name).to_dict())


def build(pres_year: int, target_cycle: int, dem_col: str, rep_col: str) -> pd.DataFrame:
    vest = gpd.read_file(ROOT / "Results and Shapefiles" / f"al_vest_{str(pres_year)[-2:]}" /
                         f"al_vest_{str(pres_year)[-2:]}.shp", ignore_geometry=True)
    cmap = county_map()
    vest["county_norm"] = vest["COUNTYFP20"].astype(str).str.zfill(3).map(cmap)
    vest["precinct"] = vest[f"NAME{str(pres_year)[-2:]}"]
    vest["match_norm"] = vest.precinct.map(normalize_for_match)
    vest["dem_votes"] = pd.to_numeric(vest[dem_col], errors="coerce").fillna(0)
    vest["rep_votes"] = pd.to_numeric(vest[rep_col], errors="coerce").fillna(0)
    vest["source_row_id"] = range(1, len(vest) + 1)

    weights = pd.read_csv(WAR / "precinct_district_allocation_weights.csv")
    weights = weights[weights.cycle.eq(target_cycle)].copy()
    weights["county_norm"] = weights.county_key.map(normalize_name)
    weights["target_norm"] = weights.precinct_key.map(normalize_for_match)
    weights["office"] = weights.chamber.map({"house": "State House", "senate": "State Senate"})
    weights = (weights.groupby(["county_norm", "target_norm", "office", "district"], as_index=False)
               .district_activity.sum())
    weights["target_activity"] = weights.groupby(
        ["county_norm", "target_norm", "office"]).district_activity.transform("sum")
    weights["share"] = weights.district_activity / weights.target_activity.where(weights.target_activity > 0)
    targets = {c: sorted(g.target_norm.dropna().unique()) for c, g in weights.groupby("county_norm")}

    match_rows = []
    for row in vest.itertuples(index=False):
        choices = targets.get(row.county_norm, [])
        target = None; method = "unmatched"; score = margin = 0.0
        if row.match_norm in choices:
            target, method, score, margin = row.match_norm, "exact", 100.0, 100.0
        elif choices and row.match_norm:
            found = process.extract(row.match_norm, choices, scorer=fuzz.WRatio, limit=2)
            score = float(found[0][1]); second = float(found[1][1]) if len(found) > 1 else 0.0
            margin = score - second
            if score >= 92 and margin >= 4:
                target, method = found[0][0], "fuzzy"
        match_rows.append({"source_row_id": row.source_row_id, "target_norm": target,
                           "match_method": method, "match_score": score, "score_margin": margin})
    matches = pd.DataFrame(match_rows)
    keyed = vest.merge(matches, on="source_row_id", validate="one_to_one")
    direct = keyed[keyed.target_norm.notna()].merge(
        weights[["county_norm", "target_norm", "office", "district", "share"]],
        on=["county_norm", "target_norm"], how="inner")
    direct["dem_allocated"] = direct.dem_votes * direct.share
    direct["rep_allocated"] = direct.rep_votes * direct.share
    direct["allocation_method"] = "direct_precinct_activity"

    distributions = (direct.groupby(["county_norm", "office", "district"], as_index=False)
                     [["dem_allocated", "rep_allocated"]].sum())
    distributions["activity"] = distributions.dem_allocated + distributions.rep_allocated
    distributions["county_activity"] = distributions.groupby(
        ["county_norm", "office"]).activity.transform("sum")
    distributions["fallback_share"] = distributions.activity / distributions.county_activity
    expected = keyed.assign(_j=1).merge(
        pd.DataFrame({"office": ["State House", "State Senate"], "_j": [1, 1]}), on="_j").drop(columns="_j")
    direct_keys = direct[["source_row_id", "office"]].drop_duplicates().assign(done=True)
    residual = expected.merge(direct_keys, on=["source_row_id", "office"], how="left")
    residual = residual[residual.done.isna()]
    fallback = residual.merge(distributions[["county_norm", "office", "district", "fallback_share"]],
                              on=["county_norm", "office"], how="inner")
    fallback["dem_allocated"] = fallback.dem_votes * fallback.fallback_share
    fallback["rep_allocated"] = fallback.rep_votes * fallback.fallback_share
    fallback["allocation_method"] = "county_distribution_fallback"
    alloc = pd.concat([direct, fallback], ignore_index=True, sort=False)

    district = (alloc.groupby(["office", "district"], as_index=False)
                .agg(**{f"pres_{pres_year}_dem_votes": ("dem_allocated", "sum"),
                        f"pres_{pres_year}_rep_votes": ("rep_allocated", "sum")}))
    district[f"pres_{pres_year}_two_party_votes"] = (
        district[f"pres_{pres_year}_dem_votes"] + district[f"pres_{pres_year}_rep_votes"])
    district[f"pres_{pres_year}_dem_margin"] = 100 * (
        district[f"pres_{pres_year}_dem_votes"] - district[f"pres_{pres_year}_rep_votes"]) / district[f"pres_{pres_year}_two_party_votes"]
    fallback_d = (alloc.assign(tp=lambda x: x.dem_allocated + x.rep_allocated)
                  .query("allocation_method == 'county_distribution_fallback'")
                  .groupby(["office", "district"], as_index=False).tp.sum())
    district = district.merge(fallback_d, on=["office", "district"], how="left")
    district[f"pres_{pres_year}_fallback_share"] = district.tp.fillna(0) / district[f"pres_{pres_year}_two_party_votes"]
    district = district.drop(columns="tp")
    district["chamber"] = district.office.map({"State House": "house", "State Senate": "senate"})
    district["cycle"] = target_cycle

    matches.to_csv(OUT / f"{pres_year}_to_{target_cycle}_precinct_match.csv", index=False)
    district.to_csv(OUT / f"{target_cycle}_district_presidential_features.csv", index=False)
    print(f"{pres_year}->{target_cycle}: {matches.match_method.value_counts().to_dict()}")
    print(f"districts {len(district)}, D reconciliation "
          f"{district.query("chamber == 'house'")[f'pres_{pres_year}_dem_votes'].sum():.0f}/"
          f"{vest.dem_votes.sum():.0f}")
    return district


def build_spatial(pres_year: int, target_cycle: int, dem_col: str, rep_col: str) -> pd.DataFrame:
    """Allocate VEST precinct votes with normalized polygon intersection area."""
    vest = gpd.read_file(ROOT / "Results and Shapefiles" / f"al_vest_{str(pres_year)[-2:]}" /
                         f"al_vest_{str(pres_year)[-2:]}.shp").to_crs(5070)
    vest = vest.reset_index(drop=True)
    vest["precinct_id"] = range(1, len(vest) + 1)
    vest["dem_votes"] = pd.to_numeric(vest[dem_col], errors="coerce").fillna(0)
    vest["rep_votes"] = pd.to_numeric(vest[rep_col], errors="coerce").fillna(0)
    configs = {
        2018: [("house", "al_sldl_2017_to_2021.zip", "SLDLST"),
               ("senate", "al_sldu_2017_to_2021.zip", "SLDUST")],
        2022: [("house", "al_sldl_2021_to_2023.zip", "DISTRICT"),
               ("senate", "al_sldu_2021_to_2023.zip", "DISTRICT")],
    }
    district_frames = []
    qa_rows = []
    for chamber, filename, field in configs[target_cycle]:
        districts = gpd.read_file(f"zip://{(ROOT / 'Results and Shapefiles' / filename).as_posix()}").to_crs(5070)
        districts["district"] = pd.to_numeric(districts[field], errors="coerce").astype(int)
        intersections = gpd.overlay(
            vest[["precinct_id", "dem_votes", "rep_votes", "geometry"]],
            districts[["district", "geometry"]], how="intersection", keep_geom_type=False)
        intersections["intersection_area"] = intersections.geometry.area
        intersections["covered_area"] = intersections.groupby("precinct_id").intersection_area.transform("sum")
        intersections["weight"] = intersections.intersection_area / intersections.covered_area.where(
            intersections.covered_area > 0)
        intersections["dem_allocated"] = intersections.dem_votes * intersections.weight
        intersections["rep_allocated"] = intersections.rep_votes * intersections.weight
        grouped = (intersections.groupby("district", as_index=False)
                   [["dem_allocated", "rep_allocated"]].sum())
        grouped = grouped.rename(columns={
            "dem_allocated": f"pres_{pres_year}_dem_votes",
            "rep_allocated": f"pres_{pres_year}_rep_votes"})
        grouped[f"pres_{pres_year}_two_party_votes"] = (
            grouped[f"pres_{pres_year}_dem_votes"] + grouped[f"pres_{pres_year}_rep_votes"])
        grouped[f"pres_{pres_year}_dem_margin"] = 100 * (
            grouped[f"pres_{pres_year}_dem_votes"] - grouped[f"pres_{pres_year}_rep_votes"]) / grouped[f"pres_{pres_year}_two_party_votes"]
        grouped[f"pres_{pres_year}_allocation_method"] = "normalized_area_intersection"
        grouped["chamber"] = chamber
        grouped["cycle"] = target_cycle
        district_frames.append(grouped)
        qa_rows.append({
            "pres_year": pres_year, "target_cycle": target_cycle, "chamber": chamber,
            "source_dem_votes": vest.dem_votes.sum(),
            "allocated_dem_votes": intersections.dem_allocated.sum(),
            "source_rep_votes": vest.rep_votes.sum(),
            "allocated_rep_votes": intersections.rep_allocated.sum(),
            "precincts": vest.precinct_id.nunique(),
            "precincts_intersected": intersections.precinct_id.nunique(),
        })
    result = pd.concat(district_frames, ignore_index=True)
    result.to_csv(OUT / f"{target_cycle}_district_presidential_{pres_year}_features.csv", index=False)
    pd.DataFrame(qa_rows).to_csv(OUT / f"{pres_year}_spatial_allocation_qa.csv", index=False)
    print(f"{pres_year}->{target_cycle} spatial: {len(result)} districts")
    print(pd.DataFrame(qa_rows).to_string(index=False))
    return result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    d16_18 = build_spatial(2016, 2018, "G16PREDCLI", "G16PRERTRU")
    d16_18.to_csv(OUT / "2018_district_presidential_features.csv", index=False)
    d16_22 = build_spatial(2016, 2022, "G16PREDCLI", "G16PRERTRU")
    d20_22 = build_spatial(2020, 2022, "G20PREDBID", "G20PRERTRU")
    keys = ["cycle", "chamber", "district"]
    combined = d20_22.merge(d16_22.drop(columns=["office"], errors="ignore"),
                            on=keys, how="left", validate="one_to_one")
    combined["pres_swing_2016_2020"] = (
        combined.pres_2020_dem_margin - combined.pres_2016_dem_margin)
    combined.to_csv(OUT / "2022_district_presidential_features.csv", index=False)


if __name__ == "__main__":
    main()
