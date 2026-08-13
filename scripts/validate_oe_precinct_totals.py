"""Validate that per-precinct/candidate vote totals reconcile to reported Total rows.

Mirrors the checksum logic in openelections-data-al's src/total_checksum.py:
every (county, office, district, precinct) group's Total-candidate row, and
every (county, office, district, candidate) group's Total-precinct row, must
equal the sum of the non-Total component rows. This runs as an explicit
pipeline step against every synced OpenElections CSV instead of being a
one-off manual check.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def check_totals(data: pd.DataFrame, group_columns: list[str], total_column: str) -> pd.DataFrame:
    """Return rows where a reported Total does not match the summed components.

    group_columns identifies one contest, e.g. ["county", "office",
    "district", "precinct"] to check candidate totals per precinct, or
    ["county", "office", "district", "candidate"] to check precinct totals
    per candidate. total_column is the *other* column: the one whose value
    is the literal string "Total" on the reported-total row.
    """
    working = data.copy()
    working["votes"] = pd.to_numeric(working["votes"], errors="coerce")

    # Use a placeholder for NaN/None to ensure consistent comparison
    placeholder = "__MISSING__"
    for col in group_columns:
        working[col] = working[col].fillna(placeholder)

    reported = working[working[total_column] == "Total"][group_columns + ["votes"]].copy()
    reported.rename(columns={"votes": "reported_total"}, inplace=True)

    components = working[(working[total_column] != "Total") & (working["precinct"] != "Total")]
    calculated = components.groupby(group_columns, dropna=False)["votes"].sum().reset_index()
    calculated.rename(columns={"votes": "calculated_total"}, inplace=True)

    # Merge on group columns
    comparison = pd.merge(reported, calculated, on=group_columns, how="inner")
    mismatches = comparison[comparison["reported_total"] != comparison["calculated_total"]]

    # Convert placeholder back to None/NaN
    for col in group_columns:
        mismatches[col] = mismatches[col].replace(placeholder, None)

    return mismatches


def validate_file(path: Path) -> pd.DataFrame:
    data = pd.read_csv(path, low_memory=False, dtype={"precinct": str})
    candidate_totals = check_totals(data, ["county", "office", "district", "precinct"], "candidate")
    candidate_totals["check"] = "candidate_total_per_precinct"
    precinct_totals = check_totals(data, ["county", "office", "district", "candidate"], "precinct")
    precinct_totals["check"] = "precinct_total_per_candidate"
    return pd.concat([candidate_totals, precinct_totals], ignore_index=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", type=Path, nargs="+")
    args = parser.parse_args()
    any_mismatch = False
    for path in args.paths:
        mismatches = validate_file(path)
        if mismatches.empty:
            print(f"{path.name}: OK, all totals reconcile")
        else:
            any_mismatch = True
            print(f"{path.name}: {len(mismatches)} mismatch(es)")
            print(mismatches.to_string(index=False))
    if any_mismatch:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
