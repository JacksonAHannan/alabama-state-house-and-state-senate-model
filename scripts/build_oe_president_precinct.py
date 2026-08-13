"""Extract precinct-level President vote totals from an OpenElections CSV.

Replaces normalize_2012_president.py's raw Secretary-of-State-zip parsing:
2012, 2016, and 2020 President results all come from the same normalized
OpenElections format as the 2014/2018 legislative data, so one function
handles every year.

Note: 2012 OE data has null party fields for President rows; party must be
inferred from candidate names. 2016/2020 have proper party normalization in
most cases but may still have null party for President, so inference is
a fallback for all years on President office rows specifically.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from oe_normalize import load_oe  # noqa: E402

YEAR_FILENAMES = {
    2012: "20121106__al__general__precinct.csv",
    2016: "20161108__al__general__precinct.csv",
    2020: "20201103__al__general__precinct.csv",
}

# Mapping of exact candidate names to party for President rows where party is null.
# This is needed because 2012 OE data has no party field for President rows.
# Each entry is the exact candidate string from the CSV for that year.
PRESIDENT_CANDIDATE_TO_PARTY = {
    # 2012: tickets listed with running mate
    "BARACK OBAMA / JOE BIDEN": "D",
    "MITT ROMNEY / PAUL RYAN": "R",
    "GARY JOHNSON / JIM GRAY": "O",
    "JILL STEIN / CHERI HONKALA": "O",
    "VIRGIL H. GOODE, JR. / JAMES N. CLYMER": "O",
    # 2016: individual candidate names
    "Hillary Rodham Clinton": "D",
    "Donald J. Trump": "R",
    "Gary Johnson": "O",
    "Jill Stein": "O",
    # 2020: individual candidate names, some truncated in CSV
    "Joseph R. Biden": "D",
    "Joseph R. Biden Kamala D. Harri": "D",  # Truncated variant
    "Donald J. Trump": "R",
    "Donald J. Trump Michael R. Penc": "R",  # Truncated variant
    "Jo Jorgensen": "O",
    "Jo Jorgensen Jeremy \"Spike\" Cohen": "O",
    "Jo Jorgensen Jeremy \"Spike\" Coh": "O",  # Truncated variant
}


def infer_president_party_from_candidate(candidate: str) -> str:
    """Infer party from candidate name for President rows.

    Used as fallback when party_norm is unmapped ("O" or null) for President
    office records. This is specifically for President rows because 2012 OE
    data lacks party information for President candidates.
    """
    # Try exact match first
    if candidate in PRESIDENT_CANDIDATE_TO_PARTY:
        return PRESIDENT_CANDIDATE_TO_PARTY[candidate]

    # Fallback: try substring matches for common names
    candidate_upper = candidate.upper()
    if any(name in candidate_upper for name in ["OBAMA", "BIDEN", "HARRIS", "CLINTON"]):
        return "D"
    if any(name in candidate_upper for name in ["TRUMP", "ROMNEY", "RYAN"]):
        return "R"

    # Non-partisan/third-party candidates and administrative entries
    return "O"


def extract_president_precinct_votes(oe_csv_path: Path) -> pd.DataFrame:
    data = load_oe(oe_csv_path)
    president = data[data["office"] == "President"].copy()

    # Filter out non-geographic entries (TOTAL, ABSENTEE, PROVISIONAL, etc.)
    # These are summary rows that would double-count votes if included.
    # Use non-capturing group pattern to avoid pandas warning.
    non_geographic_pattern = r"(?:ABSENTEE|PROVISIONAL|FAILSAFE|OVERSEAS|UOCAVA|TOTAL|TOTALS|ELECTION SYSTEMS)"
    president = president[~president["precinct_key"].str.contains(non_geographic_pattern, case=False, na=False)]

    # For President rows where party_norm is "O" (unmapped), infer from candidate name.
    # This is needed for 2012 where party field is null for all President rows.
    president.loc[president["party_norm"] == "O", "party_norm"] = president.loc[
        president["party_norm"] == "O", "candidate"
    ].apply(infer_president_party_from_candidate)

    # Filter to D and R only
    president = president[president["party_norm"].isin(["D", "R"])]

    if len(president) == 0:
        # Return empty dataframe with correct columns
        return pd.DataFrame(columns=["county_key", "precinct_key", "dem_votes", "rep_votes", "two_party_votes", "pres_dem_margin"])

    pivot = (
        president
        .groupby(["county_key", "precinct_key", "party_norm"], as_index=False)["votes"]
        .sum()
        .pivot(index=["county_key", "precinct_key"], columns="party_norm", values="votes")
        .fillna(0)
        .reset_index()
    )
    for column in ["D", "R"]:
        if column not in pivot:
            pivot[column] = 0.0
    pivot = pivot.rename(columns={"D": "dem_votes", "R": "rep_votes"})
    pivot["two_party_votes"] = pivot["dem_votes"] + pivot["rep_votes"]
    pivot["pres_dem_margin"] = 100 * (pivot["dem_votes"] - pivot["rep_votes"]) / pivot[
        "two_party_votes"
    ].where(pivot["two_party_votes"] > 0)
    return pivot[["county_key", "precinct_key", "dem_votes", "rep_votes", "two_party_votes", "pres_dem_margin"]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--year", type=int, required=True, choices=sorted(YEAR_FILENAMES))
    args = parser.parse_args()
    source = args.root / "data" / "raw" / "openelections" / YEAR_FILENAMES[args.year]
    result = extract_president_precinct_votes(source)
    output_dir = args.root / "data" / "processed" / "presidential"
    output_dir.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_dir / f"{args.year}_president_precinct.csv", index=False)
    print(f"{args.year}: {len(result)} precincts, "
          f"{result.dem_votes.sum():,.0f} D / {result.rep_votes.sum():,.0f} R")


if __name__ == "__main__":
    main()
