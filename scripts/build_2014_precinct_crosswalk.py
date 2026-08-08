"""Build and validate a 2014 Alabama result-unit to 2010 Census VTD crosswalk.

The 2014 Secretary of State files use three layouts and are not spatial data.
The target geometry is the 2012 TIGER publication of 2010 Census VTDs. Matches
are county-scoped. Only unique exact or high-confidence fuzzy matches are
accepted automatically; all other cases are retained for review.
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path

import pandas as pd
import pyogrio
from rapidfuzz import fuzz, process


NON_GEOGRAPHIC_RE = re.compile(
    r"\b(ABSENTEE|PROVISIONAL|FAILSAFE|OVERSEAS|UOCAVA|TOTAL|TOTALS|ELECTION SYSTEMS)\b"
)

TOKEN_REPLACEMENTS = {
    "1ST": "FIRST",
    "CTR": "CENTER",
    "CNTR": "CENTER",
    "COMM": "COMMUNITY",
    "DEPT": "DEPARTMENT",
    "DEPTMENT": "DEPARTMENT",
    "FD": "FIRE DEPARTMENT",
    "VFD": "VOLUNTEER FIRE DEPARTMENT",
    "VOL": "VOLUNTEER",
    "BAPT": "BAPTIST",
    "CH": "CHURCH",
    "CHUR": "CHURCH",
    "ELEM": "ELEMENTARY",
    "SCH": "SCHOOL",
    "MT": "MOUNT",
    "ST": "SAINT",
    "CO": "COUNTY",
    "CTY": "COUNTY",
    "REC": "RECREATION",
    "BLDG": "BUILDING",
}


def normalize_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    text = text.upper().replace("&", " AND ")
    text = re.sub(r"[_/\\\-]+", " ", text)
    text = re.sub(r"[^A-Z0-9 ]+", " ", text)
    tokens: list[str] = []
    for token in text.split():
        token = str(int(token)) if token.isdigit() else token
        tokens.extend(TOKEN_REPLACEMENTS.get(token, token).split())
    return " ".join(tokens)


def normalize_for_match(value: object) -> str:
    """Normalize a result name while removing codes and machine suffixes."""
    text = str(value).strip()
    text = re.sub(r"^\s*\d{3,4}\s*[-:]?\s*", "", text)
    text = re.sub(r"\s*#\s*\d+\s*$", "", text)
    text = re.sub(r"\s+(?:BOX|BX)\s*\d+\s*$", "", text, flags=re.I)
    # Montgomery reports multiple machines as a terminal 1/2/3 after a
    # three-digit precinct code. Other counties use #1/#2, handled above.
    text = re.sub(r"\s+[123]\s*$", "", text)
    return normalize_name(text)


def normalize_vtd_name(value: object) -> str:
    """Normalize Census VTD labels while removing administrative codes."""
    text = str(value).strip()
    text = re.sub(r"^\s*PCT\.?\s*\d+(?:\.\d+)?\s*", "", text, flags=re.I)
    text = re.sub(r"^\s*\d+[A-Z]\s+", "", text, flags=re.I)
    text = re.sub(r"\s+VOTING DISTRICT\s*$", "", text, flags=re.I)
    text = re.sub(r"\s*[-:]\s*\d+(?:\.\d+)?\s*$", "", text)
    return normalize_name(text)


def county_from_filename(path: Path) -> str:
    stem = path.stem
    stem = re.sub(r"^2014-General-", "", stem, flags=re.I)
    stem = re.sub(r"\s+2014 General Precinct$", "", stem, flags=re.I)
    return normalize_name(stem)


def read_result_units(results_dir: Path) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for path in sorted(p for p in results_dir.iterdir() if p.suffix.lower() in {".csv", ".xls", ".xlsx"}):
        frame = (
            pd.read_csv(path, low_memory=False, encoding_errors="replace")
            if path.suffix.lower() == ".csv"
            else pd.read_excel(path)
        )
        columns = [str(c).strip() for c in frame.columns]
        county = county_from_filename(path)

        if "Precinct Name" in columns:
            layout = "long"
            names = frame.iloc[:, columns.index("Precinct Name")].dropna().astype(str)
        elif len(columns) >= 4 and "Contest Title" in columns[0]:
            layout = "contest_rows"
            names = pd.Series(columns[3:], dtype="object")
        else:
            layout = "precinct_rows"
            # The first data column contains precincts; the first spreadsheet
            # row was consumed as the multi-row contest header by pandas.
            names = frame.iloc[:, 0].dropna().astype(str)

        for raw_name in dict.fromkeys(n.strip() for n in names if n.strip()):
            normalized = normalize_name(raw_name)
            if normalized == county:
                # In precinct-row workbooks this is the county label in the
                # second header row, not a reporting unit.
                continue
            rows.append(
                {
                    "county": county,
                    "result_precinct": raw_name,
                    "result_precinct_norm": normalized,
                    "result_match_norm": normalize_for_match(raw_name),
                    "source_file": path.name,
                    "source_layout": layout,
                    "is_non_geographic": bool(NON_GEOGRAPHIC_RE.search(normalized)),
                }
            )

    result = pd.DataFrame(rows).drop_duplicates(["county", "result_precinct_norm"])
    result.insert(0, "result_unit_id", range(1, len(result) + 1))
    return result


def read_vtds(vtd_zip: Path, county_source_shp: Path) -> pd.DataFrame:
    layer = next(n for n in __import__("zipfile").ZipFile(vtd_zip).namelist() if n.lower().endswith(".shp"))
    vtd = pyogrio.read_dataframe(
        f"/vsizip/{vtd_zip.as_posix()}/{layer}", read_geometry=False
    )
    county_source = pyogrio.read_dataframe(county_source_shp, read_geometry=False)
    county_map = (
        county_source[["COUNTYFP", "County"]]
        .dropna()
        .assign(COUNTYFP=lambda x: x["COUNTYFP"].astype(str).str.zfill(3))
        .drop_duplicates("COUNTYFP")
        .set_index("COUNTYFP")["County"]
        .map(normalize_name)
        .to_dict()
    )
    vtd["county"] = vtd["COUNTYFP10"].astype(str).str.zfill(3).map(county_map)
    vtd["vtd_name_norm"] = vtd["NAME10"].map(normalize_vtd_name)
    return vtd.rename(
        columns={
            "COUNTYFP10": "county_fips",
            "VTDST10": "vtd_code",
            "GEOID10": "vtd_geoid",
            "NAME10": "vtd_name",
        }
    )[["county", "county_fips", "vtd_code", "vtd_geoid", "vtd_name", "vtd_name_norm"]]


def build_crosswalk(result_units: pd.DataFrame, vtds: pd.DataFrame) -> pd.DataFrame:
    targets = {county: group.reset_index(drop=True) for county, group in vtds.groupby("county")}
    output: list[dict[str, object]] = []

    for row in result_units.to_dict("records"):
        record = dict(row)
        record.update(
            {
                "vtd_geoid": pd.NA,
                "vtd_code": pd.NA,
                "vtd_name": pd.NA,
                "vtd_name_norm": pd.NA,
                "match_method": "unmatched",
                "match_score": pd.NA,
                "score_margin": pd.NA,
                "candidate_count": 0,
                "candidate_2_name": pd.NA,
                "candidate_2_score": pd.NA,
                "candidate_3_name": pd.NA,
                "candidate_3_score": pd.NA,
            }
        )
        if row["is_non_geographic"]:
            record["match_method"] = "non_geographic"
            output.append(record)
            continue

        county_targets = targets.get(row["county"])
        if county_targets is None or county_targets.empty:
            record["match_method"] = "county_missing"
            output.append(record)
            continue

        exact = county_targets[county_targets["vtd_name_norm"] == row["result_match_norm"]]
        if len(exact) == 1:
            best = exact.iloc[0]
            method, score, margin = "exact_normalized", 100.0, 100.0
            candidate_count = 1
        else:
            choices = county_targets["vtd_name_norm"].fillna("").tolist()
            candidates = process.extract(
                row["result_match_norm"], choices, scorer=fuzz.WRatio, limit=3
            )
            best_name, score, _best_index = candidates[0]
            second_score = candidates[1][1] if len(candidates) > 1 else 0.0
            margin = float(score - second_score)
            best = county_targets.loc[county_targets["vtd_name_norm"].fillna("") == best_name].iloc[0]
            candidate_count = sum(1 for _, value, _ in candidates if value >= score - 2)
            if score >= 94 and margin >= 5:
                method = "fuzzy_high"
            elif score >= 88 and margin >= 8:
                method = "fuzzy_medium"
            else:
                method = "review"

        record.update(
            {
                "vtd_geoid": best["vtd_geoid"],
                "vtd_code": best["vtd_code"],
                "vtd_name": best["vtd_name"],
                "vtd_name_norm": best["vtd_name_norm"],
                "match_method": method,
                "match_score": round(float(score), 2),
                "score_margin": round(float(margin), 2),
                "candidate_count": candidate_count,
                "candidate_2_name": candidates[1][0] if len(candidates) > 1 else pd.NA,
                "candidate_2_score": round(float(candidates[1][1]), 2) if len(candidates) > 1 else pd.NA,
                "candidate_3_name": candidates[2][0] if len(candidates) > 2 else pd.NA,
                "candidate_3_score": round(float(candidates[2][1]), 2) if len(candidates) > 2 else pd.NA,
            }
        )
        output.append(record)

    crosswalk = pd.DataFrame(output)
    accepted = crosswalk["match_method"].isin(["exact_normalized", "fuzzy_high", "fuzzy_medium"])
    crosswalk["accepted_match"] = accepted
    crosswalk["needs_review"] = ~crosswalk["accepted_match"] & ~crosswalk["is_non_geographic"]
    crosswalk["review_reason"] = ""
    crosswalk.loc[crosswalk["match_method"] == "review", "review_reason"] = "low_or_ambiguous_score"
    crosswalk.loc[crosswalk["match_method"] == "county_missing", "review_reason"] = "county_not_found"
    accepted_counts = crosswalk.loc[accepted].groupby("vtd_geoid")["result_unit_id"].transform("size")
    crosswalk["accepted_units_for_vtd"] = pd.NA
    crosswalk.loc[accepted, "accepted_units_for_vtd"] = accepted_counts.astype("Int64")
    crosswalk["relationship_note"] = ""
    accepted_unit_counts = pd.to_numeric(crosswalk["accepted_units_for_vtd"], errors="coerce").fillna(0)
    crosswalk.loc[accepted & (accepted_unit_counts > 1), "relationship_note"] = "many_result_units_to_one_vtd"
    return crosswalk


def write_outputs(crosswalk: pd.DataFrame, vtds: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    crosswalk.to_csv(output_dir / "2014_precinct_vtd_crosswalk.csv", index=False)
    crosswalk[crosswalk["needs_review"]].to_csv(output_dir / "2014_precinct_vtd_review.csv", index=False)

    geographic = crosswalk[~crosswalk["is_non_geographic"]]
    summary = (
        geographic.groupby("county", as_index=False)
        .agg(
            result_units=("result_unit_id", "size"),
            accepted=("accepted_match", "sum"),
            needs_review=("needs_review", "sum"),
            exact=("match_method", lambda x: (x == "exact_normalized").sum()),
            fuzzy=("match_method", lambda x: x.isin(["fuzzy_high", "fuzzy_medium"]).sum()),
        )
    )
    summary["accepted_rate"] = (summary["accepted"] / summary["result_units"]).round(4)
    vtd_counts = vtds.groupby("county").size().rename("vtd_count")
    summary = summary.merge(vtd_counts, on="county", how="outer").sort_values("county")
    summary.to_csv(output_dir / "2014_precinct_vtd_summary_by_county.csv", index=False)

    overall = pd.DataFrame(
        [
            {
                "result_units_total": len(crosswalk),
                "non_geographic_units": int(crosswalk["is_non_geographic"].sum()),
                "geographic_units": len(geographic),
                "accepted_matches": int(geographic["accepted_match"].sum()),
                "needs_review": int(geographic["needs_review"].sum()),
                "accepted_rate": round(float(geographic["accepted_match"].mean()), 4),
                "vtd_total": len(vtds),
                "accepted_unique_vtds": int(crosswalk.loc[crosswalk["accepted_match"], "vtd_geoid"].nunique()),
            }
        ]
    )
    overall.to_csv(output_dir / "2014_precinct_vtd_summary.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root
    sources = root / "Results and Shapefiles"
    result_units = read_result_units(sources / "2014General-precinctLevel")
    vtds = read_vtds(
        sources / "tl_2012_01_vtd10.zip",
        sources / "al_gen_22_prec" / "al_gen_22_st_prec.shp",
    )
    crosswalk = build_crosswalk(result_units, vtds)
    write_outputs(crosswalk, vtds, root / "data" / "derived" / "crosswalks")


if __name__ == "__main__":
    main()
