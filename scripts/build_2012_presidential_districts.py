"""Aggregate 2012 presidential precinct returns to 2014 legislative districts.

2012 precinct names are matched to 2014 legislative-result precincts. The
existing 2014 district-activity shares then allocate split precincts. Votes from
unmatched/non-geographic units are distributed within county according to the
directly matched district shares and are explicitly flagged as fallback votes.
"""

from pathlib import Path
import sys

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_2014_precinct_crosswalk import normalize_for_match, normalize_name  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    votes = pd.read_csv(ROOT / "data" / "processed" / "presidential" /
                        "2012_president_precinct.csv")
    activity = pd.read_csv(ROOT / "data" / "processed" / "war" /
                           "precinct_district_allocation_weights.csv")
    activity = activity[activity.cycle.eq(2014)].copy()
    activity = activity.rename(columns={"county_key": "county_norm",
                                        "precinct_key": "precinct_norm",
                                        "allocation_weight": "activity_share"})
    activity["office"] = activity.chamber.map({"house": "State House", "senate": "State Senate"})
    activity["county_norm"] = activity.county_norm.map(normalize_name)
    votes["county_norm"] = votes.county.map(normalize_name)
    votes["match_norm"] = votes.precinct.map(normalize_for_match)
    votes["source_row_id"] = range(1, len(votes) + 1)
    activity["target_match_norm"] = activity.precinct_norm.map(normalize_for_match)
    activity = (activity.groupby(["county_norm", "target_match_norm", "office", "district"],
                                 as_index=False).district_activity.sum())
    activity["target_activity"] = activity.groupby(
        ["county_norm", "target_match_norm", "office"]).district_activity.transform("sum")
    activity["activity_share"] = activity.district_activity / activity.target_activity.where(
        activity.target_activity > 0)

    targets = {county: sorted(group.target_match_norm.dropna().unique())
               for county, group in activity.groupby("county_norm")}
    match_rows = []
    for row in votes.itertuples(index=False):
        choices = targets.get(row.county_norm, [])
        exact = [x for x in choices if x == row.match_norm]
        target = None
        method = "unmatched"
        score = margin = 0.0
        if len(exact) == 1:
            target, method, score, margin = exact[0], "exact", 100.0, 100.0
        elif choices and row.match_norm:
            found = process.extract(row.match_norm, choices, scorer=fuzz.WRatio, limit=2)
            score = float(found[0][1]); second = float(found[1][1]) if len(found) > 1 else 0.0
            margin = score - second
            if score >= 92 and margin >= 4:
                target, method = found[0][0], "fuzzy"
        if any(token in normalize_name(row.precinct) for token in
               ("ABSENTEE", "PROVISIONAL", "FAILSAFE", "UOCAVA")):
            target, method = None, "non_geographic"
        match_rows.append({"source_row_id": row.source_row_id,
                           "county_norm": row.county_norm, "precinct": row.precinct,
                           "target_match_norm": target, "match_method": method,
                           "match_score": score, "score_margin": margin})
    matches = pd.DataFrame(match_rows)
    keyed = votes.merge(matches[["source_row_id", "target_match_norm", "match_method",
                                 "match_score", "score_margin"]],
                        on="source_row_id", validate="one_to_one")

    direct = keyed[keyed.target_match_norm.notna()].merge(
        activity[["county_norm", "target_match_norm", "office", "district", "activity_share"]],
        on=["county_norm", "target_match_norm"], how="inner")
    direct["dem_allocated"] = direct.dem_votes * direct.activity_share
    direct["rep_allocated"] = direct.rep_votes * direct.activity_share
    direct["allocation_method"] = "direct_precinct_activity"

    # County/chamber distributions for votes lacking a geographic match.
    shares = (direct.groupby(["county_norm", "office", "district"], as_index=False)
              [["dem_allocated", "rep_allocated"]].sum())
    shares["activity"] = shares.dem_allocated + shares.rep_allocated
    shares["county_activity"] = shares.groupby(["county_norm", "office"]).activity.transform("sum")
    shares["fallback_share"] = shares.activity / shares.county_activity.where(shares.county_activity > 0)
    expected = keyed.assign(_join=1).merge(
        pd.DataFrame({"office": ["State House", "State Senate"], "_join": [1, 1]}), on="_join"
    ).drop(columns="_join")
    direct_keys = direct[["source_row_id", "office"]].drop_duplicates().assign(_allocated=True)
    residual = expected.merge(direct_keys, on=["source_row_id", "office"], how="left")
    residual = residual[residual._allocated.isna()].drop(columns="_allocated")
    fallback = residual.merge(shares[["county_norm", "office", "district", "fallback_share"]],
                              on=["county_norm", "office"], how="inner")
    fallback["dem_allocated"] = fallback.dem_votes * fallback.fallback_share
    fallback["rep_allocated"] = fallback.rep_votes * fallback.fallback_share
    fallback["allocation_method"] = "county_distribution_fallback"

    allocations = pd.concat([
        direct[["county_norm", "precinct", "office", "district", "dem_allocated",
                "rep_allocated", "allocation_method", "match_method"]],
        fallback[["county_norm", "precinct", "office", "district", "dem_allocated",
                  "rep_allocated", "allocation_method", "match_method"]],
    ], ignore_index=True)
    district = (allocations.groupby(["office", "district"], as_index=False)
                .agg(pres_2012_dem_votes=("dem_allocated", "sum"),
                     pres_2012_rep_votes=("rep_allocated", "sum")))
    district["pres_2012_two_party_votes"] = district.pres_2012_dem_votes + district.pres_2012_rep_votes
    district["pres_2012_dem_margin"] = 100 * (
        district.pres_2012_dem_votes - district.pres_2012_rep_votes) / district.pres_2012_two_party_votes
    district["chamber"] = district.office.map({"State House": "house", "State Senate": "senate"})
    district["cycle"] = 2014
    method_district = (allocations.assign(two_party=lambda x: x.dem_allocated + x.rep_allocated)
                       .groupby(["office", "district", "allocation_method"], as_index=False)
                       .two_party.sum())
    fallback_district = method_district[
        method_district.allocation_method.eq("county_distribution_fallback")
    ][["office", "district", "two_party"]].rename(columns={"two_party": "fallback_votes"})
    district = district.merge(fallback_district, on=["office", "district"], how="left")
    district["fallback_votes"] = district.fallback_votes.fillna(0)
    district["pres_2012_fallback_share"] = district.fallback_votes / district.pres_2012_two_party_votes
    district["pres_2012_source_counties"] = 63
    district["pres_2012_source_complete"] = False
    district["pres_2012_source_note"] = "Bullock, Butler, Hale, and Wilcox precinct results unavailable"

    qa = (allocations.groupby(["office", "allocation_method"], as_index=False)
          [["dem_allocated", "rep_allocated"]].sum())
    qa["two_party_allocated"] = qa.dem_allocated + qa.rep_allocated
    qa["share"] = qa.two_party_allocated / qa.groupby("office").two_party_allocated.transform("sum")

    output = ROOT / "data" / "processed" / "presidential"
    matches.to_csv(output / "2012_to_2014_precinct_match.csv", index=False)
    allocations.to_csv(output / "2012_president_district_allocations.csv", index=False)
    district.to_csv(output / "2014_district_presidential_features.csv", index=False)
    qa.to_csv(output / "2012_president_district_allocation_qa.csv", index=False)
    print(matches.match_method.value_counts().to_string())
    print("\nVote allocation QA:")
    print(qa.to_string(index=False))
    print(f"\nDistrict rows: {len(district)}; House: {(district.chamber == 'house').sum()}; "
          f"Senate: {(district.chamber == 'senate').sum()}")


if __name__ == "__main__":
    main()
