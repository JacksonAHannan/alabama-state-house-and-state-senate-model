"""Allocate Census blocks to historical precincts through audited VTD links."""
from __future__ import annotations

import sqlite3

import geopandas as gpd
import pandas as pd

from audit_historical_precinct_geography import donor_vtds
from warehouse import ROOT

BASE = ROOT / "data/processed/precinct_history"
LINKS = BASE / "historical_precinct_vtd_links.csv"
OUT = BASE / "historical_precinct_block_links.csv.gz"
COVERAGE = BASE / "historical_precinct_block_link_coverage.csv"
BLOCKS = {
    2000: ROOT / "data/raw/census/tabulation_blocks/tl_2010_01_tabblock00.zip",
    2010: ROOT / "data/raw/census/tabulation_blocks/tl_2010_01_tabblock10.zip",
}


def block_points(vintage: int) -> gpd.GeoDataFrame:
    data = gpd.read_file(BLOCKS[vintage]).to_crs(5070)
    geoid = "BLKIDFP00" if vintage == 2000 else "GEOID10"
    county = "COUNTYFP00" if vintage == 2000 else "COUNTYFP10"
    points = gpd.GeoDataFrame({"block_geoid": data[geoid], "county_fips": data[county],
                               "block_area_m2": data.geometry.area,
                               "geometry": data.geometry.representative_point()},
                              geometry="geometry", crs=5070)
    return points


def block_to_donor(vintage: int, donors: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    points = block_points(vintage)
    pool = donors[donors.donor_vintage.eq(vintage)][["donor_vtd_id", "geometry"]]
    joined = gpd.sjoin(points, pool, how="left", predicate="within").drop(columns="index_right")
    return joined


def precinct_polygons(cycle: int) -> gpd.GeoDataFrame:
    path = BASE / f"approximate_{cycle}_house_precincts.gpkg"
    data = gpd.read_file(path).to_crs(5070)
    data = data[data.geometry.map(lambda geometry: geometry is not None and not geometry.is_empty)]
    dissolved = data[["county_key", "precinct_key", "geometry"]].dissolve(
        by=["county_key", "precinct_key"], as_index=False)
    return dissolved


def main() -> None:
    links = pd.read_csv(LINKS).fillna("")
    donors = donor_vtds().to_crs(5070)
    blocks_by_vintage = {vintage: block_to_donor(vintage, donors) for vintage in BLOCKS}
    output = []
    coverage_rows = []
    for cycle in sorted(links.cycle.unique()):
        vintage = 2010 if int(cycle) >= 2006 else 2000
        blocks = blocks_by_vintage[vintage].copy()
        cycle_links = links[links.cycle.eq(cycle)]
        donor_counts = cycle_links.groupby("donor_vtd_id").precinct_key.nunique()
        unique_donors = set(donor_counts[donor_counts.eq(1)].index)
        unique_links = cycle_links[cycle_links.donor_vtd_id.isin(unique_donors)]
        unique_lookup = unique_links.drop_duplicates("donor_vtd_id").set_index("donor_vtd_id")
        direct = blocks[blocks.donor_vtd_id.isin(unique_donors)].copy()
        direct["cycle"] = int(cycle)
        direct["county_key"] = direct.donor_vtd_id.map(unique_lookup.county_key)
        direct["precinct_key"] = direct.donor_vtd_id.map(unique_lookup.precinct_key)
        direct["allocation_method"] = "unique_precinct_vtd_link"
        direct["confidence"] = direct.donor_vtd_id.map(unique_lookup.confidence)
        output.append(direct.drop(columns="geometry"))

        shared_donors = set(donor_counts[donor_counts.gt(1)].index)
        shared_blocks = blocks[blocks.donor_vtd_id.isin(shared_donors)].copy()
        assigned_shared = pd.DataFrame()
        if not shared_blocks.empty:
            polygons = precinct_polygons(int(cycle))
            candidates = gpd.sjoin(shared_blocks, polygons, how="left", predicate="within")
            candidates = candidates.merge(
                cycle_links[["county_key", "precinct_key", "donor_vtd_id", "confidence"]],
                on=["county_key", "precinct_key", "donor_vtd_id"], how="inner")
            counts = candidates.groupby("block_geoid").precinct_key.transform("nunique")
            assigned_shared = candidates[counts.eq(1)].drop_duplicates("block_geoid").copy()
            assigned_shared["cycle"] = int(cycle)
            assigned_shared["allocation_method"] = "shared_vtd_precinct_polygon_partition"
            output.append(assigned_shared[["block_geoid", "county_fips", "block_area_m2",
                                           "donor_vtd_id", "cycle", "county_key", "precinct_key",
                                           "allocation_method", "confidence"]])
        linked = len(direct) + len(assigned_shared)
        relevant = int(blocks.donor_vtd_id.isin(set(cycle_links.donor_vtd_id)).sum())
        coverage_rows.append({"cycle": int(cycle), "donor_linked_blocks": relevant,
                              "precinct_allocated_blocks": linked,
                              "coverage": linked / relevant if relevant else 0.0})

    result = pd.concat(output, ignore_index=True)
    result["block_to_precinct_weight"] = 1.0
    result = result.drop_duplicates(["cycle", "block_geoid"])
    result.to_csv(OUT, index=False, compression="gzip")
    coverage = pd.DataFrame(coverage_rows)
    coverage.to_csv(COVERAGE, index=False)
    with sqlite3.connect(ROOT / "data/processed/elections/alabama_elections.sqlite") as connection:
        result.to_sql("precinct_block_links", connection, if_exists="replace", index=False,
                      chunksize=20000)
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS precinct_block_key ON precinct_block_links(cycle,block_geoid)")
        connection.execute("CREATE INDEX IF NOT EXISTS precinct_block_lookup ON precinct_block_links(cycle,county_key,precinct_key)")
    print(f"Wrote {len(result):,} block allocations to {OUT}")
    print(coverage.to_string(index=False))


if __name__ == "__main__":
    main()
