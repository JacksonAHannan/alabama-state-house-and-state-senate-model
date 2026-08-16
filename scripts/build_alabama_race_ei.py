"""Estimate Alabama racial vote preference from VTD returns and Census PL data.

This is a race-first ecological-inference prototype. It uses mutually exclusive
non-Hispanic White, non-Hispanic Black, and other population shares and
statewide Governor returns. Race x education is intentionally deferred until
block-group ACS allocation is available.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "census"
ELECTIONS = ROOT / "data" / "processed" / "elections"
OUT = ROOT / "data" / "processed" / "polling"
CYCLES = (2018, 2020)


def read_member(path: Path, suffix: str, sep: str) -> pd.DataFrame:
    with ZipFile(path) as archive:
        member = next(name for name in archive.namelist() if name.endswith(suffix))
        return pd.read_csv(archive.open(member), sep=sep, dtype=str)


def block_race(year: int) -> pd.DataFrame:
    """Read mutually exclusive voting-age race counts from PL segment 2."""
    path = RAW / f"al{year}.pl.zip"
    geo_name, data_name = f"algeo{year}.pl", f"al00002{year}.pl"
    geos: dict[str, str] = {}
    with ZipFile(path) as archive:
        if year == 2010:
            for raw in archive.open(geo_name):
                line = raw.decode("latin1")
                if line[8:11] == "750":
                    geos[line[18:25]] = line[27:29] + line[29:32] + line[54:60] + line[61:65]
        else:
            for raw in archive.open(geo_name):
                fields = raw.decode("utf-8").rstrip().split("|")
                if fields[2] == "750":
                    geos[fields[7]] = fields[9]
        delimiter = "," if year == 2010 else "|"
        rows = []
        for raw in archive.open(data_name):
            fields = raw.decode("utf-8").rstrip().split(delimiter)
            blockid = geos.get(fields[4])
            if blockid:
                total = int(fields[5] or 0)       # P3_001: voting-age population
                white_nh = int(fields[80] or 0)  # P4_005: VAP, not Hispanic, White alone
                black_nh = int(fields[81] or 0)  # P4_006: VAP, not Hispanic, Black alone
                rows.append((blockid, total, white_nh, black_nh, total - white_nh - black_nh))
    result = pd.DataFrame(rows, columns=["blockid", "population", "white_nh", "black_nh", "other"])
    if (result[["white_nh", "black_nh", "other"]] < 0).any().any():
        raise ValueError("PL race categories are not mutually exclusive")
    return result


def vtd_race(census_year: int) -> pd.DataFrame:
    assignment_zip = RAW / ("BlockAssign2010_ST01_AL.zip" if census_year == 2010 else "BlockAssign_ST01_AL.zip")
    sep = "," if census_year == 2010 else "|"
    assignment = read_member(assignment_zip, "_VTD.txt", sep).rename(
        columns={"BLOCKID": "blockid", "COUNTYFP": "county_fips", "DISTRICT": "vtd"}
    )
    race = block_race(census_year)
    joined = assignment[["blockid", "county_fips", "vtd"]].merge(race, on="blockid", validate="one_to_one")
    return joined.groupby(["county_fips", "vtd"], as_index=False)[
        ["population", "white_nh", "black_nh", "other"]
    ].sum()


def governor_returns() -> pd.DataFrame:
    connection = sqlite3.connect(ELECTIONS / "alabama_elections.sqlite")
    query = """
        SELECT year AS cycle, county_key, precinct_key, candidate, party_norm, votes
        FROM vote_observations
        WHERE year IN (2010, 2014, 2018, 2022)
          AND lower(office) = 'governor' AND authority_rank = 1
    """
    votes = pd.read_sql(query, connection)
    connection.close()
    votes.loc[(votes.cycle == 2010) & votes.candidate.str.contains("SPARKS", case=False), "party_norm"] = "D"
    votes.loc[(votes.cycle == 2010) & votes.candidate.str.contains("BENTLEY", case=False), "party_norm"] = "R"
    votes = votes[votes.party_norm.isin(["D", "R"])]
    wide = votes.groupby(["cycle", "county_key", "precinct_key", "party_norm"], as_index=False).votes.sum()
    wide = wide.pivot(index=["cycle", "county_key", "precinct_key"], columns="party_norm", values="votes").fillna(0).reset_index()
    return wide.rename(columns={"D": "dem_votes", "R": "rep_votes"})


def vest_statewide_returns() -> pd.DataFrame:
    """Use VEST's already-geocoded statewide contests for validation cycles."""
    import geopandas as gpd

    specifications = {
        2018: ("al_vest_18.zip", "COUNTYFP20", "VTDST18", "G18GOVDMAD", "G18GOVRIVE"),
        2020: ("al_vest_20.zip", "COUNTYFP20", "VTDST20", "G20PREDBID", "G20PRERTRU"),
    }
    rows = []
    maps = ROOT / "data" / "raw" / "alabama_elections_and_geography"
    for cycle, (archive, county, vtd, dem, rep) in specifications.items():
        frame = gpd.read_file(f"zip://{(maps / archive).resolve()}", ignore_geometry=True)
        part = frame[[county, vtd, dem, rep]].rename(columns={
            county: "county_fips", vtd: "vtd", dem: "dem_votes", rep: "rep_votes",
        })
        part["cycle"] = cycle
        rows.append(part)
    return pd.concat(rows, ignore_index=True)


