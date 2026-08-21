"""Audit historical legislative precincts and build approximate election snapshots.

The election ballot establishes the district assignment. A 2010 Census VTD is
used only as a donor shape, then clipped to the district polygon for the cycle.
Outputs never claim that an approximation is an authoritative precinct boundary.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sqlite3
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process
from scipy.optimize import linear_sum_assignment
from shapely import make_valid, voronoi_polygons
from shapely.geometry import MultiPoint, Point

from build_1998_2006_context_features import PLANS as LATER_PLANS
from build_1994_context_features import COUNTY_1994_ALIASES, PLANS as PLAN_1994
from oe_normalize import is_county_level_ballot, normalize_for_match, normalize_name
from warehouse import ROOT

DB = ROOT / "data/processed/elections/alabama_elections.sqlite"
VTD = ROOT / "data/raw/alabama_elections_and_geography/tl_2012_01_vtd10.zip"
VTD2000 = ROOT / "data/raw/census/vtd2000/alabama_vtd2000.geojson"
COUNTY_SOURCE = ROOT / "data/raw/alabama_elections_and_geography/al_gen_22_prec/al_gen_22_st_prec.shp"
DOJ = ROOT / "data/processed/precinct_history/doj_alabama_submission_history.csv"
OUT = ROOT / "data/processed/precinct_history"
ALIAS_RESOLUTIONS = OUT / "adjacent_cycle_precinct_alias_resolutions.csv"
ALIAS_EDGES = OUT / "adjacent_cycle_precinct_alias_edges.csv"
GEOCODE_RESOLUTIONS = OUT / "historical_precinct_geocode_resolutions.csv"
SAME_YEAR_PRIMARY_RESOLUTIONS = OUT / "same_year_primary_alias_resolutions.csv"
MANUAL_ADJUDICATIONS = ROOT / "data/manual/precinct_history/historical_precinct_adjudications.csv"
FROZEN_ONE_TO_ONE = ROOT / "data/manual/precinct_history/frozen_one_to_one_anchors.csv"
CYCLES = (1994, 1998, 2002, 2006)


def canonical_vtd_code(value: object) -> str:
    segments = re.findall(r"\d+", str(value))
    return "-".join(str(int(segment)) for segment in segments) if segments else ""


def decoded_county_vtd_code(county: object, precinct: object,
                            race_assignments: set[tuple[str, int]] | None = None) -> tuple[str, str]:
    """Decode narrow county-specific identifiers; spatial checks still apply."""
    county_key = county_match_key(county)
    text = str(precinct).strip().upper()
    assignments = race_assignments or set()
    if county_key == "MOBILE":
        match = re.fullmatch(r"0*(\d{1,2})-0*(\d{2,3})-0*(\d{1,2})", text)
        if match:
            senate, house, box = map(int, match.groups())
            if not assignments or {("senate", senate), ("house", house)} <= assignments:
                return f"{house}-{box}", "mobile_senate_house_box_code"
    if county_key == "LEE":
        match = re.search(r"(?:\bBEAT\s*)?0*(\d+)\s*[/,]?\s*BOX\s*0*\d+\b", text)
        if match:
            return str(int(match.group(1)) * 10), "lee_beat_box_code"
    if county_key == "MORGAN":
        match = re.fullmatch(r"0*(\d{1,2})-0*(\d{1,3})", text)
        if match:
            return f"{int(match.group(1))}-{int(match.group(2))}", "morgan_segmented_code"
        match = re.fullmatch(r"(\d{1,2})(\d{3})", text)
        if match:
            return f"{int(match.group(1))}-{int(match.group(2))}", "morgan_compact_segmented_code"
    return "", ""


def non_geographic_record(value: object) -> bool:
    text = normalize_for_match(value)
    return bool(is_county_level_ballot(value) or re.search(
        r"\b(?:CALCULATED(?: NUMBER OF)?(?: VOTES)?|COUNTY REPORTING TOTAL|GRAND TOTAL|"
        r"CHALLENGED(?: VOTES)?|PROVISIONAL(?: VOTES)?|REPORTED|WRITE IN)\b", text))


def county_match_key(value: object) -> str:
    normalized = normalize_name(value)
    normalized = COUNTY_1994_ALIASES.get(normalized, normalized)
    normalized = {"STCLAIR": "SAINTCLAIR"}.get(normalized.replace(" ", ""), normalized)
    return normalized.replace(" ", "")


def normalize_split_base(value: object) -> str:
    text = normalize_for_match(value)
    text = re.sub(r"^\d+(?:[-/]\d+)*\s+", "", text)
    text = re.sub(r"\s+(?:BOX|DIST(?:RICT)?)\s*#?\s*[A-Z0-9-]+$", "", text)
    text = re.sub(r"\s+(?:NO|NUMBER|#)\s*\d+$", "", text)
    text = re.sub(r"\s+[. ]?\d+$", "", text)
    text = re.sub(r"\s+[A-Z]-[A-Z](?:\s+DIST)?$", "", text)
    return text.strip()


def plans(cycle: int) -> dict:
    return ({chamber: value for chamber, value in PLAN_1994.items()}
            if cycle == 1994 else LATER_PLANS[cycle])


def legislative_assignments(cycle: int) -> pd.DataFrame:
    if cycle == 1994:
        data = pd.read_csv(ROOT / "data/processed/elections/1994_precinct_district_ballot_weights.csv")
        data = data[data.allocation_weight.gt(0)].copy()
        return data[["cycle", "chamber", "county_key", "precinct_key", "district",
                     "allocation_weight", "allocation_method"]].drop_duplicates()
    with sqlite3.connect(DB) as connection:
        data = pd.read_sql_query("""
          SELECT year AS cycle, county_key, precinct_key, office, district, SUM(votes) AS activity
          FROM vote_observations
          WHERE source='alabama_sos' AND year=?
            AND office IN ('State House','State Senate') AND district IS NOT NULL
          GROUP BY year,county_key,precinct_key,office,district
        """, connection, params=(cycle,))
    data = data[data.activity.gt(0)].copy()
    data["chamber"] = data.office.map({"State House": "house", "State Senate": "senate"})
    data["total"] = data.groupby(["county_key", "precinct_key", "chamber"]).activity.transform("sum")
    data = data[data.total.gt(0)].copy()
    data["allocation_weight"] = data.activity / data.total
    data["allocation_method"] = "official_legislative_ballot_activity"
    return data[["cycle", "chamber", "county_key", "precinct_key", "district",
                 "allocation_weight", "allocation_method"]]


def donor_vtds() -> gpd.GeoDataFrame:
    county_rows = gpd.read_file(COUNTY_SOURCE, ignore_geometry=True)[["COUNTYFP", "County"]].drop_duplicates()
    county_rows["county_key"] = county_rows.County.map(normalize_name)
    current = gpd.read_file(VTD)[["COUNTYFP10", "VTDST10", "NAME10", "geometry"]].rename(
        columns={"COUNTYFP10": "county_fips", "VTDST10": "vtd_code", "NAME10": "donor_name"})
    historical = gpd.read_file(VTD2000)[["COUNTY", "VTD", "BASENAME", "geometry"]].rename(
        columns={"COUNTY": "county_fips", "VTD": "vtd_code", "BASENAME": "donor_name"})
    current["donor_vintage"] = 2010; historical["donor_vintage"] = 2000
    donors = pd.concat([historical.to_crs(current.crs), current], ignore_index=True)
    donors = gpd.GeoDataFrame(donors, geometry="geometry", crs=current.crs)
    donors = donors.merge(county_rows[["COUNTYFP", "county_key"]], left_on="county_fips",
                           right_on="COUNTYFP", validate="many_to_one")
    donors["donor_name_norm"] = donors.donor_name.map(normalize_for_match)
    donors["donor_split_base"] = donors.donor_name.map(normalize_split_base)
    donors["donor_code_norm"] = donors.vtd_code.astype(str).str.replace(r"[^0-9A-Z]", "", regex=True).str.lstrip("0")
    donors["donor_code_canonical"] = donors.vtd_code.map(canonical_vtd_code)
    donors["donor_vtd_id"] = ("VTD" + donors.donor_vintage.astype(str) + "-" +
                              donors.county_fips + "-" + donors.vtd_code.astype(str))
    return donors.drop(columns="COUNTYFP")


def match_donors(assignments: pd.DataFrame, donors: gpd.GeoDataFrame) -> pd.DataFrame:
    identities = assignments[["cycle", "county_key", "precinct_key"]].drop_duplicates().copy()
    identities["precinct_name_norm"] = identities.precinct_key.map(normalize_for_match)
    identities["precinct_split_base"] = identities.precinct_key.map(normalize_split_base)
    donors = donors.copy(); donors["county_match_key"] = donors.county_key.map(county_match_key)
    pools = {key: group.reset_index(drop=True) for key, group in donors.groupby(["donor_vintage", "county_match_key"])}
    donor_projected_frame = donors.to_crs(5070)
    donor_projected_frame["geometry"] = donor_projected_frame.geometry.map(make_valid)
    donor_projected = donor_projected_frame.set_index("donor_vtd_id").geometry
    district_shapes = {}
    for cycle in sorted(assignments.cycle.unique()):
        for chamber, (path, column) in plans(int(cycle)).items():
            source = gpd.read_file(path).to_crs(5070)
            source["geometry"] = source.geometry.map(make_valid)
            source_column = column if column in source else "DISTRICT"
            source["district"] = pd.to_numeric(source[source_column], errors="raise").astype(int)
            district_shapes[(int(cycle), chamber)] = source.set_index("district").geometry
    assignment_groups = {key: group for key, group in assignments.groupby(["cycle", "county_key", "precinct_key"])}
    allowed_geometry_cache = {}
    spatial_share_cache = {}

    def allowed_geometry(row):
        key = (row.cycle, row.county_key, row.precinct_key)
        if key in allowed_geometry_cache:
            return allowed_geometry_cache[key]
        group = assignment_groups[key]
        allowed = None
        for chamber, chamber_rows in group.groupby("chamber"):
            lookup = district_shapes[(int(row.cycle), chamber)]
            chamber_shape = lookup.loc[sorted(set(chamber_rows.district.astype(int)))].union_all()
            allowed = chamber_shape if allowed is None else allowed.intersection(chamber_shape)
        allowed_geometry_cache[key] = allowed
        return allowed

    def donor_spatial_share(row, candidate) -> float:
        key = (row.cycle, row.county_key, row.precinct_key, candidate.donor_vtd_id)
        if key in spatial_share_cache:
            return spatial_share_cache[key]
        allowed = allowed_geometry(row)
        shape = donor_projected[candidate.donor_vtd_id]
        share = 0.0 if shape.is_empty or shape.area == 0 else shape.intersection(allowed).area / shape.area
        spatial_share_cache[key] = share
        return share

    def constrained_choice(row, candidates: pd.DataFrame):
        scored = []
        for candidate in candidates.itertuples(index=False):
            share = donor_spatial_share(row, candidate)
            scored.append((share, candidate))
        scored.sort(key=lambda item: item[0], reverse=True)
        if not scored or scored[0][0] < 0.5:
            return None, 0.0, 0.0
        spatial_margin = scored[0][0] - (scored[1][0] if len(scored) > 1 else 0.0)
        if len(scored) > 1 and spatial_margin < 0.05:
            return None, scored[0][0], spatial_margin
        return scored[0][1], scored[0][0], spatial_margin

    rows = []
    for row in identities.itertuples(index=False):
        donor_vintage = 2010 if row.cycle >= 2006 else 2000
        if non_geographic_record(row.precinct_key):
            rows.append({**row._asdict(), "donor_vintage": donor_vintage,
                         "donor_vtd_id": None, "donor_name": None,
                         "suggested_donor_vtd_id": None, "suggested_donor_name": None,
                         "name_match_method": "administrative_non_geographic", "name_match_score": 0.0,
                         "name_match_margin": 0.0})
            continue
        county_key = county_match_key(row.county_key)
        pool = pools.get((donor_vintage, county_key))
        if pool is None or pool.empty:
            rows.append({**row._asdict(), "donor_vintage": donor_vintage,
                         "donor_vtd_id": None, "donor_name": None,
                         "suggested_donor_vtd_id": None, "suggested_donor_name": None,
                         "name_match_method": "county_unavailable", "name_match_score": 0.0,
                         "name_match_margin": 0.0})
            continue
        assignment_set = {(str(chamber), int(district)) for chamber, district in
                          assignment_groups[(row.cycle, row.county_key, row.precinct_key)][
                              ["chamber", "district"]].itertuples(index=False, name=None)}
        decoded_code, decoder_method = decoded_county_vtd_code(
            row.county_key, row.precinct_key, assignment_set)
        decoded = pool[pool.donor_code_canonical.eq(decoded_code)] if decoded_code else pool.iloc[0:0]
        decoded_hit, decoded_share, decoded_margin = constrained_choice(row, decoded) if len(decoded) else (None, 0.0, 0.0)
        code_match = re.match(r"^\s*([0-9][0-9.\-]*)\s+", str(row.precinct_key))
        code = re.sub(r"[^0-9A-Z]", "", code_match.group(1).upper()).lstrip("0") if code_match else ""
        coded = pool[pool.donor_code_norm.eq(code)] if code else pool.iloc[0:0]
        coded_hit, coded_share, coded_margin = constrained_choice(row, coded) if len(coded) else (None, 0.0, 0.0)
        exact = pool[pool.donor_name_norm.eq(row.precinct_name_norm)]
        split_base = pool[pool.donor_split_base.eq(row.precinct_split_base)] if row.precinct_split_base else pool.iloc[0:0]
        split_hit, split_share, split_margin = constrained_choice(row, split_base) if len(split_base) else (None, 0.0, 0.0)
        suggested = (decoded.iloc[0] if len(decoded) == 1 else coded.iloc[0] if len(coded)
                     else exact.iloc[0] if len(exact) else split_base.iloc[0] if len(split_base) else None)
        if decoded_hit is not None and len(decoded) == 1:
            hit, method, score, margin = decoded_hit, decoder_method, 100.0, decoded_margin * 100
        elif coded_hit is not None:
            hit, method, score, margin = coded_hit, "exact_vtd_code_district_constraint", 100.0, coded_margin * 100
        elif len(exact) == 1:
            hit, method, score, margin = exact.iloc[0], "exact_name", 100.0, 100.0
        elif len(exact) > 1:
            hit, spatial_score, spatial_margin = constrained_choice(row, exact)
            method, score, margin = ("exact_name_district_constraint" if hit is not None
                                      else "ambiguous_exact_name"), 100.0, spatial_margin * 100
        elif split_hit is not None and row.precinct_split_base != row.precinct_name_norm:
            hit, method, score, margin = split_hit, "split_base_district_constraint", 95.0, split_margin * 100
        else:
            choices = pool.donor_name_norm.tolist()
            ranked = process.extract(row.precinct_name_norm, choices, scorer=fuzz.WRatio, limit=5)
            suggested = pool.iloc[ranked[0][2]]
            score = float(ranked[0][1]); second = float(ranked[1][1]) if len(ranked) > 1 else 0.0
            margin = score - second
            candidates = pool.iloc[[item[2] for item in ranked if item[1] >= score - 2]]
            if score >= 85 and (margin < 7 or len(candidates) > 1):
                hit, spatial_score, spatial_margin = constrained_choice(row, candidates)
                accepted = hit is not None
                method = "fuzzy_name_district_constraint" if accepted else "ambiguous_fuzzy_name"
                margin = spatial_margin * 100
            else:
                accepted = score >= 88 and margin >= 7
                hit = pool.iloc[ranked[0][2]] if accepted else None
                method = "fuzzy_name" if accepted else "unmatched_name"
        rows.append({**row._asdict(), "donor_vintage": donor_vintage,
                     "donor_vtd_id": None if hit is None else hit.donor_vtd_id,
                     "donor_name": None if hit is None else hit.donor_name, "name_match_method": method,
                     "suggested_donor_vtd_id": None if suggested is None else suggested.donor_vtd_id,
                     "suggested_donor_name": None if suggested is None else suggested.donor_name,
                     "name_match_score": score, "name_match_margin": margin})
    result = pd.DataFrame(rows)
    # Inventory logic precedes geocoding. When physical precinct and donor-cell
    # counts are equal, donor cells are exclusive and remaining-cell elimination
    # is valid. Only an overflow inventory may reuse and subdivide a donor VTD.
    physical_counts = (result[~result.name_match_method.eq("administrative_non_geographic")]
                       .groupby(["cycle", "county_key"]).size())
    donor_counts = {(cycle, county): len(pools.get(
        (2010 if int(cycle) >= 2006 else 2000, county_match_key(county)), []))
        for cycle, county in result[["cycle", "county_key"]].drop_duplicates().itertuples(index=False)}
    result["physical_precinct_count"] = [physical_counts.get((row.cycle, row.county_key), 0)
                                         for row in result.itertuples(index=False)]
    result["donor_vtd_count"] = [donor_counts.get((row.cycle, row.county_key), 0)
                                  for row in result.itertuples(index=False)]
    result["vtd_inventory_relation"] = np.select([
        result.physical_precinct_count.eq(result.donor_vtd_count),
        result.physical_precinct_count.gt(result.donor_vtd_count)],
        ["one_to_one", "overflow"], default="underflow")
    result["iterative_match_round"] = 0
    result["frozen_one_to_one"] = False
    # Once a complete equal-inventory bijection has been published by this audit,
    # treat it as an immutable anchor in later improvement passes.
    prior_audit = OUT / "historical_precinct_geometry_audit.csv"
    anchor_source = FROZEN_ONE_TO_ONE if FROZEN_ONE_TO_ONE.exists() else prior_audit
    if anchor_source.exists():
        prior = pd.read_csv(anchor_source).fillna("")
        if anchor_source == FROZEN_ONE_TO_ONE:
            prior["vtd_inventory_relation"] = "one_to_one"
            prior["frozen_one_to_one"] = True
        if "vtd_inventory_relation" in prior and "donor_vtd_id" in prior:
            frozen_rows = []
            for _, group in prior[prior.vtd_inventory_relation.eq("one_to_one")].groupby(
                    ["cycle", "county_key"]):
                physical = group[~group.name_match_method.isin(
                    ["administrative_non_geographic", "county_level_ballot"])]
                if (not physical.empty and physical.donor_vtd_id.ne("").all()
                        and physical.donor_vtd_id.nunique() == len(physical)):
                    frozen_rows.append(physical)
            if frozen_rows:
                frozen = pd.concat(frozen_rows).set_index(["cycle", "county_key", "precinct_key"])
                for index, row in result[result.vtd_inventory_relation.eq("one_to_one")].iterrows():
                    key = (int(row.cycle), row.county_key, row.precinct_key)
                    if key not in frozen.index:
                        continue
                    prior_row = frozen.loc[key]
                    if isinstance(prior_row, pd.DataFrame):
                        continue
                    prior_score = pd.to_numeric(pd.Series([prior_row.name_match_score]), errors="coerce").iloc[0]
                    prior_margin = pd.to_numeric(pd.Series([prior_row.name_match_margin]), errors="coerce").iloc[0]
                    result.loc[index, ["donor_vtd_id", "donor_name", "donor_vintage",
                                       "name_match_method", "name_match_score", "name_match_margin",
                                       "frozen_one_to_one"]] = [
                        prior_row.donor_vtd_id, prior_row.donor_name, int(prior_row.donor_vintage),
                        prior_row.name_match_method, prior_score, prior_margin, True]
    if ALIAS_RESOLUTIONS.exists():
        aliases = pd.read_csv(ALIAS_RESOLUTIONS)
        aliases["county_match_key"] = aliases.county_key.map(county_match_key)
        alias_lookup = aliases.set_index(["cycle", "county_match_key", "precinct_key"])
        donor_lookup = donors.set_index("donor_vtd_id")
        for index, row in result[result.donor_vtd_id.isna()].iterrows():
            key = (int(row.cycle), county_match_key(row.county_key), row.precinct_key)
            if key not in alias_lookup.index:
                continue
            alias = alias_lookup.loc[key]
            if isinstance(alias, pd.DataFrame) or alias.donor_vtd_id not in donor_lookup.index:
                continue
            candidate = donors[donors.donor_vtd_id.eq(alias.donor_vtd_id)]
            hit, spatial_share, spatial_margin = constrained_choice(row, candidate)
            if hit is None:
                continue
            result.loc[index, ["donor_vtd_id", "donor_name", "donor_vintage", "name_match_method",
                               "name_match_score", "name_match_margin"]] = [
                hit.donor_vtd_id, hit.donor_name, int(hit.donor_vintage),
                "adjacent_cycle_alias_graph", np.nan, spatial_margin * 100]
    if SAME_YEAR_PRIMARY_RESOLUTIONS.exists():
        primary_aliases = pd.read_csv(SAME_YEAR_PRIMARY_RESOLUTIONS).fillna("")
        primary_lookup = primary_aliases.set_index(["cycle", "county_key", "precinct_key"])
        for index, row in result[result.donor_vtd_id.isna()].iterrows():
            key = (int(row.cycle), row.county_key, row.precinct_key)
            if key not in primary_lookup.index:
                continue
            alias = primary_lookup.loc[key]
            if isinstance(alias, pd.DataFrame):
                continue
            candidate = donors[donors.donor_vtd_id.eq(alias.donor_vtd_id)]
            hit, spatial_share, spatial_margin = constrained_choice(row, candidate)
            if hit is None:
                continue
            result.loc[index, ["donor_vtd_id", "donor_name", "donor_vintage", "name_match_method",
                               "name_match_score", "name_match_margin"]] = [
                hit.donor_vtd_id, hit.donor_name, int(hit.donor_vintage),
                "validated_same_year_primary_position", np.nan, spatial_margin * 100]
    # Equal inventories are a true bijection. Resolve duplicate preliminary matches
    # and remaining cells jointly; district-ballot compatibility is a hard constraint.
    for (cycle, county_key), group in result[result.vtd_inventory_relation.eq("one_to_one")].groupby(
            ["cycle", "county_key"]):
        physical = group[~group.name_match_method.eq("administrative_non_geographic")]
        if physical.frozen_one_to_one.all():
            continue
        donor_vintage = 2010 if int(cycle) >= 2006 else 2000
        pool = pools.get((donor_vintage, county_match_key(county_key)))
        if pool is None or len(physical) != len(pool) or physical.empty:
            continue
        costs = np.full((len(physical), len(pool)), 1_000_000.0)
        physical_rows = list(physical.itertuples())
        donor_rows = list(pool.itertuples(index=False))
        for row_position, row in enumerate(physical_rows):
            for donor_position, candidate in enumerate(donor_rows):
                share = donor_spatial_share(row, candidate)
                if share < 0.5:
                    continue
                name_score = float(fuzz.WRatio(row.precinct_name_norm, candidate.donor_name_norm))
                incumbent_bonus = 35.0 if row.donor_vtd_id == candidate.donor_vtd_id else 0.0
                exact_bonus = 20.0 if row.precinct_name_norm == candidate.donor_name_norm else 0.0
                costs[row_position, donor_position] = 100.0 - name_score - incumbent_bonus - exact_bonus
        row_positions, donor_positions = linear_sum_assignment(costs)
        complete = (len(row_positions) == len(physical)
                    and not any(costs[r, d] >= 1_000_000 for r, d in zip(row_positions, donor_positions)))
        if not complete:
            # Preserve every donor occupied by exactly one preliminary match. Only
            # duplicated and unresolved rows enter a relaxed fragment-aware solve.
            occupied = physical[physical.donor_vtd_id.notna()]
            donor_frequency = occupied.donor_vtd_id.value_counts()
            locked = occupied[occupied.donor_vtd_id.map(donor_frequency).eq(1)]
            free_physical = physical[~physical.index.isin(locked.index)]
            free_pool = pool[~pool.donor_vtd_id.isin(set(locked.donor_vtd_id))]
            if len(free_physical) != len(free_pool) or free_physical.empty:
                continue
            relaxed = np.full((len(free_physical), len(free_pool)), 1_000_000.0)
            physical_rows = list(free_physical.itertuples())
            donor_rows = list(free_pool.itertuples(index=False))
            for row_position, row in enumerate(physical_rows):
                for donor_position, candidate in enumerate(donor_rows):
                    share = donor_spatial_share(row, candidate)
                    if share <= 0:
                        continue
                    name_score = float(fuzz.WRatio(row.precinct_name_norm, candidate.donor_name_norm))
                    incumbent_bonus = 35.0 if row.donor_vtd_id == candidate.donor_vtd_id else 0.0
                    relaxed[row_position, donor_position] = (
                        100.0 - name_score - incumbent_bonus - 20.0 * min(1.0, share))
            row_positions, donor_positions = linear_sum_assignment(relaxed)
            complete = (len(row_positions) == len(free_physical)
                        and not any(relaxed[r, d] >= 1_000_000 for r, d in zip(row_positions, donor_positions)))
            if not complete:
                continue
            costs = relaxed
            assignment_method = "one_to_one_inventory_relaxed_fragment_assignment"
        else:
            assignment_method = "one_to_one_inventory_global_assignment"
        for row_position, donor_position in zip(row_positions, donor_positions):
            row = physical_rows[row_position]; hit = donor_rows[donor_position]
            if row.donor_vtd_id == hit.donor_vtd_id:
                continue
            name_score = float(fuzz.WRatio(row.precinct_name_norm, hit.donor_name_norm))
            result.loc[row.Index, ["donor_vtd_id", "donor_name", "donor_vintage", "name_match_method",
                                   "name_match_score", "name_match_margin"]] = [
                hit.donor_vtd_id, hit.donor_name, int(hit.donor_vintage),
                assignment_method, name_score, np.nan]
    # Monotonic improvement pass. Equal-inventory anchors are never touched.
    # Each round fills only unresolved rows and stops at a fixed point.
    adjacency = {}
    if ALIAS_EDGES.exists():
        edges = pd.read_csv(ALIAS_EDGES)
        for edge in edges.itertuples(index=False):
            old = (int(edge.old_year), county_match_key(edge.county_key), edge.old_precinct)
            new = (int(edge.new_year), county_match_key(edge.county_key), edge.new_precinct)
            adjacency.setdefault(old, set()).add(new)
            adjacency.setdefault(new, set()).add(old)
    result_key_to_index = {(int(row.cycle), county_match_key(row.county_key), row.precinct_key): index
                           for index, row in result.iterrows()}
    for round_number in range(1, 25):
        additions = []
        # First propagate a donor when every resolved adjacent-cycle neighbor agrees.
        for index, row in result[result.donor_vtd_id.isna()
                                 & ~result.vtd_inventory_relation.eq("one_to_one")].iterrows():
            key = (int(row.cycle), county_match_key(row.county_key), row.precinct_key)
            neighbor_donors = set()
            for neighbor in adjacency.get(key, set()):
                neighbor_index = result_key_to_index.get(neighbor)
                if neighbor_index is None:
                    continue
                donor_id = result.at[neighbor_index, "donor_vtd_id"]
                if donor_id and str(donor_id).startswith(f"VTD{int(row.donor_vintage)}-"):
                    neighbor_donors.add(donor_id)
            if len(neighbor_donors) != 1:
                continue
            donor_id = next(iter(neighbor_donors))
            candidate = donors[donors.donor_vtd_id.eq(donor_id)]
            hit, spatial_share, spatial_margin = constrained_choice(row, candidate)
            if hit is not None:
                additions.append((index, hit, "iterative_adjacent_cycle_consensus", np.nan,
                                  spatial_margin * 100))
        # Then use inventory logic. Underflow retains donor exclusivity; overflow
        # permits co-occupancy but only a uniquely compatible cell is inferred.
        for (cycle, county_key), group in result[result.donor_vtd_id.isna()
                                                  & ~result.vtd_inventory_relation.eq("one_to_one")].groupby(
                ["cycle", "county_key"]):
            relation = group.vtd_inventory_relation.iloc[0]
            donor_vintage = 2010 if int(cycle) >= 2006 else 2000
            pool = pools.get((donor_vintage, county_match_key(county_key)))
            if pool is None:
                continue
            all_group = result[result.cycle.eq(cycle) & result.county_key.eq(county_key)]
            available = pool if relation == "overflow" else pool[~pool.donor_vtd_id.isin(
                set(all_group.donor_vtd_id.dropna()))]
            candidate_map = {}
            for index, row in group.iterrows():
                candidates = [candidate for candidate in available.itertuples(index=False)
                              if donor_spatial_share(row, candidate) >= 0.5]
                candidate_map[index] = candidates
            unique_requests = {}
            for candidates in candidate_map.values():
                if len(candidates) == 1:
                    unique_requests[candidates[0].donor_vtd_id] = (
                        unique_requests.get(candidates[0].donor_vtd_id, 0) + 1)
            for index, candidates in candidate_map.items():
                if len(candidates) != 1:
                    continue
                hit = candidates[0]
                if relation == "underflow" and unique_requests[hit.donor_vtd_id] != 1:
                    continue
                additions.append((index, hit, f"iterative_unique_{relation}_district_cell",
                                  float(fuzz.WRatio(result.at[index, "precinct_name_norm"], hit.donor_name_norm)),
                                  np.nan))
        if not additions:
            break
        applied = 0
        for index, hit, method, score, margin in additions:
            if pd.notna(result.at[index, "donor_vtd_id"]):
                continue
            result.loc[index, ["donor_vtd_id", "donor_name", "donor_vintage", "name_match_method",
                               "name_match_score", "name_match_margin", "iterative_match_round"]] = [
                hit.donor_vtd_id, hit.donor_name, int(hit.donor_vintage), method, score, margin,
                round_number]
            applied += 1
        if applied == 0:
            break
    if GEOCODE_RESOLUTIONS.exists():
        geocodes = pd.read_csv(GEOCODE_RESOLUTIONS)
        geocodes["county_match_key"] = geocodes.county_key.map(county_match_key)
        geocode_lookup = geocodes.set_index(["cycle", "county_match_key", "precinct_key"])
        for index, row in result[result.donor_vtd_id.isna()
                                 & result.vtd_inventory_relation.eq("overflow")].iterrows():
            key = (int(row.cycle), county_match_key(row.county_key), row.precinct_key)
            if key not in geocode_lookup.index:
                continue
            location = geocode_lookup.loc[key]
            if isinstance(location, pd.DataFrame): continue
            candidate = donors[donors.donor_vtd_id.eq(location.donor_vtd_id)]
            hit, spatial_share, spatial_margin = constrained_choice(row, candidate)
            if hit is None: continue
            result.loc[index, ["donor_vtd_id", "donor_name", "donor_vintage", "name_match_method",
                               "name_match_score", "name_match_margin"]] = [
                hit.donor_vtd_id, hit.donor_name, int(hit.donor_vintage),
                "named_place_geocode_to_containing_vtd", float(location.geocoder_name_similarity),
                spatial_margin * 100]
    if MANUAL_ADJUDICATIONS.exists():
        decisions = pd.read_csv(MANUAL_ADJUDICATIONS).fillna("")
        decisions = decisions[decisions.decision.eq("accept_donor")]
        decision_lookup = decisions.set_index(["cycle", "county_key", "precinct_key"])
        donor_lookup = donors.set_index("donor_vtd_id")
        for index, row in result[result.donor_vtd_id.isna()].iterrows():
            key = (int(row.cycle), row.county_key, row.precinct_key)
            if key not in decision_lookup.index:
                continue
            decision = decision_lookup.loc[key]
            if isinstance(decision, pd.DataFrame) or decision.donor_vtd_id not in donor_lookup.index:
                continue
            candidate = donors[donors.donor_vtd_id.eq(decision.donor_vtd_id)]
            hit, spatial_share, spatial_margin = constrained_choice(row, candidate)
            if hit is None:
                continue
            result.loc[index, ["donor_vtd_id", "donor_name", "donor_vintage", "name_match_method",
                               "name_match_score", "name_match_margin"]] = [
                hit.donor_vtd_id, hit.donor_name, int(hit.donor_vintage),
                "manual_adjudication", np.nan, spatial_margin * 100]
    # A VTD may contain multiple election precincts. Evaluate every unresolved
    # name independently and never reserve a donor to only one precinct.
    for index, row in result[result.donor_vtd_id.isna()
                             & result.vtd_inventory_relation.eq("overflow")
                             & result.name_match_method.str.contains("unmatched|ambiguous")].iterrows():
        donor_vintage = int(row.donor_vintage)
        county_key = county_match_key(row.county_key)
        pool = pools.get((donor_vintage, county_key))
        if pool is None:
            continue
        candidates = []
        for candidate in pool.itertuples(index=False):
            spatial_share = donor_spatial_share(row, candidate)
            if spatial_share >= 0.8:
                candidates.append((float(fuzz.WRatio(row.precinct_name_norm, candidate.donor_name_norm)), candidate))
        candidates.sort(key=lambda item: item[0], reverse=True)
        if not candidates:
            continue
        top = candidates[0][0]; second = candidates[1][0] if len(candidates) > 1 else 0.0
        if not (len(candidates) == 1 or (top >= 60 and top - second >= 10)):
            continue
        hit = candidates[0][1]
        result.loc[index, ["donor_vtd_id", "donor_name", "name_match_method",
                           "name_match_score", "name_match_margin"]] = [
            hit.donor_vtd_id, hit.donor_name, "district_constrained_nonexclusive_approximation", top, top - second]
    return result


def doj_change_calendar() -> pd.DataFrame:
    data = pd.read_csv(DOJ)
    data["county_key"] = data.county.fillna("").astype(str).str.split("|").str[0].map(county_match_key)
    data["event_date"] = pd.to_datetime(data.first_activity_date, errors="coerce")
    text = (data.descriptions.fillna("") + " " + data.precinct_terms.fillna("")).str.lower()
    data["likely_geometry_change"] = text.str.contains(
        r"boundar|realign|split|division|divide|consolidat|merge|creation|abolish|eliminat",
        regex=True)
    data["polling_place_only"] = (text.str.contains(r"polling place|polling-place", regex=True)
                                   & ~data.likely_geometry_change)
    return data[data.precinct_candidate.eq(1)]


def attach_change_flags(matches: pd.DataFrame, changes: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for row in matches.itertuples(index=False):
        start = pd.Timestamp(f"{row.cycle}-11-01")
        donor_date = pd.Timestamp(f"{row.donor_vintage}-04-01")
        lower, upper = min(start, donor_date), max(start, donor_date)
        county_key = county_match_key(row.county_key)
        pool = changes[(changes.county_key.eq(county_key))
                       & changes.event_date.gt(lower) & changes.event_date.le(upper)]
        geometry = pool[pool.likely_geometry_change]
        rows.append({**row._asdict(), "intervening_doj_candidates": len(pool),
                     "intervening_geometry_candidates": len(geometry),
                     "intervening_submission_numbers": "|".join(sorted(geometry.submission_number.astype(str).unique()))})
    return pd.DataFrame(rows)


def approximate_geometries(assignments: pd.DataFrame, audit: pd.DataFrame,
                           donors: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    joined = assignments.merge(audit.drop(columns=["precinct_name_norm", "precinct_split_base"]),
        on=["cycle", "county_key", "precinct_key"], validate="many_to_one")
    donor_geometry = donors[["donor_vtd_id", "geometry"]].rename(columns={"geometry": "donor_geometry"})
    joined = joined.merge(donor_geometry, on="donor_vtd_id", how="left", validate="many_to_one")
    frames = []
    for (cycle, chamber), group in joined.groupby(["cycle", "chamber"]):
        path, column = plans(int(cycle))[chamber]
        district_source = gpd.read_file(path)
        source_column = column if column in district_source.columns else "DISTRICT"
        districts = district_source[[source_column, "geometry"]].rename(columns={source_column: "district"})
        districts["district"] = pd.to_numeric(districts["district"], errors="raise").astype(int)
        districts = districts.to_crs(5070)
        districts["geometry"] = districts.geometry.map(make_valid)
        part = group.copy()
        geometry_lookup = districts.set_index("district").geometry
        donor_series = gpd.GeoSeries(part.donor_geometry.tolist(), index=part.index, crs=donors.crs).to_crs(5070)
        donor_series = gpd.GeoSeries(
            donor_series.map(lambda geometry: make_valid(geometry) if geometry is not None else None),
            index=part.index, crs=5070)
        district_series = gpd.GeoSeries(part.district.map(geometry_lookup).tolist(), index=part.index, crs=5070)
        part["geometry"] = donor_series.intersection(district_series, align=False)
        geometry_series = gpd.GeoSeries(part["geometry"].tolist(), index=part.index, crs=5070)
        empty_geometry = geometry_series.is_empty | geometry_series.isna()
        part["geometry_method"] = np.where(part.donor_vtd_id.notna(),
            part.donor_vintage.astype(str) + "_vtd_clipped_to_known_legislative_district",
            "unresolved_no_donor_geometry")
        part["geometry_confidence"] = np.select([
            part.donor_vtd_id.isna() | empty_geometry,
            part.intervening_geometry_candidates.gt(0) |
                part.name_match_method.isin(["district_constrained_nonexclusive_approximation",
                                             "named_place_geocode_to_containing_vtd"]),
            part.name_match_method.str.contains("fuzzy") |
                part.name_match_method.eq("adjacent_cycle_alias_graph")],
            ["unresolved", "low", "medium"], default="high")
        part["verification_status"] = "approximate_not_authoritative"
        frames.append(gpd.GeoDataFrame(part.drop(columns=["donor_geometry"]), geometry="geometry", crs=5070))
    return partition_shared_vtds(gpd.GeoDataFrame(pd.concat(frames, ignore_index=True),
                                                   geometry="geometry", crs=5070))


def partition_shared_vtds(data: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    data = data.copy()
    grouping = ["cycle", "chamber", "district", "donor_vtd_id"]
    data["vtd_occupancy_count"] = data.groupby(grouping, dropna=False).precinct_key.transform("nunique")
    data["vtd_partition_method"] = np.where(data.vtd_occupancy_count.gt(1),
                                             "shared_vtd_pending_partition", "single_precinct_vtd")
    data.loc[data.donor_vtd_id.isna(), "vtd_occupancy_count"] = 0
    data.loc[data.donor_vtd_id.isna(), "vtd_partition_method"] = "unresolved_no_donor_vtd"
    geocodes = pd.read_csv(GEOCODE_RESOLUTIONS) if GEOCODE_RESOLUTIONS.exists() else pd.DataFrame()
    geocode_lookup = {}
    if not geocodes.empty:
        points = gpd.GeoDataFrame(geocodes, geometry=gpd.points_from_xy(
            geocodes.longitude, geocodes.latitude), crs=4326).to_crs(5070)
        geocode_lookup = {(int(row.cycle), row.county_key, row.precinct_key): row.geometry
                          for row in points.itertuples(index=False)}

    def synthetic_point(base, identity: str, occupied: list[Point]) -> Point:
        seed = int(hashlib.sha256(identity.encode()).hexdigest()[:16], 16)
        rng = np.random.default_rng(seed); minx, miny, maxx, maxy = base.bounds
        for _ in range(5000):
            point = Point(rng.uniform(minx, maxx), rng.uniform(miny, maxy))
            if base.covers(point) and all(point.distance(other) > 1 for other in occupied):
                return point
        return base.representative_point()

    shared = data[data.donor_vtd_id.notna() & data.vtd_occupancy_count.gt(1)]
    for _, group in shared.groupby(grouping, dropna=False):
        base = make_valid(group.geometry.union_all())
        if base.is_empty or base.area == 0:
            data.loc[group.index, "vtd_partition_method"] = "shared_vtd_no_district_overlap"
            data.loc[group.index, "geometry_confidence"] = "unresolved"
            continue
        precinct_indices = {precinct: indices for precinct, indices in group.groupby("precinct_key").groups.items()}
        seeds, used_geocode = {}, 0
        for precinct, indices in precinct_indices.items():
            first = data.loc[next(iter(indices))]
            point = geocode_lookup.get((int(first.cycle), first.county_key, precinct))
            if (point is not None and base.covers(point) and
                    all(point.distance(other) > 1 for other in seeds.values())):
                seeds[precinct] = point; used_geocode += 1
            else:
                seeds[precinct] = synthetic_point(base, f"{first.cycle}|{first.chamber}|{first.district}|{first.donor_vtd_id}|{precinct}", list(seeds.values()))
        if len(seeds) < 2 or len({point.wkb for point in seeds.values()}) < 2:
            data.loc[group.index, "geometry"] = None
            data.loc[group.index, "vtd_partition_method"] = "shared_vtd_partition_failed"
            data.loc[group.index, "geometry_confidence"] = "unresolved"
            continue
        cells = list(voronoi_polygons(MultiPoint(list(seeds.values())), extend_to=base).geoms)
        names = list(seeds)
        costs = np.array([[cell.distance(seeds[name]) for cell in cells] for name in names])
        seed_positions, cell_positions = linear_sum_assignment(costs)
        assigned = {names[seed_position]: make_valid(cells[cell_position].intersection(base))
                    for seed_position, cell_position in zip(seed_positions, cell_positions)}
        if len(assigned) != len(seeds):
            data.loc[group.index, "geometry"] = None
            data.loc[group.index, "vtd_partition_method"] = "shared_vtd_partition_failed"
            data.loc[group.index, "geometry_confidence"] = "unresolved"
            continue
        method = ("geocoded_voronoi" if used_geocode == len(seeds) else
                  "mixed_geocoded_synthetic_voronoi" if used_geocode else "synthetic_voronoi")
        for precinct, indices in precinct_indices.items():
            for index in indices:
                data.at[index, "geometry"] = assigned[precinct]
                data.at[index, "vtd_partition_method"] = method
                if "synthetic" in method:
                    data.at[index, "geometry_confidence"] = "low"
    return gpd.GeoDataFrame(data, geometry="geometry", crs=5070)


def separate_valid_assignments(assignments: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    valid_by_plan = {}
    for cycle, chamber in assignments[["cycle", "chamber"]].drop_duplicates().itertuples(index=False):
        path, column = plans(int(cycle))[chamber]
        source = gpd.read_file(path, ignore_geometry=True)
        source_column = column if column in source else "DISTRICT"
        valid_by_plan[(int(cycle), chamber)] = set(
            pd.to_numeric(source[source_column], errors="coerce").dropna().astype(int))
    valid_masks = []
    for row in assignments.itertuples(index=False):
        valid = valid_by_plan[(int(row.cycle), row.chamber)]
        valid_masks.append(int(row.district) in valid)
    mask = pd.Series(valid_masks, index=assignments.index)
    invalid = assignments[~mask].copy()
    invalid["audit_issue"] = "district_not_present_in_cycle_plan"
    return assignments[mask].copy(), invalid


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", nargs="*", type=int, default=list(CYCLES))
    parser.add_argument("--skip-geometry", action="store_true",
                        help="Refresh audit/review tables without rebuilding GeoPackages")
    parser.add_argument("--geometry-from-audit", action="store_true",
                        help="Rebuild GeoPackages from the existing audited matches")
    args = parser.parse_args()
    assignments = pd.concat([legislative_assignments(cycle) for cycle in args.cycles], ignore_index=True)
    assignments, invalid_assignments = separate_valid_assignments(assignments)
    donors = donor_vtds()
    if args.geometry_from_audit:
        matches = pd.read_csv(OUT / "historical_precinct_geometry_audit.csv")
        matches = matches[matches.cycle.isin(args.cycles)].copy()
    else:
        matches = attach_change_flags(match_donors(assignments, donors), doj_change_calendar())
        split_context = (assignments.groupby(["cycle", "county_key", "precinct_key", "chamber"])
                         .district.nunique().unstack(fill_value=0).reset_index())
        for chamber in ("house", "senate"):
            if chamber not in split_context: split_context[chamber] = 0
        split_context = split_context.rename(columns={"house": "house_district_count",
                                                       "senate": "senate_district_count"})
        split_context["is_split_precinct"] = (split_context.house_district_count.gt(1) |
                                               split_context.senate_district_count.gt(1))
        matches = matches.merge(split_context, on=["cycle", "county_key", "precinct_key"],
                                how="left", validate="one_to_one")
    OUT.mkdir(parents=True, exist_ok=True)
    matches.to_csv(OUT / "historical_precinct_geometry_audit.csv", index=False)
    district_context = (assignments.assign(label=lambda frame: frame.chamber + "-" + frame.district.astype(int).astype(str))
        .groupby(["cycle", "county_key", "precinct_key"]).label
        .agg(lambda values: "|".join(sorted(set(values)))).reset_index(name="known_race_assignments"))
    review = (matches[matches.donor_vtd_id.isna() & ~matches.name_match_method.eq("administrative_non_geographic")]
              .merge(district_context, on=["cycle", "county_key", "precinct_key"], validate="one_to_one"))
    review.to_csv(OUT / "historical_precinct_geometry_review_queue.csv", index=False)
    invalid_assignments.to_csv(OUT / "historical_precinct_invalid_district_assignments.csv", index=False)
    pd.DataFrame([{"cycle": cycle, "alabama_sos_precinct_results": True,
                   "openelections_same_election_precinct_results": False,
                   "donor_vtd_vintage": 2010 if cycle >= 2006 else 2000,
                   "note": "Local OpenElections Alabama precinct coverage begins in 2012"}
                  for cycle in args.cycles]).to_csv(
        OUT / "historical_precinct_multisource_coverage.csv", index=False)
    if args.skip_geometry:
        print(f"Wrote {len(matches):,} audit rows and {len(review):,} review rows; geometry skipped")
        return
    geometry = approximate_geometries(assignments, matches, donors)
    for (cycle, chamber), layer in geometry.groupby(["cycle", "chamber"]):
        layer = gpd.GeoDataFrame(layer, geometry="geometry", crs=geometry.crs)
        layer.to_file(OUT / f"approximate_{int(cycle)}_{chamber}_precincts.gpkg",
                      layer=f"{int(cycle)}_{chamber}", driver="GPKG")
    summary = (geometry.groupby(["cycle", "chamber", "geometry_confidence"], dropna=False)
               .size().rename("precinct_district_slices").reset_index())
    summary.to_csv(OUT / "historical_precinct_geometry_audit_summary.csv", index=False)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
