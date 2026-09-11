#!/usr/bin/env python3
"""Audit whether Mississippi's corrected 2012 returns can enter strict WAR.

The OpenElections result conversion has names but no precinct identifiers.  The
MARIS 2012 file has identifiers and geometry but no results.  This audit links
the two only within county, supplements the 2012 name with a 2019 VEST/RDH name
when the county/VTD code is unchanged, and enforces a one-to-one assignment.
Unresolved rows are then evaluated against the exact 2019 legislative plan so
that a whole-county result is considered determinate only for a chamber in
which that county belongs to one district.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
import zipfile
from contextlib import closing
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from rapidfuzz import fuzz
from scipy.optimize import linear_sum_assignment

from build_southern_2016_vest_plan_allocation import BLOCK_MANIFEST
from build_southern_historical_plan_allocations import assign_blocks_to_plan, plan_geometry
from warehouse import ROOT, connect, file_sha256


GEOMETRY = ROOT / "data/raw/presidential/southern_war_v4/precinct_geography_2012/MS/precincts_2012.zip"
PLAN_PRECINCTS = ROOT / "data/raw/historical_statewide_elections/ms_gen_19_prec.zip"
PLAN_PRECINCTS_MANIFEST = (
    ROOT / "data/processed/source_audits/mississippi_2019_precinct_alias_manifest.csv"
)
VEST_2016 = ROOT / "data/raw/presidential/southern_war_v4/vest_2016/MS/ms_2016.zip"
OUT = ROOT / "data/processed/presidential/mississippi_2012_precinct_match_audit"

NUMBER_WORDS = {
    "FIRST": "1", "ONE": "1", "SECOND": "2", "TWO": "2", "THIRD": "3", "THREE": "3",
    "FOURTH": "4", "FOUR": "4", "FIFTH": "5", "FIVE": "5", "SIXTH": "6", "SIX": "6",
    "SEVENTH": "7", "SEVEN": "7", "EIGHTH": "8", "EIGHT": "8", "NINTH": "9", "NINE": "9",
    "TENTH": "10", "TEN": "10", "ELEVENTH": "11", "ELEVEN": "11", "TWELFTH": "12",
    "TWELVE": "12", "THIRTEENTH": "13", "THIRTEEN": "13", "FOURTEENTH": "14",
    "FOURTEEN": "14", "FIFTEENTH": "15", "FIFTEEN": "15", "SIXTEENTH": "16",
    "SIXTEEN": "16", "SEVENTEENTH": "17", "SEVENTEEN": "17", "EIGHTEENTH": "18",
    "EIGHTEEN": "18", "NINETEENTH": "19", "NINETEEN": "19", "TWENTIETH": "20",
    "TWENTY": "20",
}
EXPANSIONS = {
    "GWD": "GREENWOOD", "OS": "OCEAN SPRINGS", "CO": "COUNTY", "NAT": "NATIONAL",
    "ASSOC": "ASSOCIATION", "METH": "METHODIST", "LEG": "LEGION", "SUPT": "SUPERINTENDENT",
    "EDUC": "EDUCATION", "CTR": "CENTER", "BLDG": "BUILDING", "SCH": "SCHOOL",
    "HGTS": "HEIGHTS", "COMM": "COMMUNITY", "BAPT": "BAPTIST", "BAP": "BAPTIST",
    "DPT": "DEPARTMENT", "FAM": "FAMILY", "LF": "LIFE", "EPIS": "EPISCOPAL",
    "IND": "INDUSTRIAL", "E": "EAST", "W": "WEST", "N": "NORTH", "S": "SOUTH",
    "MT": "MOUNT",
}


def normalize(value: object, generic: bool = False) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().upper()
    tokens = re.findall(r"[A-Z0-9]+", text.replace("&", " AND "))
    tokens = [NUMBER_WORDS.get(token, EXPANSIONS.get(token, token)) for token in tokens]
    if generic:
        tokens = [token for token in tokens if token not in {"COUNTY", "PRECINCT", "DISTRICT"}]
    return " ".join(tokens)


def code(value: object) -> str:
    value = re.sub(r"[^0-9A-Z]", "", str(value).upper())
    return value.lstrip("0") or "0"


def result_prefix_code(value: object) -> str:
    match = re.match(r"^\s*\(?([0-9]{1,4})\)?(?:\s*[-)]|\s+)", str(value))
    return code(match.group(1)) if match else ""


def result_aliases(value: object) -> tuple[str, ...]:
    text = str(value)
    aliases = {normalize(text), normalize(text, generic=True),
               normalize(text, generic=True).replace(" ", "")}
    prefix = result_prefix_code(text)
    if prefix:
        aliases.add(prefix)
    tail = re.sub(r"^\s*(?:\([0-9]{1,4}\)|[0-9]{1,4})\s*(?:-\s*)?", "", text)
    aliases.update({normalize(tail), normalize(tail, generic=True),
                    normalize(tail, generic=True).replace(" ", "")})
    cleaned = re.sub(r"^\s*DIST(?:RICT)?\.?\s*\d+\s*,?\s*", "", text, flags=re.I)
    cleaned = re.sub(r"\s+BEAT\s+\d+\b", "", cleaned, flags=re.I)
    aliases.update({normalize(cleaned), normalize(cleaned, generic=True),
                    normalize(cleaned, generic=True).replace(" ", "")})
    return tuple(aliases - {""})


def abbreviation_aliases(value: object) -> set[str]:
    tokens = re.findall(r"[A-Z0-9]+", normalize(value))
    aliases: set[str] = set()
    if not tokens:
        return aliases
    if len(tokens) == 1 and tokens[0].isalpha() and len(tokens[0]) >= 2:
        aliases.add(tokens[0][:2])
    words = [token for token in tokens if token not in {"SAINT", "ST"}]
    if len(words) >= 2:
        aliases.add("".join(token[0] for token in words))
    if tokens[-1].isdigit() and tokens[0].isalpha():
        aliases.update({tokens[0][0] + tokens[-1], tokens[0][:2] + tokens[-1]})
    if len(tokens) >= 2 and tokens[0] in {"SAINT", "ST"}:
        aliases.add("ST")
    if normalize(value).replace(" ", "") == "PINEHAVEN":
        aliases.add("PN")
    return aliases


def shapefile(path: Path, suffix: str) -> str:
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(suffix.lower())]
    if len(names) != 1:
        raise ValueError(f"Expected one {suffix} in {path}, found {names}")
    return names[0]


def validate_alias_source() -> dict[str, str]:
    manifest = pd.read_csv(PLAN_PRECINCTS_MANIFEST, dtype=str).fillna("")
    if len(manifest) != 1:
        raise ValueError("Expected exactly one registered Mississippi 2019 alias source")
    row = manifest.iloc[0].to_dict()
    if row["source_file_id"] != "RDH-VEST-2019-MS-PRECINCT":
        raise ValueError("Unexpected Mississippi 2019 alias source ID")
    path = (ROOT / row["local_path"]).resolve()
    if path != PLAN_PRECINCTS.resolve() or not path.exists():
        raise ValueError("Mississippi 2019 alias manifest points to the wrong archive")
    if file_sha256(path) != row["sha256"].lower():
        raise ValueError("Mississippi 2019 alias archive hash does not match its manifest")
    return row


def result_rows(connection) -> pd.DataFrame:
    rows = pd.read_sql_query(
        """SELECT result_observation_id,county_name_original,precinct_name_original,
                  dem_votes,rep_votes,other_votes
           FROM fact_southern_presidential_geography_result
           WHERE state_code='MS' AND cycle=2012
           ORDER BY county_key,precinct_key""",
        connection,
    )
    rows["county_key"] = rows.county_name_original.map(normalize)
    if rows.empty or rows.county_key.nunique() != 82:
        raise ValueError("Expected Mississippi 2012 results for all 82 counties")
    if rows.result_observation_id.duplicated().any():
        raise ValueError("Mississippi result observation IDs are not unique")
    return rows


def donor_rows(results: pd.DataFrame) -> gpd.GeoDataFrame:
    validate_alias_source()
    member = shapefile(GEOMETRY, ".shp")
    donors = gpd.read_file(f"zip://{GEOMETRY.resolve().as_posix()}!{member}")
    donors = donors[
        donors.geometry.notna() & ~donors.geometry.is_empty & donors.COUNTYFP10.notna()
    ].copy()
    donors["county_fips"] = donors.COUNTYFP10.astype(str).str.zfill(3)
    donors["vtd_code"] = donors.VTDST10.map(code)
    duplicate_ordinal = donors.groupby("GEOID10").cumcount() + 1
    duplicate_count = donors.groupby("GEOID10").GEOID10.transform("size")
    donors["donor_id"] = "MSVTD2012-" + donors.GEOID10.astype(str) + np.where(
        duplicate_count.gt(1), "-" + duplicate_ordinal.astype(str), ""
    )
    if donors.donor_id.duplicated().any() or donors.county_fips.nunique() != 82:
        raise ValueError("Unexpected Mississippi 2012 VTD inventory")

    # Mississippi county FIPS codes are the alphabetical odd-number sequence.
    # Validate the complete 82-county inventory before using that deterministic
    # mapping; no partial or guessed county mapping is permitted.
    county_names = sorted(results.county_key.unique())
    county_fips = sorted(donors.county_fips.unique())
    if len(county_names) != len(county_fips) or county_fips != [f"{n:03d}" for n in range(1, 164, 2)]:
        raise ValueError("Mississippi county name/FIPS inventories do not form the complete sequence")
    county_map = dict(zip(county_fips, county_names))
    donors["county_key"] = donors.county_fips.map(county_map)

    aliases: dict[str, set[str]] = {}
    code_aliases: dict[str, set[str]] = {}
    for row in donors.itertuples(index=False):
        native = {
            normalize(row.NAME10), normalize(row.NAME10, generic=True),
            normalize(row.NAME10, generic=True).replace(" ", ""),
        }
        donors.loc[donors.donor_id.eq(row.donor_id), "native_aliases"] = "|".join(sorted(native - {""}))
        aliases[row.donor_id] = native | abbreviation_aliases(row.NAME10)
        code_aliases[row.donor_id] = set()
    layer = shapefile(PLAN_PRECINCTS, "ms_gen_19_sldl_prec.shp")
    current = gpd.read_file(f"zip://{PLAN_PRECINCTS.resolve().as_posix()}!{layer}")
    current["county_fips"] = current.COUNTYFP.astype(str).str.zfill(3)
    current["vtd_code"] = current.VTDST19.map(code)
    for row in current[["county_fips", "vtd_code", "NAME19"]].drop_duplicates().itertuples(index=False):
        donor_ids = donors.loc[
            donors.county_fips.eq(row.county_fips) & donors.vtd_code.eq(row.vtd_code), "donor_id"
        ]
        for donor_id in donor_ids:
            new_aliases = {
                normalize(row.NAME19), normalize(row.NAME19, generic=True),
                normalize(row.NAME19, generic=True).replace(" ", ""),
            } | abbreviation_aliases(row.NAME19)
            aliases[donor_id].update(new_aliases)
            code_aliases[donor_id].update(new_aliases)
    layer_2016 = shapefile(VEST_2016, ".shp")
    current_2016 = gpd.read_file(f"zip://{VEST_2016.resolve().as_posix()}!{layer_2016}")
    current_2016["county_fips"] = current_2016.COUNTYFP16.astype(str).str.zfill(3)
    current_2016["vtd_code"] = current_2016.VTDST16.map(code)
    for row in current_2016[["county_fips", "vtd_code", "NAME16"]].drop_duplicates().itertuples(index=False):
        donor_ids = donors.loc[
            donors.county_fips.eq(row.county_fips) & donors.vtd_code.eq(row.vtd_code), "donor_id"
        ]
        for donor_id in donor_ids:
            new_aliases = {
                normalize(row.NAME16), normalize(row.NAME16, generic=True),
                normalize(row.NAME16, generic=True).replace(" ", ""),
            } | abbreviation_aliases(row.NAME16)
            aliases[donor_id].update(new_aliases)
            code_aliases[donor_id].update(new_aliases)
    # Codes were renumbered in some counties.  Add a later name only when the
    # 2012 and 2016 polygons are mutually at least 90 percent coincident.  This
    # excludes merges and splits while recovering stable renumbered precincts.
    donor_shapes = donors[["donor_id", "county_fips", "geometry"]].to_crs(5070)
    donor_shapes.geometry = donor_shapes.geometry.make_valid()
    donor_shapes["donor_area"] = donor_shapes.geometry.area
    current_shapes = current_2016[["county_fips", "NAME16", "geometry"]].to_crs(5070)
    current_shapes.geometry = current_shapes.geometry.make_valid()
    current_shapes["current_area"] = current_shapes.geometry.area
    pairs = gpd.sjoin(current_shapes, donor_shapes, how="inner", predicate="intersects")
    donor_geometry = donor_shapes.geometry
    pairs["intersection_area"] = [
        row.geometry.intersection(donor_geometry.loc[row.index_right]).area
        for row in pairs.itertuples()
    ]
    pairs["current_share"] = pairs.intersection_area / pairs.current_area
    pairs["donor_share"] = pairs.intersection_area / pairs.donor_area
    stable = pairs[pairs.current_share.ge(0.90) & pairs.donor_share.ge(0.90)]
    for row in stable.itertuples(index=False):
        target_index = donors.index[donors.donor_id.eq(row.donor_id)]
        if len(target_index) != 1:
            raise ValueError("Spatial alias did not identify one 2012 donor")
        aliases[row.donor_id].update({
            normalize(row.NAME16), normalize(row.NAME16, generic=True),
            normalize(row.NAME16, generic=True).replace(" ", ""),
        } | abbreviation_aliases(row.NAME16))

    current_2019 = current[["county_fips", "vtd_code", "NAME19", "geometry"]].dissolve(
        by=["county_fips", "vtd_code", "NAME19"], as_index=False
    ).to_crs(5070)
    current_2019.geometry = current_2019.geometry.make_valid()
    current_2019["current_area"] = current_2019.geometry.area
    pairs_2019 = gpd.sjoin(current_2019, donor_shapes, how="inner", predicate="intersects")
    pairs_2019["intersection_area"] = [
        row.geometry.intersection(donor_geometry.loc[row.index_right]).area
        for row in pairs_2019.itertuples()
    ]
    pairs_2019["current_share"] = pairs_2019.intersection_area / pairs_2019.current_area
    pairs_2019["donor_share"] = pairs_2019.intersection_area / pairs_2019.donor_area
    stable_2019 = pairs_2019[pairs_2019.current_share.ge(0.90) & pairs_2019.donor_share.ge(0.90)]
    for row in stable_2019.itertuples(index=False):
        aliases[row.donor_id].update({
            normalize(row.NAME19), normalize(row.NAME19, generic=True),
            normalize(row.NAME19, generic=True).replace(" ", ""),
        } | abbreviation_aliases(row.NAME19))
    donors["aliases"] = [sorted(a for a in aliases[donor_id] if a) for donor_id in donors.donor_id]
    donors["native_aliases"] = donors.native_aliases.map(lambda value: tuple(str(value).split("|")))
    donors["code_aliases"] = [tuple(sorted(a for a in code_aliases[donor_id] if a))
                              for donor_id in donors.donor_id]
    return donors


def match_results(results: pd.DataFrame, donors: gpd.GeoDataFrame) -> pd.DataFrame:
    records: list[dict] = []
    for county, source in results.groupby("county_key", sort=True):
        target = donors[donors.county_key.eq(county)].reset_index(drop=True)
        source = source.reset_index(drop=True)
        matrix = np.zeros((len(source), len(target)), dtype=float)
        source_aliases = [result_aliases(value) for value in source.precinct_name_original]
        for i, names in enumerate(source_aliases):
            for j, aliases in enumerate(target.aliases):
                matrix[i, j] = max(fuzz.WRatio(left, right) for left in names for right in aliases)
                if any(left == right for left in names for right in target.iloc[j].native_aliases):
                    matrix[i, j] = 120.0
                elif any(left == right for left in names for right in target.iloc[j].code_aliases):
                    matrix[i, j] = 118.0
                prefix = result_prefix_code(source.iloc[i].precinct_name_original)
                if prefix and prefix == target.iloc[j].vtd_code and matrix[i, j] < 115.0:
                    matrix[i, j] = 115.0
        source_indexes, target_indexes = linear_sum_assignment(-matrix)
        assigned = dict(zip(source_indexes, target_indexes))
        for i, row in source.iterrows():
            j = assigned.get(i)
            score = float(matrix[i, j]) if j is not None else 0.0
            row_scores = np.sort(matrix[i])[::-1]
            row_margin = score - (float(row_scores[1]) if len(row_scores) > 1 else 0.0)
            column_scores = np.sort(matrix[:, j])[::-1] if j is not None else np.array([])
            column_margin = score - (float(column_scores[1]) if len(column_scores) > 1 else 0.0)
            native_exact = bool(j is not None and score > 119.0)
            same_code_exact = bool(j is not None and 115.0 < score < 120.0)
            code_exact = bool(j is not None and 110.0 < score <= 115.0)
            exact = bool(j is not None and any(left == right for left in source_aliases[i]
                                                for right in target.iloc[j].aliases))
            accepted = bool(j is not None and (native_exact or same_code_exact or code_exact or exact or
                (score >= 88.0 and row_margin >= 4.0)))
            candidate = target.iloc[j] if j is not None else None
            if j is None or score < 85.0:
                plausible = target
            else:
                plausible = target[matrix[i] >= max(85.0, score - 4.0)]
            records.append({
                **row.to_dict(),
                "donor_id": candidate.donor_id if accepted else None,
                "donor_name": candidate.NAME10 if accepted else None,
                "suggested_donor_id": candidate.donor_id if candidate is not None else None,
                "suggested_donor_name": candidate.NAME10 if candidate is not None else None,
                "match_method": "exact_2012_geometry_name" if native_exact else
                                "exact_later_name_same_vtd_code" if same_code_exact else
                                "exact_ballot_vtd_code" if code_exact else
                                "exact_alias_one_to_one" if exact else
                                "fuzzy_alias_one_to_one" if accepted else "unresolved",
                "match_score": score,
                "row_score_margin": row_margin,
                "column_score_margin": column_margin,
                "plausible_donor_ids_json": json.dumps(sorted(plausible.donor_id.tolist())),
                "plausible_donor_names_json": json.dumps(sorted(plausible.NAME10.astype(str).tolist())),
                "two_party_votes": float(row.dem_votes + row.rep_votes),
            })
    matches = pd.DataFrame(records)
    accepted = matches[matches.donor_id.notna()]
    if accepted.donor_id.duplicated().any():
        raise ValueError("Accepted donor match is not one-to-one")
    return matches


def district_exposure(connection, matches: pd.DataFrame, donors: gpd.GeoDataFrame) -> pd.DataFrame:
    manifest = pd.read_csv(BLOCK_MANIFEST, dtype=str).fillna("").set_index("state_code")
    block_path = (ROOT / manifest.loc["MS"].local_path).resolve()
    blocks = gpd.read_file(f"zip://{block_path.as_posix()}", columns=["GEOID20", "geometry"])
    blocks["GEOID20"] = blocks.GEOID20.astype(str).str.zfill(15)
    blocks["county_fips"] = blocks.GEOID20.str[2:5]
    blocks["VAP_MOD"] = 1.0
    blocks = blocks.to_crs(5070)
    donor_shapes = donors[["donor_id", "county_fips", "county_key", "geometry"]].to_crs(5070)
    donor_shapes.geometry = donor_shapes.geometry.make_valid()
    county_map = donor_shapes[["county_fips", "county_key"]].drop_duplicates()
    if county_map.county_fips.duplicated().any():
        raise ValueError("County FIPS does not map to one county key")
    blocks = blocks.merge(county_map, on="county_fips", validate="many_to_one")
    unresolved = matches[matches.donor_id.isna()].copy()
    contested = pd.read_sql_query(
        """SELECT chamber,district FROM mart_southern_war_training_no_finance
           WHERE state_code='MS' AND cycle=2019
             AND training_status='strict_war_ready_no_finance'""", connection,
    ).drop_duplicates()
    cells = pd.read_sql_query(
        """SELECT chamber,geography_layer_id FROM source_southern_spatial_plan_assignment
           WHERE state_code='MS' AND plan_cycle=2019 ORDER BY chamber""", connection,
    )
    output = []
    for cell in cells.itertuples(index=False):
        plans = plan_geometry(connection, cell.geography_layer_id)
        plan_match, _ = assign_blocks_to_plan(blocks, plans)
        assignments = plan_match.merge(
            blocks[["GEOID20", "county_fips", "county_key"]],
            left_on="block_index", right_index=True, validate="one_to_one",
        )
        points = gpd.GeoDataFrame(
            assignments[["block_index", "district", "county_fips", "county_key"]],
            geometry=blocks.loc[assignments.block_index].geometry.representative_point().values,
            crs=blocks.crs,
        )
        donor_assignment = gpd.sjoin(points, donor_shapes, how="inner", predicate="within")
        donor_districts = donor_assignment.groupby("donor_id").district.agg(
            lambda values: sorted(set(values), key=lambda x: int(x)))
        for row in unresolved.itertuples(index=False):
            candidate_ids = json.loads(row.plausible_donor_ids_json)
            districts = sorted({district for donor_id in candidate_ids
                                for district in donor_districts.get(donor_id, [])}, key=lambda x: int(x))
            if len(districts) == 1:
                status = "exact_single_district_plausible_set"
            else:
                status = "ambiguous_plausible_set"
            for district in districts:
                output.append({
                    "chamber": cell.chamber, "district": str(district), "county_key": row.county_key,
                    "result_observation_id": row.result_observation_id,
                    "precinct_name_original": row.precinct_name_original,
                    "unresolved_rows": 1, "unresolved_two_party_votes": float(row.two_party_votes),
                    "plausible_district_count": len(districts), "allocation_status": status,
                })
    exposure = pd.DataFrame(output)
    exposure = exposure.merge(contested.assign(contested_race=True), on=["chamber", "district"],
                              how="left", validate="many_to_one")
    exposure["contested_race"] = exposure["contested_race"].eq(True)
    return exposure.sort_values(["chamber", "district", "county_key"])


def build(database: Path | None = None) -> dict:
    with closing(connect(database, readonly=True)) as connection:
        results = result_rows(connection)
        donors = donor_rows(results)
        matches = match_results(results, donors)
        exposure = district_exposure(connection, matches, donors)
    OUT.mkdir(parents=True, exist_ok=True)
    matches.drop(columns="county_name_original").to_csv(OUT / "precinct_matches.csv", index=False)
    exposure.to_csv(OUT / "unresolved_district_exposure.csv", index=False)
    unresolved = matches[matches.donor_id.isna()]
    ambiguous = exposure[exposure.allocation_status.eq("ambiguous_plausible_set")]
    summary = {
        "result_rows": len(matches),
        "matched_rows": int(matches.donor_id.notna().sum()),
        "matched_two_party_votes": float(matches.loc[matches.donor_id.notna(), "two_party_votes"].sum()),
        "source_two_party_votes": float(matches.two_party_votes.sum()),
        "unresolved_rows": len(unresolved),
        "unresolved_two_party_votes": float(unresolved.two_party_votes.sum()),
        "contested_cells_with_ambiguous_exposure": int(
            ambiguous.loc[ambiguous.contested_race, ["chamber", "district"]].drop_duplicates().shape[0]),
    }
    print(pd.Series(summary).to_json(indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path)
    args = parser.parse_args()
    build(args.database)


if __name__ == "__main__":
    main()
