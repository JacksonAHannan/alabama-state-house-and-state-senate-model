"""Attach Nate Silver pollster grades to the VoteHub crosstab source catalog."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RATINGS = ROOT / "data" / "raw" / "polling" / "nate_silver_pollster_ratings.csv"
QUEUE = ROOT / "data" / "processed" / "polling" / "votehub_crosstab_document_review_queue.csv"
OUT = ROOT / "data" / "processed" / "polling"
ELIGIBLE = {"A+", "A", "A-", "A/B", "B+", "B"}

# Conservative aliases only: combined firms are not promoted from a constituent
# firm's grade unless Silver lists that exact partnership.
ALIASES = {
    "Marist University": "Marist College",
}


def clean_grade(value: str) -> str:
    return str(value).split("@@", 1)[0].strip()


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def attach_grades(queue: pd.DataFrame, ratings: pd.DataFrame) -> pd.DataFrame:
    r = ratings.copy()
    r["silver_grade"] = r.Grade.map(clean_grade)
    lookup = {normalize_name(row["Pollster"]): row for _, row in r.iterrows()}
    rows = []
    for pollster in sorted(queue.pollster.dropna().unique()):
        rated_name = ALIASES.get(pollster, pollster)
        match = lookup.get(normalize_name(rated_name))
        rows.append({"votehub_pollster": pollster, "silver_pollster": match["Pollster"] if match is not None else None,
                     "silver_grade": match["silver_grade"] if match is not None else None,
                     "predictive_plus_minus": match.get("Predictive Plus-Minus") if match is not None else None,
                     "silver_number_of_polls": match.get("Number of polls") if match is not None else None,
                     "match_method": "explicit_alias" if pollster in ALIASES else ("normalized_exact" if match is not None else "unmatched"),
                     "b_or_better": bool(match is not None and match["silver_grade"] in ELIGIBLE),
                     # Compatibility field for existing downstream artifacts.
                     "b_plus_or_better": bool(match is not None and match["silver_grade"] in ELIGIBLE)})
    crosswalk = pd.DataFrame(rows)
    return queue.merge(crosswalk, left_on="pollster", right_on="votehub_pollster", validate="many_to_one")


def main() -> None:
    result = attach_grades(pd.read_csv(QUEUE), pd.read_csv(RATINGS))
    result.to_csv(OUT / "votehub_crosstab_documents_with_silver_grades.csv", index=False)
    eligible = result[result.b_plus_or_better].copy()
    eligible.to_csv(OUT / "votehub_silver_bplus_crosstab_review_queue.csv", index=False)
    coverage = eligible.groupby(["pollster", "silver_pollster", "silver_grade", "asset_kind", "status"],
                                dropna=False).agg(rows=("id", "size"), polls=("id", "nunique")).reset_index()
    coverage.to_csv(OUT / "votehub_silver_bplus_document_coverage.csv", index=False)
    print(coverage.to_string(index=False))


if __name__ == "__main__":
    main()
