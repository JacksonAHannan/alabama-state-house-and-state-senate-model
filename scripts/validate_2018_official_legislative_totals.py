"""Compare modeled 2018 candidate totals with the official county workbooks."""

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
import re
import unicodedata

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Results and Shapefiles" / "2018-Official-General-Precinct-Results.zip"
WAR = ROOT / "data" / "processed" / "war"


def norm(value: object) -> str:
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().upper()
    value = re.sub(r"\b(JR|SR|II|III|IV)\b", " ", value)
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z ]", " ", value)).strip()


def parse_contest(value: object):
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().upper()
    text = re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9 ]", " ", text)).strip()
    patterns = [
        ("house", r"STATE REPRESENTATIVE,? DISTRICT (\d+)"),
        ("senate", r"STATE SENATOR,? DISTRICT (\d+)"),
    ]
    for chamber, pattern in patterns:
        found = re.search(pattern, text)
        if found:
            return chamber, int(found.group(1))
    return None, None


def main() -> None:
    rows = []
    with ZipFile(SOURCE) as archive:
        for filename in archive.namelist():
            data = pd.read_excel(BytesIO(archive.read(filename)), header=0)
            chamber_district = data["Contest Title"].map(parse_contest)
            data["chamber"] = chamber_district.map(lambda x: x[0])
            data["district"] = chamber_district.map(lambda x: x[1])
            data = data[data.chamber.notna() & data.Party.astype(str).str.strip().isin(["DEM", "REP"])]
            vote_cols = data.columns[3:-2]  # excludes the two fields added above
            data["row_votes"] = data[vote_cols].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)
            for _, row in data.iterrows():
                rows.append({
                    "county_file": filename, "chamber": row.chamber,
                    "district": int(row.district),
                    "party": "D" if str(row.Party).strip() == "DEM" else "R",
                    "candidate_official": str(row.Candidate).strip(),
                    "candidate_norm": norm(row.Candidate), "votes_official_county": row.row_votes,
                })
    county = pd.DataFrame(rows)
    official = (county.groupby(["chamber", "district", "party", "candidate_norm"], as_index=False)
                .agg(candidate_official=("candidate_official", "first"),
                     votes_official=("votes_official_county", "sum"),
                     county_rows=("county_file", "nunique")))
    modeled = pd.read_csv(WAR / "race_candidate_results.csv")
    modeled = modeled[modeled.cycle.eq(2018)].copy()
    modeled["candidate_norm"] = modeled.candidate.map(norm)
    comparison = modeled.merge(official, on=["chamber", "district", "party", "candidate_norm"],
                               how="outer", indicator=True, validate="one_to_one")
    comparison["vote_difference"] = comparison.votes - comparison.votes_official
    comparison["exact_vote_match"] = comparison._merge.eq("both") & comparison.vote_difference.eq(0)
    comparison.to_csv(WAR / "2018_official_vote_validation.csv", index=False)
    county.to_csv(WAR / "2018_official_candidate_county_totals.csv", index=False)
    summary = pd.DataFrame([{
        "modeled_candidates": len(modeled),
        "official_candidates": len(official),
        "joined_candidates": int(comparison._merge.eq("both").sum()),
        "exact_vote_matches": int(comparison.exact_vote_match.sum()),
        "mismatches": int((comparison._merge.eq("both") & ~comparison.exact_vote_match).sum()),
        "modeled_only": int(comparison._merge.eq("left_only").sum()),
        "official_only": int(comparison._merge.eq("right_only").sum()),
    }])
    summary.to_csv(WAR / "2018_official_vote_validation_summary.csv", index=False)
    print(summary.to_string(index=False))
    print(comparison[~comparison.exact_vote_match][
        ["chamber", "district", "party", "candidate", "candidate_official", "votes",
         "votes_official", "vote_difference", "_merge"]].head(30).to_string(index=False))


if __name__ == "__main__":
    main()
