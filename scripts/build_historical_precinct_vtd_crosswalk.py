"""Build a many-to-many historical precinct-to-VTD crosswalk.

The scalar audit donor remains an evidence anchor. This table additionally permits
one precinct to contain multiple VTDs (underflow) and multiple precincts to share a
VTD (overflow), without changing frozen one-to-one assignments.
"""
from __future__ import annotations

import hashlib
import sqlite3

import geopandas as gpd
import pandas as pd
from rapidfuzz import fuzz
from shapely import make_valid

from audit_historical_precinct_geography import (
    DB, OUT, county_match_key, donor_vtds, legislative_assignments, plans,
)
from warehouse import ROOT

AUDIT = OUT / "historical_precinct_geometry_audit.csv"
CSV_OUT = OUT / "historical_precinct_vtd_links.csv"
COVERAGE_OUT = OUT / "historical_precinct_vtd_link_coverage.csv"
CYCLES = (1994, 1998, 2002, 2006)


def link_id(cycle: int, county: str, precinct: str, donor: str) -> str:
    payload = f"{int(cycle)}|{county}|{precinct}|{donor}".encode()
    return "PVL-" + hashlib.sha256(payload).hexdigest()[:16].upper()


def confidence_for_method(method: str) -> str:
    if method in {"exact_name", "exact_vtd_code_district_constraint",
                  "mobile_senate_house_box_code", "lee_beat_box_code",
                  "morgan_segmented_code", "morgan_compact_segmented_code"}:
        return "high"
    if "one_to_one" in method or "alias" in method or "fuzzy" in method:
        return "medium"
    return "low"


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    audit = pd.read_csv(AUDIT).fillna("")
    audit = audit[~audit.name_match_method.eq("administrative_non_geographic")].copy()
    assignments = pd.concat([legislative_assignments(cycle) for cycle in CYCLES], ignore_index=True)
    assignment_groups = {key: frame for key, frame in assignments.groupby(
        ["cycle", "county_key", "precinct_key"])}
    donors = donor_vtds().to_crs(5070)
    donors["geometry"] = donors.geometry.map(make_valid)
    donors["county_match_key"] = donors.county_key.map(county_match_key)

    district_shapes = {}
    for cycle in CYCLES:
        for chamber, (path, column) in plans(cycle).items():
            source = gpd.read_file(path).to_crs(5070)
            source["geometry"] = source.geometry.map(make_valid)
            source_column = column if column in source else "DISTRICT"
            source["district"] = pd.to_numeric(source[source_column], errors="raise").astype(int)
            district_shapes[(cycle, chamber)] = source.set_index("district").geometry

    allowed_cache = {}
    def allowed_geometry(row):
        key = (int(row.cycle), row.county_key, row.precinct_key)
        if key in allowed_cache:
            return allowed_cache[key]
        group = assignment_groups[key]
        allowed = None
        for chamber, chamber_rows in group.groupby("chamber"):
            lookup = district_shapes[(int(row.cycle), chamber)]
            shape = lookup.loc[sorted(set(chamber_rows.district.astype(int)))].union_all()
            allowed = shape if allowed is None else allowed.intersection(shape)
        allowed_cache[key] = allowed
        return allowed

    rows = []
    for row in audit[audit.donor_vtd_id.ne("")].itertuples(index=False):
        relation = ("one_to_one" if row.vtd_inventory_relation == "one_to_one" else
                    "overflow_member" if row.vtd_inventory_relation == "overflow" else
                    "underflow_primary")
        rows.append({
            "link_id": link_id(row.cycle, row.county_key, row.precinct_key, row.donor_vtd_id),
            "cycle": int(row.cycle), "county_key": row.county_key,
            "precinct_key": row.precinct_key, "donor_vintage": int(row.donor_vintage),
            "donor_vtd_id": row.donor_vtd_id, "donor_name": row.donor_name,
            "relationship": relation, "is_primary": True,
            "vtd_to_precinct_weight": 1.0 if relation != "overflow_member" else pd.NA,
            "evidence_method": row.name_match_method,
            "confidence": confidence_for_method(row.name_match_method),
            "district_overlap_share": pd.NA, "name_score": row.name_match_score,
            "verification_status": "audited_scalar_anchor",
        })

    # Underflow means donor cells outnumber physical precincts. Assign each still-
    # unclaimed VTD to at most one precinct when district geography identifies a
    # unique recipient, or when a strong name match clearly separates candidates.
    underflow = audit[audit.vtd_inventory_relation.eq("underflow")]
    for (cycle, county), group in underflow.groupby(["cycle", "county_key"]):
        vintage = 2010 if int(cycle) >= 2006 else 2000
        pool = donors[(donors.donor_vintage.eq(vintage))
                      & donors.county_match_key.eq(county_match_key(county))]
        claimed = set(group[group.donor_vtd_id.ne("")].donor_vtd_id)
        for donor in pool[~pool.donor_vtd_id.isin(claimed)].itertuples(index=False):
            candidates = []
            for precinct in group.itertuples(index=False):
                allowed = allowed_geometry(precinct)
                share = 0.0 if donor.geometry.area == 0 else donor.geometry.intersection(allowed).area / donor.geometry.area
                if share >= 0.5:
                    candidates.append((precinct, share,
                        float(fuzz.WRatio(str(precinct.precinct_name_norm), str(donor.donor_name_norm)))))
            if not candidates:
                continue
            candidates.sort(key=lambda item: (item[2], item[1]), reverse=True)
            top = candidates[0]; second_score = candidates[1][2] if len(candidates) > 1 else 0.0
            if len(candidates) == 1:
                method, confidence = "underflow_unique_district_recipient", "medium"
            elif top[2] >= 88 and top[2] - second_score >= 8:
                method, confidence = "underflow_district_constrained_name_match", "medium"
            else:
                continue
            precinct, share, score = top
            rows.append({
                "link_id": link_id(cycle, county, precinct.precinct_key, donor.donor_vtd_id),
                "cycle": int(cycle), "county_key": county, "precinct_key": precinct.precinct_key,
                "donor_vintage": int(vintage), "donor_vtd_id": donor.donor_vtd_id,
                "donor_name": donor.donor_name, "relationship": "underflow_additional",
                "is_primary": False, "vtd_to_precinct_weight": 1.0,
                "evidence_method": method, "confidence": confidence,
                "district_overlap_share": share, "name_score": score,
                "verification_status": "inferred_many_to_one_vtd_union",
            })

    links = pd.DataFrame(rows).drop_duplicates("link_id")
    linked_precincts = links[["cycle", "county_key", "precinct_key"]].drop_duplicates()
    coverage = (audit.merge(linked_precincts.assign(has_vtd_link=True),
                            on=["cycle", "county_key", "precinct_key"], how="left")
                .assign(has_vtd_link=lambda frame: frame.has_vtd_link.eq(True))
                .groupby(["cycle", "vtd_inventory_relation", "has_vtd_link"]).size()
                .rename("precincts").reset_index())
    return links, coverage


def main() -> None:
    links, coverage = build()
    links.to_csv(CSV_OUT, index=False)
    coverage.to_csv(COVERAGE_OUT, index=False)
    with sqlite3.connect(DB) as connection:
        links.to_sql("precinct_vtd_links", connection, if_exists="replace", index=False)
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS precinct_vtd_link_id ON precinct_vtd_links(link_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS precinct_vtd_lookup ON precinct_vtd_links(cycle,county_key,precinct_key)")
    print(f"Wrote {len(links):,} precinct-VTD links; "
          f"{(links.relationship == 'underflow_additional').sum():,} are additional underflow unions")
    print(coverage.to_string(index=False))


if __name__ == "__main__":
    main()
