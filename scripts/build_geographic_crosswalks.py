"""Build population-weighted precinct-to-legislative-district crosswalks.

2014 uses 2010 Census blocks/VTDs/SLDs. 2018 uses 2020 blocks and the SLD
assignments tabulated with the 2020 Census (2018 session plan). 2022 joins the
2020 VTD block assignments to the Census 2022 SLD block-equivalency files.
Election precinct labels are county-scoped matched to election-specific
precinct polygons. Census block representative points connect those polygons
to official block-level legislative district assignments. This is important in
2022 because the election precinct identifiers are often subdivisions of a
broader Census VTD; joining those identifiers directly incorrectly sent most
precincts to the county fallback. Any genuinely unmatched or county-level
ballot batch receives an independent county population district share, never a
legislative-turnout-derived share.
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
    # Some county workbooks report alphabetic voter-name ranges as separate
    # rows even though both rows share one physical precinct polygon.
    text = re.sub(r"[\s_,.-]+[A-Z]\s*[-–]\s*[A-Z]\s*$", "", text, flags=re.I)
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
    joined = block_district_assignments(cycle, chamber)
    agg = (joined.groupby(["county_fips", "vtd", "district"], as_index=False)
           .agg(population=("population", "sum"), block_count=("block_count", "sum")))
    agg["vtd_population"] = agg.groupby(["county_fips", "vtd"]).population.transform("sum")
    agg["vtd_blocks"] = agg.groupby(["county_fips", "vtd"]).block_count.transform("sum")
    agg["allocation_weight"] = np.where(
        agg.vtd_population.gt(0), agg.population / agg.vtd_population,
        agg.block_count / agg.vtd_blocks)
    agg["chamber"] = chamber
    return agg


def block_district_assignments(cycle: int, chamber: str) -> pd.DataFrame:
    """Return one official legislative assignment and population per block."""
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
    return joined


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


def reference_precinct_geometries(cycle: int):
    """Load the best election-specific precinct geometry available."""
    import geopandas as gpd
    if cycle in (2010, 2014):
        frame = gpd.read_file(f"zip://{(MAPS / 'tl_2012_01_vtd10.zip').resolve()}")
        result = frame[["COUNTYFP10", "VTDST10", "NAME10", "geometry"]].copy()
        result.columns = ["county_fips", "geometry_id", "geometry_name", "geometry"]
    elif cycle == 2018:
        frame = gpd.read_file(f"zip://{(MAPS / 'al_vest_18.zip').resolve()}")
        result = frame[["COUNTYFP20", "VTDST18", "NAME18", "geometry"]].copy()
        result.columns = ["county_fips", "geometry_id", "geometry_name", "geometry"]
    elif cycle == 2022:
        frame = gpd.read_file(MAPS / "al_gen_22_prec" / "al_gen_22_st_prec.shp")
        result = frame[["COUNTYFP", "UNIQUE_ID", "Precinct", "geometry"]].copy()
        result.columns = ["county_fips", "geometry_id", "geometry_name", "geometry"]
    else:
        raise ValueError(f"No precinct geometry configured for cycle {cycle}")
    result["county_fips"] = result.county_fips.astype(str).str.zfill(3)
    result["geometry_id"] = result.geometry_id.astype(str)
    result["match_norm"] = result.geometry_name.map(precinct_norm)
    if result.geometry.isna().any() or result.geometry.is_empty.any():
        raise ValueError(f"{cycle} precinct geometry contains null or empty shapes")
    return result


@lru_cache(maxsize=2)
def block_geometries(year: int):
    """Load Census tabulation blocks needed for spatial precinct membership."""
    import geopandas as gpd
    path = RAW / f"tl_{year}_01_tabblock{str(year)[-2:]}.zip"
    if not path.exists():
        path = RAW / "tabulation_blocks" / path.name
    frame = gpd.read_file(f"zip://{path.resolve()}")
    suffix = str(year)[-2:]
    result = frame[[f"GEOID{suffix}", f"COUNTYFP{suffix}", "geometry"]].copy()
    result.columns = ["blockid", "county_fips", "geometry"]
    result["blockid"] = result.blockid.astype(str)
    result["county_fips"] = result.county_fips.astype(str).str.zfill(3)
    return result


def spatial_precinct_weights(cycle: int, chamber: str) -> pd.DataFrame:
    """Allocate each precinct polygon to districts with Census block population."""
    import geopandas as gpd

    census_year = 2010 if cycle in (2010, 2014) else 2020
    precincts = reference_precinct_geometries(cycle).to_crs(5070)
    blocks = block_geometries(census_year).to_crs(5070)
    # Blocks and election precincts normally share Census edges. A guaranteed
    # interior point avoids double-counting boundary-touching blocks.
    points = blocks[["blockid", "county_fips", "geometry"]].copy()
    points.geometry = points.geometry.representative_point()
    located = gpd.sjoin(
        points,
        precincts[["county_fips", "geometry_id", "geometry_name", "geometry"]],
        how="left",
        predicate="within",
        lsuffix="block",
        rsuffix="precinct",
    )
    # County is included in the spatial join as a QA field; reject the rare
    # cross-county match caused by coincident boundary points.
    located = located[located.county_fips_block.eq(located.county_fips_precinct)].copy()
    located = located.rename(columns={"county_fips_block": "county_fips"})
    if located.blockid.duplicated().any():
        # A handful of source precinct polygons overlap slightly. Resolve only
        # those blocks by greatest polygon intersection rather than arbitrarily
        # accepting the spatial-index order.
        block_shapes = blocks.set_index("blockid").geometry
        precinct_shapes = precincts.geometry
        duplicate = located.blockid.duplicated(False)
        located.loc[~duplicate, "_overlap_area"] = np.inf
        located.loc[duplicate, "_overlap_area"] = located.loc[duplicate].apply(
            lambda row: block_shapes.loc[row.blockid].intersection(
                precinct_shapes.loc[row.index_precinct]
            ).area,
            axis=1,
        )
        located = (located.sort_values("_overlap_area", ascending=False)
                   .drop_duplicates("blockid").drop(columns="_overlap_area"))

    official = block_district_assignments(cycle, chamber)[
        ["blockid", "district", "population", "block_count"]
    ]
    joined = located.merge(official, on="blockid", how="left", validate="one_to_one")
    if joined.district.isna().any() or joined.population.isna().any():
        raise ValueError(f"{cycle} {chamber} spatial blocks lack official assignments")
    grouped = (joined.groupby(
        ["county_fips", "geometry_id", "geometry_name", "district"], as_index=False
    ).agg(population=("population", "sum"), block_count=("block_count", "sum")))
    group_keys = ["county_fips", "geometry_id"]
    grouped["precinct_population"] = grouped.groupby(group_keys).population.transform("sum")
    grouped["precinct_blocks"] = grouped.groupby(group_keys).block_count.transform("sum")
    grouped["allocation_weight"] = np.where(
        grouped.precinct_population.gt(0),
        grouped.population / grouped.precinct_population,
        grouped.block_count / grouped.precinct_blocks,
    )
    return grouped


def county_lookup() -> dict[str, str]:
    import geopandas as gpd
    frame = gpd.read_file(MAPS / "al_gen_22_prec" / "al_gen_22_st_prec.shp",
                          ignore_geometry=True)
    return dict(zip(frame.County.map(normalize_name), frame.COUNTYFP.astype(str).str.zfill(3)))


def match_precincts(target: pd.DataFrame, refs: pd.DataFrame,
                    id_column: str = "vtd") -> pd.DataFrame:
    choices = {county: sorted(group.match_norm.unique())
               for county, group in refs.groupby("county_fips")}
    ref_key = refs.drop_duplicates(["county_fips", "match_norm"]).set_index(
        ["county_fips", "match_norm"])[id_column].to_dict()
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
                     id_column: ref_key.get((row.county_fips, found_name)),
                     "match_method": method, "match_score": score, "score_margin": margin})
    return pd.DataFrame(rows)


def hierarchical_precinct_weights(activity: pd.DataFrame, matches: pd.DataFrame,
                                  spatial: pd.DataFrame,
                                  official_blocks: pd.DataFrame) -> pd.DataFrame:
    """Use reported districts first and geography only for genuine splits."""
    keys = ["cycle", "county_key", "precinct_key"]
    base = activity.merge(matches, on=keys, how="left", validate="many_to_one")
    base["reported_districts"] = base.groupby(keys).district.transform("nunique")
    base["county_batch"] = base.precinct_key.map(is_county_level_ballot)

    spatial_candidates = base[~base.county_batch][
        keys + ["county_fips", "geometry_id"]
    ].drop_duplicates().merge(
        spatial[["county_fips", "geometry_id", "district", "allocation_weight"]],
        on=["county_fips", "geometry_id"], how="inner", validate="many_to_many"
    )
    spatial_counts = spatial_candidates.groupby(keys).district.nunique()
    spatial_split_keys = set(spatial_counts[spatial_counts.gt(1)].index)
    resolved_mask = spatial_candidates[keys].apply(tuple, axis=1).isin(spatial_split_keys)
    resolved = spatial_candidates[resolved_mask].copy()
    resolved["allocation_weight"] = resolved.allocation_weight / resolved.groupby(
        keys).allocation_weight.transform("sum")
    resolved = resolved.merge(
        matches, on=keys + ["county_fips", "geometry_id"], how="left", validate="many_to_one"
    )
    resolved["allocation_method"] = "split_precinct_block_population"

    # A single reported district is conclusive only when the precinct polygon
    # does not cross another district. This protects unopposed districts whose
    # race may be absent from the election results.
    single = base[
        base.reported_districts.eq(1) & ~base.county_batch &
        ~base[keys].apply(tuple, axis=1).isin(spatial_split_keys)
    ].copy()
    single["allocation_weight"] = 1.0
    single["allocation_method"] = "reported_single_district"

    split = base[
        base.reported_districts.gt(1) & ~base.county_batch &
        ~base[keys].apply(tuple, axis=1).isin(spatial_split_keys)
    ].copy()
    unresolved = split.copy()
    unresolved_total = unresolved.groupby(keys).allocation_weight.transform("sum")
    zero_activity = unresolved_total.isna() | unresolved_total.le(0)
    unresolved_valid = unresolved[~zero_activity].copy()
    unresolved_valid["allocation_weight"] = unresolved_valid.allocation_weight / unresolved_valid.groupby(
        keys).allocation_weight.transform("sum")
    unresolved_valid["allocation_method"] = "split_legislative_activity_fallback"
    unresolved_zero = unresolved[zero_activity][keys + ["county_fips", "geometry_id", "vtd",
        "match_method", "match_score", "score_margin"]].drop_duplicates()

    batch = base[base.county_batch][keys + ["county_fips", "geometry_id", "vtd",
        "match_method", "match_score", "score_margin"]].drop_duplicates()
    county = official_blocks.groupby(["county_fips", "district"], as_index=False).population.sum()
    county["allocation_weight"] = county.population / county.groupby(
        "county_fips").population.transform("sum")
    batch = batch.merge(
        county[["county_fips", "district", "allocation_weight"]],
        on="county_fips", how="left", validate="many_to_many"
    )
    batch["allocation_method"] = "county_level_ballot"
    unresolved_zero = unresolved_zero.merge(
        county[["county_fips", "district", "allocation_weight"]],
        on="county_fips", how="left", validate="many_to_many"
    )
    unresolved_zero["allocation_method"] = "split_county_population_fallback"

    unassigned = base[
        base.reported_districts.eq(0) & ~base.county_batch &
        ~base[keys].apply(tuple, axis=1).isin(spatial_split_keys)
    ][
        keys + ["county_fips", "geometry_id", "vtd", "match_method", "match_score", "score_margin"]
    ].drop_duplicates()
    unassigned_spatial = unassigned[unassigned.geometry_id.notna()].merge(
        spatial[["county_fips", "geometry_id", "district", "allocation_weight"]],
        on=["county_fips", "geometry_id"], how="inner", validate="many_to_many"
    )
    unassigned_spatial["allocation_method"] = "spatial_no_reported_district"
    spatial_keys = set(unassigned_spatial[keys].apply(tuple, axis=1))
    unassigned_fallback = unassigned[
        ~unassigned[keys].apply(tuple, axis=1).isin(spatial_keys)
    ].merge(
        county[["county_fips", "district", "allocation_weight"]],
        on="county_fips", how="left", validate="many_to_many"
    )
    unassigned_fallback["allocation_method"] = "county_population_no_reported_district_fallback"

    keep = keys + ["county_fips", "geometry_id", "vtd", "match_method", "match_score",
                   "score_margin", "district", "allocation_weight", "allocation_method"]
    return pd.concat([single[keep], resolved[keep], unresolved_valid[keep],
                      unresolved_zero[keep], unassigned_spatial[keep],
                      unassigned_fallback[keep], batch[keep]],
                     ignore_index=True)


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
        geometry = reference_precinct_geometries(cycle)
        refs = geometry[["county_fips", "geometry_id", "geometry_name", "match_norm"]]
        matches = match_precincts(target[target.cycle.eq(cycle)], refs, "geometry_id")
        matches["vtd"] = matches["geometry_id"]
        match_outputs.append(matches)
        for chamber in ("house", "senate"):
            weights = spatial_precinct_weights(cycle, chamber)
            official_blocks = block_district_assignments(cycle, chamber)
            current_activity = activity[
                activity.cycle.eq(cycle) & activity.chamber.eq(chamber)
            ].copy()
            combined = hierarchical_precinct_weights(
                current_activity, matches, weights, official_blocks
            )
            combined["chamber"] = chamber
            outputs.append(combined)

    result = pd.concat(outputs, ignore_index=True)
    key = ["cycle", "chamber", "county_key", "precinct_key"]
    sums = result.groupby(key).allocation_weight.sum()
    if not np.allclose(sums, 1, atol=1e-9):
        bad = sums[~np.isclose(sums, 1, atol=1e-9)]
        raise ValueError(
            f"Geographic weights do not sum to one; max error {(sums-1).abs().max()}; "
            f"examples {bad.head().to_dict()}"
        )
    result.to_csv(WAR / "geographic_precinct_district_weights.csv", index=False)
    matches = pd.concat(match_outputs, ignore_index=True)
    matches.to_csv(WAR / "geographic_precinct_vtd_matches.csv", index=False)
    qa = (matches.groupby(["cycle", "match_method"], as_index=False).size()
          .rename(columns={"size": "precincts"}))
    qa.to_csv(WAR / "geographic_crosswalk_qa.csv", index=False)
    print(qa.to_string(index=False))


if __name__ == "__main__":
    main()
