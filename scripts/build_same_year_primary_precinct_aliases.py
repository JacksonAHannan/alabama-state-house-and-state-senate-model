"""Extract primary precinct names and validate same-year positional aliases."""
from __future__ import annotations

import io
import re
import sqlite3
import zipfile

import pandas as pd
from rapidfuzz import fuzz, process

from audit_historical_precinct_geography import (
    DB, OUT, county_match_key, donor_vtds, non_geographic_record,
)
from oe_normalize import normalize_for_match
from warehouse import ROOT

RAW = ROOT / "data/raw/alabama_elections_and_geography/historical_primaries"
NAMES_OUT = OUT / "same_year_primary_precinct_names.csv"
VALIDATION_OUT = OUT / "same_year_primary_positional_validation.csv"
RESOLUTIONS_OUT = OUT / "same_year_primary_alias_resolutions.csv"


def clean_names(values) -> list[str]:
    result = []
    for value in values:
        if pd.isna(value):
            continue
        text = str(value).strip()
        if not text or re.search(r"(?i)\b(?:total|precinct)\b", text):
            continue
        if non_geographic_record(text):
            continue
        result.append(text)
    return list(dict.fromkeys(result))


def extract_1998(path) -> list[dict]:
    rows = []
    with zipfile.ZipFile(path) as archive:
        for member in archive.namelist():
            if not member.lower().endswith(".xls"):
                continue
            county = member.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            payload = archive.read(member)
            candidates = []
            for sheet in pd.ExcelFile(io.BytesIO(payload)).sheet_names:
                data = pd.read_excel(io.BytesIO(payload), sheet_name=sheet, header=None)
                first = data.iloc[:, 0].astype(str)
                starts = first[first.str.fullmatch("Precinct", case=False, na=False)].index
                if len(starts):
                    candidates.append(clean_names(data.iloc[starts[0] + 1:, 0]))
            if not candidates:
                continue
            names = max(candidates, key=len)
            rows.extend({"year": 1998, "election": "primary", "county_key": county_match_key(county),
                         "primary_order": order, "primary_precinct_name": name}
                        for order, name in enumerate(names, 1))
    return rows


def extract_2002(path, election: str) -> list[dict]:
    rows = []
    with zipfile.ZipFile(path) as archive:
        for member in archive.namelist():
            if not member.lower().endswith(".xls"):
                continue
            county = member.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            payload = archive.read(member)
            data = pd.read_excel(io.BytesIO(payload), sheet_name=0)
            names = clean_names(list(data.columns[4:]))
            rows.extend({"year": 2002, "election": election, "county_key": county_match_key(county),
                         "primary_order": order, "primary_precinct_name": name}
                        for order, name in enumerate(names, 1))
    return rows


def donor_match(names: pd.DataFrame) -> pd.DataFrame:
    donors = donor_vtds()
    donors = donors[donors.donor_vintage.eq(2000)].copy()
    donors["county_match_key"] = donors.county_key.map(county_match_key)
    donors["normalized"] = donors.donor_name.map(normalize_for_match)
    output = []
    for row in names.itertuples(index=False):
        pool = donors[donors.county_match_key.eq(row.county_key)]
        ranked = process.extract(normalize_for_match(row.primary_precinct_name),
                                 pool.normalized.tolist(), scorer=fuzz.WRatio, limit=2)
        if not ranked:
            output.append({**row._asdict(), "primary_donor_vtd_id": "", "primary_donor_name": "",
                           "primary_donor_score": 0.0, "primary_donor_margin": 0.0})
            continue
        top = pool.iloc[ranked[0][2]]; second = ranked[1][1] if len(ranked) > 1 else 0.0
        accepted = ranked[0][1] >= 88 and ranked[0][1] - second >= 7
        output.append({**row._asdict(),
                       "primary_donor_vtd_id": top.donor_vtd_id if accepted else "",
                       "primary_donor_name": top.donor_name if accepted else "",
                       "primary_donor_score": float(ranked[0][1]),
                       "primary_donor_margin": float(ranked[0][1] - second)})
    return pd.DataFrame(output)


def main() -> None:
    rows = extract_1998(RAW / "1998_primary.zip")
    rows += extract_2002(RAW / "2002_primary.exe", "primary")
    rows += extract_2002(RAW / "2002_primary_runoff.exe", "primary_runoff")
    names = donor_match(pd.DataFrame(rows))
    names.to_csv(NAMES_OUT, index=False)

    audit = pd.read_csv(OUT / "historical_precinct_geometry_audit.csv").fillna("")
    audit = audit[~audit.name_match_method.eq("administrative_non_geographic")]
    with sqlite3.connect(DB) as connection:
        order = pd.read_sql_query("""
          SELECT year,county_key,precinct_key,MIN(rowid) AS source_order
          FROM vote_observations WHERE source='alabama_sos' AND year IN (1998,2002)
          GROUP BY year,county_key,precinct_key
        """, connection)
    audit = audit.merge(order, left_on=["cycle", "county_key", "precinct_key"],
                        right_on=["year", "county_key", "precinct_key"], how="left")
    audit["general_order"] = audit.groupby(["cycle", "county_key"]).source_order.rank(
        method="first").astype("Int64")

    validation, resolutions = [], []
    primary = names[names.election.eq("primary")]
    for (year, county), general in audit[audit.cycle.isin([1998, 2002])].groupby(["cycle", "county_key"]):
        source = primary[(primary.year.eq(year)) & primary.county_key.eq(county)]
        if len(source) != len(general) or source.empty:
            validation.append({"year": year, "county_key": county, "general_count": len(general),
                               "primary_count": len(source), "validated_anchors": 0,
                               "anchor_accuracy": 0.0, "accepted": False})
            continue
        paired = general.merge(source, left_on="general_order", right_on="primary_order",
                               suffixes=("_general", "_primary"), validate="one_to_one")
        anchors = paired[(paired.donor_vtd_id.ne("")) & (paired.primary_donor_vtd_id.ne(""))]
        accuracy = (anchors.donor_vtd_id == anchors.primary_donor_vtd_id).mean() if len(anchors) else 0.0
        accepted = len(anchors) >= 5 and accuracy >= 0.95
        validation.append({"year": year, "county_key": county, "general_count": len(general),
                           "primary_count": len(source), "validated_anchors": len(anchors),
                           "anchor_accuracy": accuracy, "accepted": accepted})
        if not accepted:
            continue
        for row in paired[(paired.donor_vtd_id.eq("")) & paired.primary_donor_vtd_id.ne("")].itertuples(index=False):
            resolutions.append({"cycle": int(year), "county_key": county,
                                "precinct_key": row.precinct_key,
                                "primary_precinct_name": row.primary_precinct_name,
                                "donor_vtd_id": row.primary_donor_vtd_id,
                                "donor_name": row.primary_donor_name,
                                "match_method": "validated_same_year_primary_position",
                                "confidence": "medium", "anchor_accuracy": accuracy,
                                "verification_status": "validated_against_resolved_positional_anchors"})
    pd.DataFrame(validation).to_csv(VALIDATION_OUT, index=False)
    pd.DataFrame(resolutions).to_csv(RESOLUTIONS_OUT, index=False)
    accepted_counties = sum(row["accepted"] for row in validation)
    print(f"Extracted {len(names):,} primary names; validated {accepted_counties} county/year positional systems; "
          f"proposed {len(resolutions):,} new aliases")


if __name__ == "__main__":
    main()