def vest_precinct_demographics(cycle: int) -> pd.DataFrame:
    """Allocate populated 2020 Census blocks to VEST precinct polygons."""
    import geopandas as gpd

    archive = "al_vest_18.zip" if cycle == 2018 else "al_vest_20.zip"
    maps = ROOT / "data" / "raw" / "alabama_elections_and_geography"
    precincts = gpd.read_file(f"zip://{(maps / archive).resolve()}").reset_index(names="precinct_id")
    precincts = precincts[["precinct_id", "geometry"]].to_crs(5070)
    blocks = gpd.read_file(f"zip://{(RAW / 'tl_2020_01_tabblock20.zip').resolve()}")
    race = block_race(2020)
    blocks = blocks[["GEOID20", "geometry"]].rename(columns={"GEOID20": "blockid"}).merge(
        race, on="blockid", validate="one_to_one"
    )
    blocks = blocks[blocks.population > 0].to_crs(5070)
    block_points = blocks.set_geometry(blocks.geometry.representative_point())
    joined = gpd.sjoin(block_points, precincts, how="inner", predicate="within")
    result = joined.groupby("precinct_id", as_index=False)[
        ["population", "white_nh", "black_nh", "other"]
    ].sum()
    return result


def build_ei_inputs() -> pd.DataFrame:
    votes = vest_statewide_returns()
    outputs = []
    for cycle in CYCLES:
        part_votes = votes[votes.cycle == cycle].reset_index(drop=True).reset_index(names="precinct_id")
        demo = vest_precinct_demographics(cycle)
        part = part_votes.merge(demo, on="precinct_id", validate="one_to_one")
        outputs.append(part)
    return pd.concat(outputs, ignore_index=True)


def estimate_cycle(frame: pd.DataFrame) -> tuple[np.ndarray, bool]:
    groups = ["white_nh", "black_nh", "other"]
    composition = frame[groups].to_numpy(float)
    composition = composition / composition.sum(axis=1, keepdims=True)
    dem = frame.dem_votes.to_numpy(float)
    total = dem + frame.rep_votes.to_numpy(float)

    def objective(parameters: np.ndarray) -> float:
        theta = 1 / (1 + np.exp(-parameters))
        probability = np.clip(composition @ theta, 1e-8, 1 - 1e-8)
        return float(-np.sum(dem * np.log(probability) + (total - dem) * np.log(1 - probability)))

    result = minimize(objective, np.array([-2.0, 3.0, -0.5]), method="L-BFGS-B")
    return 1 / (1 + np.exp(-result.x)), bool(result.success)


def main() -> None:
    inputs = build_ei_inputs()
    inputs.to_csv(OUT / "alabama_vtd_race_ei_inputs.csv", index=False)
    rows = []
    for cycle, frame in inputs.groupby("cycle"):
        estimates, success = estimate_cycle(frame)
        boundary = bool(((estimates < 0.02) | (estimates > 0.98)).any())
        for group, value in zip(["White non-Hispanic", "Black non-Hispanic", "Other"], estimates):
            rows.append({"cycle": cycle, "group": group, "dem_two_party_share": value,
                         "vtds": len(frame), "two_party_votes": frame.dem_votes.sum() + frame.rep_votes.sum(),
                         "optimizer_success": success, "boundary_solution": boundary,
                         "release_eligible": success and not boundary,
                         "status": "failed_boundary_diagnostic" if boundary else "race_only_ecological_prototype"})
    result = pd.DataFrame(rows)
    result.to_csv(OUT / "alabama_race_vote_ei_estimates.csv", index=False)
    coverage = inputs.groupby("cycle").agg(vtds=("vtd", "size"), matched_votes=("dem_votes", "sum"))
    print(result.to_string(index=False))
    print(coverage.to_string())


if __name__ == "__main__":
    main()
