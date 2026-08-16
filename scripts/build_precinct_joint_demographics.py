"""Allocate modeled ACS block-group joint cells into VEST precincts."""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from build_alabama_race_ei import block_race

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "census"
MAPS = ROOT / "data" / "raw" / "alabama_elections_and_geography"
DEMOGRAPHICS = ROOT / "data" / "processed" / "demographics"
POLLING = ROOT / "data" / "processed" / "polling"
CELL_COLUMNS = [f"{race}_{education}" for race in ["white_nh", "black", "other"]
                for education in ["noncollege", "college"]]


def block_precinct_links(cycle: int) -> pd.DataFrame:
    archive = "al_vest_18.zip" if cycle == 2018 else "al_vest_20.zip"
    precincts = gpd.read_file(f"zip://{(MAPS / archive).resolve()}").reset_index(names="precinct_id")
    precincts = precincts[["precinct_id", "geometry"]].to_crs(5070)
    blocks = gpd.read_file(f"zip://{(RAW / 'tl_2020_01_tabblock20.zip').resolve()}")
    blocks = blocks[["GEOID20", "geometry"]].rename(columns={"GEOID20": "blockid"}).to_crs(5070)
    points = blocks.set_geometry(blocks.geometry.representative_point())
    links = gpd.sjoin(points, precincts, how="inner", predicate="within")
    if links.blockid.duplicated().any():
        # Resolve rare topology overlaps by assigning the block to the polygon
        # containing the largest share of its area (two blocks in VEST 2018).
        duplicate = links.blockid.duplicated(False)
        links.loc[duplicate, "overlap_area"] = [
            blocks.loc[index].geometry.intersection(precincts.loc[row.index_right].geometry).area
            for index, row in links[duplicate].iterrows()
        ]
        links = links.sort_values("overlap_area", na_position="last").drop_duplicates("blockid", keep="last")
    return links[["blockid", "precinct_id"]]


def allocate(cells: pd.DataFrame, links: pd.DataFrame, cycle: int, vintage: int) -> pd.DataFrame:
    blocks = block_race(2020)[["blockid", "population"]]
    blocks["block_group_geoid"] = blocks.blockid.str[:12]
    blocks = blocks.merge(links, on="blockid", validate="one_to_one")
    blocks["bg_vap"] = blocks.groupby("block_group_geoid").population.transform("sum")
    blocks["bg_blocks"] = blocks.groupby("block_group_geoid").blockid.transform("size")
    blocks["allocation_weight"] = np.where(
        blocks.bg_vap > 0, blocks.population / blocks.bg_vap, 1 / blocks.bg_blocks
    )
    selected = cells[cells.acs_vintage == vintage][["block_group_geoid", *CELL_COLUMNS]]
    joined = blocks.merge(selected, on="block_group_geoid", validate="many_to_one")
    for column in CELL_COLUMNS:
        joined[column] *= joined.allocation_weight
    result = joined.groupby("precinct_id", as_index=False)[CELL_COLUMNS].sum()
    result["cycle"] = cycle
    result["acs_vintage"] = vintage
    result["adult25_total"] = result[CELL_COLUMNS].sum(axis=1)
    result["method"] = "acs_bg_ipf_cells_allocated_by_2020_block_vap"
    return result


def main() -> None:
    cells = pd.read_csv(DEMOGRAPHICS / "acs_block_group_joint_race_education_modeled.csv",
                        dtype={"block_group_geoid": str})
    outputs = []
    for cycle in [2018, 2020]:
        links = block_precinct_links(cycle)
        for vintage in [2022, 2024]:
            outputs.append(allocate(cells, links, cycle, vintage))
    panel = pd.concat(outputs, ignore_index=True)
    panel.to_csv(POLLING / "vest_precinct_joint_race_education.csv", index=False)
    print(panel.groupby(["cycle", "acs_vintage"]).agg(
        precincts=("precinct_id", "size"), adult25=("adult25_total", "sum"),
        zero_adult_precincts=("adult25_total", lambda x: x.eq(0).sum()),
    ).to_string())


if __name__ == "__main__":
    main()
