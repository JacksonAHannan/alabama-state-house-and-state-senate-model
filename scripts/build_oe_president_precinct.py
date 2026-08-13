"""Extract precinct-level President vote totals from an OpenElections CSV.

Replaces normalize_2012_president.py's raw Secretary-of-State-zip parsing:
2012, 2016, and 2020 President results all come from the same normalized
OpenElections format as the 2014/2018 legislative data, so one function
handles every year.
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

# Mapping of candidate names to party for President rows where party is null
CANDIDATE_TO_PARTY = {
    # 2012
    "BARACK OBAMA / JOE BIDEN": "D",
    "MITT ROMNEY / PAUL RYAN": "R",
    # 2016
    "Hillary Rodham Clinton": "D",
    "Donald J. Trump": "R",
    # 2020
    "Joseph R. Biden": "D",
    "Donald J. Trump Michael R. Penc": "R",  # Truncated in some cases
    "Jo Jorgensen Jeremy \"Spike\" Cohen": "O",
    "Jo Jorgensen Jeremy \"Spike\" Coh": "O",  # Truncated variant
}


def infer_party_from_candidate(candidate: str) -> str:
    """Infer party from candidate name."""
    # Try exact match first
    if candidate in CANDIDATE_TO_PARTY:
        return CANDIDATE_TO_PARTY[candidate]

    # Try substring matches for common names
    candidate_upper = candidate.upper()
    if "OBAMA" in candidate_upper or "BIDEN" in candidate_upper or "HARRIS" in candidate_upper or "CLINTON" in candidate_upper:
        return "D"
    if "TRUMP" in candidate_upper or "ROMNEY" in candidate_upper or "RYAN" in candidate_upper:
        return "R"

    # Handle write-ins, over/under votes
    if "WRITE" in candidate_upper or "OVER" in candidate_upper or "UNDER" in candidate_upper:
        return "O"

    return "O"


def extract_president_precinct_votes(oe_csv_path: Path) -> pd.DataFrame:
    data = load_oe(oe_csv_path)
    president = data[data["office"] == "President"].copy()

    # For President rows where party_norm is "O" (unmapped), infer from candidate name
    president.loc[president["party_norm"] == "O", "party_norm"] = president.loc[
        president["party_norm"] == "O", "candidate"
    ].apply(infer_party_from_candidate)

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
