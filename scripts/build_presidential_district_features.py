"""Allocate precinct-level presidential votes onto legislative districts.

For each (source_year, target_cycle) pair, precinct names from the source
year's OpenElections President results are matched (county-scoped, exact or
high-confidence fuzzy) against the target cycle's own precinct
legislative-activity weights. Unmatched votes are distributed within county
according to the directly matched district shares and flagged as fallback.
This is the technique already used and trusted for the 2012-to-2014
allocation, generalized to every source/target pair so all four use the same
method instead of three different ones.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

sys.path.insert(0, str(Path(__file__).resolve().parent))
from oe_normalize import normalize_for_match, normalize_name  # noqa: E402

TARGET_SOURCES: dict[int, list[int]] = {2014: [2012], 2018: [2016], 2022: [2016, 2020]}

# Known cross-file county-key spelling/typo variants that survive
# normalize_name() as different strings, confirmed by diffing normalized
# county sets between source votes and target weights for every pair:
#  - "STCLAIR" vs "SAINT CLAIR": normalize_name() only expands the "ST"
#    token to "SAINT" when it's its own whitespace-delimited token, so
#    "St. Clair" (period/space separates "St" and "Clair") normalizes to
#    "SAINT CLAIR" while "StClair" (no separator -- how the 2016/2020 raw
#    OpenElections files spell the county) normalizes to plain "STCLAIR".
#    2016->2022 and 2020->2022 both had "STCLAIR" in votes but only
#    "SAINT CLAIR" in the 2022-cycle weights, silently dropping ~36-39K
#    votes' worth of St. Clair county -- not just missing rows, but a
#    quietly under-counted margin in every other district St. Clair shares
#    with a correctly-matching county.
#  - "SAINT" (from bare "St", the entire 2012 raw file's truncated county
#    field for this one county -- confirmed by its precinct names being
#    unmistakably St. Clair towns: Ashville, Argo, Odenville-area churches)
#    vs "SAINT CLAIR". Alabama has exactly one "St."-prefixed county, so
#    this is an unambiguous, safe correction, not a guess.
#  - "RADOLPH" (2012 raw file's misspelling, missing the "N") vs
#    "RANDOLPH".
COUNTY_ALIASES: dict[str, str] = {
    "STCLAIR": "SAINT CLAIR",
    "SAINT": "SAINT CLAIR",
    "RADOLPH": "RANDOLPH",
}


def _canonical_county(county_norm: str) -> str:
    return COUNTY_ALIASES.get(county_norm, county_norm)


def _prepare_weights(raw_weights: pd.DataFrame, target_cycle: int) -> pd.DataFrame:
    weights = raw_weights[raw_weights["cycle"].eq(target_cycle)].copy()
    weights["county_norm"] = weights["county_key"].map(normalize_name).map(_canonical_county)
    weights["target_match_norm"] = weights["precinct_key"].map(normalize_for_match)
    weights["office"] = weights["chamber"].map({"house": "State House", "senate": "State Senate"})
    weights = (
        weights.groupby(["county_norm", "target_match_norm", "office", "district"], as_index=False)
        ["district_activity"].sum()
    )
    weights["target_activity"] = weights.groupby(
        ["county_norm", "target_match_norm", "office"]
    )["district_activity"].transform("sum")
    weights["activity_share"] = weights["district_activity"] / weights["target_activity"].where(
        weights["target_activity"] > 0
    )
    return weights


def load_target_weights(weights_path: Path, target_cycle: int) -> pd.DataFrame:
    raw_weights = pd.read_csv(weights_path)
    return _prepare_weights(raw_weights, target_cycle)


def _match_precincts(votes: pd.DataFrame, weights: pd.DataFrame) -> pd.DataFrame:
    targets = {
        county: sorted(group["target_match_norm"].dropna().unique())
        for county, group in weights.groupby("county_norm")
    }
    rows = []
    for row in votes.itertuples(index=False):
        choices = targets.get(row.county_norm, [])
        target = None
        method = "unmatched"
        score = margin = 0.0
        if row.match_norm in choices:
            target, method, score, margin = row.match_norm, "exact", 100.0, 100.0
        elif choices and row.match_norm:
            found = process.extract(row.match_norm, choices, scorer=fuzz.WRatio, limit=2)
            score = float(found[0][1])
            second = float(found[1][1]) if len(found) > 1 else 0.0
            margin = score - second
            if score >= 92 and margin >= 4:
                target, method = found[0][0], "fuzzy"
        rows.append({"source_row_id": row.source_row_id, "target_match_norm": target,
                     "match_method": method, "match_score": score, "score_margin": margin})
    return pd.DataFrame(rows)


def allocate_to_districts(
    votes: pd.DataFrame, weights: pd.DataFrame, source_year: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Allocate precinct votes to legislative districts.

    votes: columns county_key, precinct_key, dem_votes, rep_votes (one row
    per source precinct). weights: output of load_target_weights()/`_prepare_weights`.
    Returns (district_features, matches): district_features has one row per
    (chamber, district) with pres_{source_year}_dem_votes/rep_votes/
    two_party_votes/dem_margin/fallback_share; matches is the per-precinct
    match diagnostic frame.
    """
    votes = votes.copy()
    votes["county_norm"] = votes["county_key"].map(normalize_name).map(_canonical_county)
    votes["match_norm"] = votes["precinct_key"].map(normalize_for_match)
    votes["source_row_id"] = range(1, len(votes) + 1)

    matches = _match_precincts(votes[["county_norm", "match_norm", "source_row_id"]], weights)
    keyed = votes.merge(matches, on="source_row_id", validate="one_to_one")

    direct = keyed[keyed["target_match_norm"].notna()].merge(
        weights[["county_norm", "target_match_norm", "office", "district", "activity_share"]],
        on=["county_norm", "target_match_norm"], how="inner",
    )
    direct["dem_allocated"] = direct["dem_votes"] * direct["activity_share"]
    direct["rep_allocated"] = direct["rep_votes"] * direct["activity_share"]
    direct["allocation_method"] = "direct_precinct_activity"

    shares = (
        direct.groupby(["county_norm", "office", "district"], as_index=False)
        [["dem_allocated", "rep_allocated"]].sum()
    )
    shares["activity"] = shares["dem_allocated"] + shares["rep_allocated"]
    shares["county_activity"] = shares.groupby(["county_norm", "office"])["activity"].transform("sum")
    shares["fallback_share"] = shares["activity"] / shares["county_activity"].where(shares["county_activity"] > 0)

    # County-level activity share computed directly from the target cycle's
    # own legislative-activity weights, independent of which precincts this
    # source year happened to match. This is the fallback of last resort for
    # a county+office where NOT ONE precinct matched directly: without it,
    # `shares` has no rows for that county+office, the inner-join fallback
    # below drops the residual votes entirely, and the whole county silently
    # disappears from the output. Found in practice: Jefferson county's
    # 2018/2022 legislative-weights precinct names carry a "PREC " prefix
    # that 2016's source presidential precinct names lack, so 0/171
    # Jefferson precincts matched directly for 2016->2018 and 2016->2022,
    # and all 15 Jefferson-only districts (12 house + 3 senate) vanished
    # from the 2018 output before this fallback tier was added.
    county_shares = weights.groupby(["county_norm", "office", "district"], as_index=False)["district_activity"].sum()
    county_shares["county_total_activity"] = county_shares.groupby(["county_norm", "office"])["district_activity"].transform("sum")
    county_shares["county_fallback_share"] = county_shares["district_activity"] / county_shares["county_total_activity"].where(
        county_shares["county_total_activity"] > 0
    )

    expected = keyed.assign(_join=1).merge(
        pd.DataFrame({"office": ["State House", "State Senate"], "_join": [1, 1]}), on="_join"
    ).drop(columns="_join")
    direct_keys = direct[["source_row_id", "office"]].drop_duplicates().assign(_allocated=True)
    residual = expected.merge(direct_keys, on=["source_row_id", "office"], how="left")
    residual = residual[residual["_allocated"].isna()].drop(columns="_allocated")

    has_direct_share = shares[["county_norm", "office"]].drop_duplicates().assign(_has_direct_share=True)
    residual = residual.merge(has_direct_share, on=["county_norm", "office"], how="left")
    residual_precinct_fallback = residual[residual["_has_direct_share"].notna()].drop(columns="_has_direct_share")
    residual_county_fallback = residual[residual["_has_direct_share"].isna()].drop(columns="_has_direct_share")

    fallback_precinct = residual_precinct_fallback.merge(
        shares[["county_norm", "office", "district", "fallback_share"]],
        on=["county_norm", "office"], how="inner",
    )
    fallback_precinct["dem_allocated"] = fallback_precinct["dem_votes"] * fallback_precinct["fallback_share"]
    fallback_precinct["rep_allocated"] = fallback_precinct["rep_votes"] * fallback_precinct["fallback_share"]
    fallback_precinct["allocation_method"] = "county_distribution_fallback"

    fallback_county = residual_county_fallback.merge(
        county_shares[["county_norm", "office", "district", "county_fallback_share"]],
        on=["county_norm", "office"], how="inner",
    )
    fallback_county["dem_allocated"] = fallback_county["dem_votes"] * fallback_county["county_fallback_share"]
    fallback_county["rep_allocated"] = fallback_county["rep_votes"] * fallback_county["county_fallback_share"]
    fallback_county["allocation_method"] = "county_activity_fallback"

    fallback = pd.concat([fallback_precinct, fallback_county], ignore_index=True)

    allocations = pd.concat(
        [
            direct[["county_norm", "precinct_key", "office", "district", "dem_allocated", "rep_allocated", "allocation_method"]],
            fallback[["county_norm", "precinct_key", "office", "district", "dem_allocated", "rep_allocated", "allocation_method"]],
        ],
        ignore_index=True,
    )
    district = allocations.groupby(["office", "district"], as_index=False).agg(
        **{
            f"pres_{source_year}_dem_votes": ("dem_allocated", "sum"),
            f"pres_{source_year}_rep_votes": ("rep_allocated", "sum"),
        }
    )
    district[f"pres_{source_year}_two_party_votes"] = (
        district[f"pres_{source_year}_dem_votes"] + district[f"pres_{source_year}_rep_votes"]
    )
    district[f"pres_{source_year}_dem_margin"] = 100 * (
        district[f"pres_{source_year}_dem_votes"] - district[f"pres_{source_year}_rep_votes"]
    ) / district[f"pres_{source_year}_two_party_votes"]

    fallback_by_district = (
        allocations.assign(two_party=lambda x: x["dem_allocated"] + x["rep_allocated"])
        .query("allocation_method != 'direct_precinct_activity'")
        .groupby(["office", "district"], as_index=False)["two_party"].sum()
        .rename(columns={"two_party": "fallback_votes"})
    )
    district = district.merge(fallback_by_district, on=["office", "district"], how="left")
    district["fallback_votes"] = district["fallback_votes"].fillna(0)
    district[f"pres_{source_year}_fallback_share"] = (
        district["fallback_votes"] / district[f"pres_{source_year}_two_party_votes"]
    )
    district = district.drop(columns="fallback_votes")
    district["chamber"] = district["office"].map({"State House": "house", "State Senate": "senate"})
    district = district.drop(columns="office")
    return district, matches


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root
    weights_path = root / "data" / "processed" / "war" / "precinct_district_allocation_weights.csv"
    pres_dir = root / "data" / "processed" / "presidential"

    for target_cycle, source_years in TARGET_SOURCES.items():
        weights = load_target_weights(weights_path, target_cycle)
        combined: pd.DataFrame | None = None
        for source_year in source_years:
            votes = pd.read_csv(pres_dir / f"{source_year}_president_precinct.csv")
            district, matches = allocate_to_districts(votes, weights, source_year)
            matches.to_csv(pres_dir / f"{source_year}_to_{target_cycle}_precinct_match.csv", index=False)
            print(f"{source_year}->{target_cycle}: {matches.match_method.value_counts().to_dict()}")
            combined = district if combined is None else combined.merge(
                district, on=["chamber", "district"], how="outer", validate="one_to_one"
            )
        combined["cycle"] = target_cycle
        if target_cycle == 2022:
            combined["pres_swing_2016_2020"] = (
                combined["pres_2020_dem_margin"] - combined["pres_2016_dem_margin"]
            )
        combined.to_csv(pres_dir / f"{target_cycle}_district_presidential_features.csv", index=False)
        print(f"{target_cycle}: {len(combined)} district rows written")


if __name__ == "__main__":
    main()
