"""Build population-weighted VTD-to-legislative-district crosswalks.

2014 uses 2010 Census blocks/VTDs/SLDs. 2018 uses 2020 blocks and the SLD
assignments tabulated with the 2020 Census (2018 session plan). 2022 joins the
2020 VTD block assignments to the Census 2022 SLD block-equivalency files.
Election precinct labels are county-scoped matched to VEST VTD labels. Any
unmatched or county-level ballot batch receives an independent county population
district share, never a legislative-turnout-derived share.
"""

from __future__ import annotations

from io import TextIOWrapper
from functools import lru_cache
from pathlib import Path
from zipfile import ZipFile
import re

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process

from oe_normalize import is_county_level_ballot, normalize_for_match, normalize_name

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "census"
WAR = ROOT / "data" / "processed" / "war"
MAPS = ROOT / "data" / "raw" / "alabama_elections_and_geography"


def precinct_norm(value: object) -> str:
    text = re.sub(r"^\s*PREC(?:INCT)?\s+\d+(?:/\d+)?\s*[-:]?\s*", "", str(value), flags=re.I)
    return normalize_for_match(text)


@lru_cache(maxsize=2)
def block_population(year: int) -> pd.DataFrame:
    """Read block total population from the official PL 94-171 state file."""
    path = RAW / f"al{year}.pl.zip"
    geo_name, data_name = f"algeo{year}.pl", f"al00001{year}.pl"
    geos: dict[str, str] = {}
    with ZipFile(path) as archive:
        if year == 2010:
            for raw in archive.open(geo_name):
                line = raw.decode("latin1")
                if line[8:11] == "750":
                    geoid = line[27:29] + line[29:32] + line[54:60] + line[61:65]
                    geos[line[18:25]] = geoid
        else:
            for raw in archive.open(geo_name):
                fields = raw.decode("utf-8").rstrip().split("|")
                if fields[2] == "750":
                    geos[fields[7]] = fields[9]
        delimiter = "," if year == 2010 else "|"
        rows = []
        for raw in archive.open(data_name):
            fields = raw.decode("utf-8").rstrip().split(delimiter)
            geoid = geos.get(fields[4])
            if geoid:
                rows.append((geoid, int(fields[5] or 0)))
    result = pd.DataFrame(rows, columns=["blockid", "population"])
    if len(result) != len(geos) or result.blockid.duplicated().any():
        raise ValueError(f"{year} block population join is incomplete or duplicated")
    return result


def read_member(path: Path, suffix: str, sep: str) -> pd.DataFrame:
    with ZipFile(path) as archive:
        member = next(name for name in archive.namelist() if name.endswith(suffix))
        return pd.read_csv(archive.open(member), sep=sep, dtype=str)


def block_assignments(cycle: int, chamber: str) -> pd.DataFrame:
    entity = "SLDL" if chamber == "house" else "SLDU"
    if cycle in (2010, 2014):
        baf = RAW / "BlockAssign2010_ST01_AL.zip"
        vtd = read_member(baf, "_VTD.txt", ",")
        if cycle == 2010:
            sld = read_member(baf, f"_{entity}.txt", ",")
        else:
            post = RAW / ("sldl_post2010.zip" if chamber == "house" else "sldu_post2010.zip")
            sld = read_member(post, f"01_AL_{entity}.txt", ",")
        pop = block_population(2010)
        block_col = "BLOCKID"
    else:
        baf = RAW / "BlockAssign_ST01_AL.zip"
        vtd = read_member(baf, "_VTD.txt", "|")
        if cycle == 2018:
            sld = read_member(baf, f"_{entity}.txt", "|")
            sld = sld.rename(columns={"BLOCKID": "blockid", "DISTRICT": "district"})
        else:
            path = RAW / ("sldl_2022.zip" if chamber == "house" else "sldu_2022.zip")
            suffix = "01_AL_SLDL22.txt" if chamber == "house" else "01_AL_SLDU22.txt"
            sld = read_member(path, suffix, ",")
            sld = sld.rename(columns={"GEOID": "blockid",
                                      "SLDLST" if chamber == "house" else "SLDUST": "district"})
        pop = block_population(2020)
        block_col = "BLOCKID"
    vtd = vtd.rename(columns={block_col: "blockid", "COUNTYFP": "county_fips",
                              "DISTRICT": "vtd"})
    if cycle in (2010, 2014):
        sld = sld.rename(columns={block_col: "blockid", "DISTRICT": "district"})
    joined = vtd[["blockid", "county_fips", "vtd"]].merge(
        sld[["blockid", "district"]], on="blockid", validate="one_to_one").merge(
        pop, on="blockid", validate="one_to_one")
    joined["district"] = pd.to_numeric(joined.district, errors="raise").astype(int)
    joined["block_count"] = 1
    agg = (joined.groupby(["county_fips", "vtd", "district"], as_index=False)
           .agg(population=("population", "sum"), block_count=("block_count", "sum")))
    agg["vtd_population"] = agg.groupby(["county_fips", "vtd"]).population.transform("sum")
    agg["vtd_blocks"] = agg.groupby(["county_fips", "vtd"]).block_count.transform("sum")
    agg["allocation_weight"] = np.where(
        agg.vtd_population.gt(0), agg.population / agg.vtd_population,
        agg.block_count / agg.vtd_blocks)
    agg["chamber"] = chamber
    return agg


def reference_vtds(cycle: int) -> pd.DataFrame:
    import geopandas as gpd
    if cycle in (2010, 2014):
        frame = gpd.read_file(f"zip://{(MAPS / 'tl_2012_01_vtd10.zip').resolve()}",
                              ignore_geometry=True)
        result = frame[["COUNTYFP10", "VTDST10", "NAME10"]].copy()
        result.columns = ["county_fips", "vtd", "vtd_name"]
        result["match_norm"] = result.vtd_name.map(precinct_norm)
        return result
    year = {2014: 16, 2018: 18, 2022: 20}[cycle]
    frame = gpd.read_file(f"zip://{(MAPS / f'al_vest_{year}.zip').resolve()}",
                          ignore_geometry=True)
    result = frame[["COUNTYFP20", f"VTDST{year}", f"NAME{year}"]].copy()
    result.columns = ["county_fips", "vtd", "vtd_name"]
    result["match_norm"] = result.vtd_name.map(precinct_norm)
    return result


def county_lookup() -> dict[str, str]:
    import geopandas as gpd
    frame = gpd.read_file(MAPS / "al_gen_22_prec" / "al_gen_22_st_prec.shp",
                          ignore_geometry=True)
    return dict(zip(frame.County.map(normalize_name), frame.COUNTYFP.astype(str).str.zfill(3)))


def match_precincts(target: pd.DataFrame, refs: pd.DataFrame) -> pd.DataFrame:
    choices = {county: sorted(group.match_norm.unique())
               for county, group in refs.groupby("county_fips")}
    ref_key = refs.drop_duplicates(["county_fips", "match_norm"]).set_index(
        ["county_fips", "match_norm"])["vtd"].to_dict()
    rows = []
    for row in target.itertuples(index=False):
        target_norm = precinct_norm(row.precinct_key)
        found_name = None; method = "unmatched"; score = margin = 0.0
        if is_county_level_ballot(row.precinct_key):
            method = "county_level_ballot"
        elif target_norm in choices.get(row.county_fips, []):
            found_name, method, score, margin = target_norm, "exact", 100.0, 100.0
        elif choices.get(row.county_fips):
            found = process.extract(target_norm, choices[row.county_fips], scorer=fuzz.WRatio, limit=2)
            score = float(found[0][1]); second = float(found[1][1]) if len(found) > 1 else 0
            margin = score - second
            if score >= 90 and margin >= 4:
                found_name, method = found[0][0], "fuzzy"
        rows.append({"cycle": row.cycle, "county_key": row.county_key,
                     "precinct_key": row.precinct_key, "county_fips": row.county_fips,
                     "vtd": ref_key.get((row.county_fips, found_name)),
                     "match_method": method, "match_score": score, "score_margin": margin})
    return pd.DataFrame(rows)


def main() -> None:
    activity = pd.read_csv(WAR / "precinct_district_allocation_weights.csv")
    target = activity[["cycle", "county_key", "precinct_key"]].drop_duplicates()
    county_map = county_lookup()
    county_norm = target.county_key.map(normalize_name).replace({"STCLAIR": "SAINT CLAIR"})
    target["county_fips"] = county_norm.map(county_map)
    if target.county_fips.isna().any():
        raise ValueError(f"Missing county FIPS: {target.loc[target.county_fips.isna(), 'county_key'].unique()}")

    outputs = []; match_outputs = []
    for cycle in (2014, 2018, 2022):
        matches = match_precincts(target[target.cycle.eq(cycle)], reference_vtds(cycle))
        match_outputs.append(matches)
        for chamber in ("house", "senate"):
            weights = block_assignments(cycle, chamber)
            valid_vtd = weights[["county_fips", "vtd"]].drop_duplicates().assign(_valid=True)
            eligible = matches.merge(valid_vtd, on=["county_fips", "vtd"], how="left")
            valid = eligible._valid.eq(True)
            direct = eligible[valid].drop(columns="_valid").merge(
                weights[["county_fips", "vtd", "district", "allocation_weight"]],
                on=["county_fips", "vtd"], how="left", validate="many_to_many")
            direct["allocation_method"] = "vtd_population"
            county = (weights.groupby(["county_fips", "district"], as_index=False)
                      .population.sum())
            county["allocation_weight"] = county.population / county.groupby(
                "county_fips").population.transform("sum")
            fallback = eligible[~valid].drop(columns="_valid").merge(
                county[["county_fips", "district", "allocation_weight"]],
                on="county_fips", how="left", validate="many_to_many")
            fallback["allocation_method"] = "county_population_fallback"
            combined = pd.concat([direct, fallback], ignore_index=True)
            combined["chamber"] = chamber
            outputs.append(combined)

    result = pd.concat(outputs, ignore_index=True)
    key = ["cycle", "chamber", "county_key", "precinct_key"]
    sums = result.groupby(key).allocation_weight.sum()
    if not np.allclose(sums, 1, atol=1e-9):
        raise ValueError(f"Geographic weights do not sum to one; max error {(sums-1).abs().max()}")
    result.to_csv(WAR / "geographic_precinct_district_weights.csv", index=False)
    matches = pd.concat(match_outputs, ignore_index=True)
    matches.to_csv(WAR / "geographic_precinct_vtd_matches.csv", index=False)
    qa = (matches.groupby(["cycle", "match_method"], as_index=False).size()
          .rename(columns={"size": "precincts"}))
    qa.to_csv(WAR / "geographic_crosswalk_qa.csv", index=False)
    print(qa.to_string(index=False))


if __name__ == "__main__":
    main()
