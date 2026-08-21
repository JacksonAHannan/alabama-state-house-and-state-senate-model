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
import sqlite3
import sys
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

sys.path.insert(0, str(Path(__file__).resolve().parent))
from oe_normalize import is_county_level_ballot, normalize_for_match, normalize_name  # noqa: E402

TARGET_SOURCES: dict[int, list[int]] = {
    2010: [2008], 2014: [2012], 2018: [2012, 2016], 2022: [2016, 2020]
}

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
    value = ("allocation_weight" if "allocation_method" in weights.columns
             else "district_activity")
    weights = (
        weights.groupby(["county_norm", "target_match_norm", "office", "district"], as_index=False)
        [value].sum().rename(columns={value: "district_activity"})
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


def load_legislative_activity_weights(database: Path, cycle: int) -> pd.DataFrame:
    """Recover same-plan precinct aliases from official legislative returns."""
    with sqlite3.connect(database) as connection:
        raw = pd.read_sql_query(
            """SELECT year AS cycle, county_key, precinct_key, office, district,
                      SUM(votes) AS district_activity
               FROM vote_observations
               WHERE source='alabama_sos' AND year=?
                 AND office IN ('State House','State Senate') AND district IS NOT NULL
               GROUP BY year,county_key,precinct_key,office,district""",
            connection, params=(cycle,))
    raw["chamber"] = raw.office.map({"State House": "house", "State Senate": "senate"})
    raw["precinct_activity"] = raw.groupby(
        ["cycle", "chamber", "county_key", "precinct_key"]
    ).district_activity.transform("sum")
    raw = raw[raw.precinct_activity.gt(0)].copy()
    raw["allocation_weight"] = raw.district_activity / raw.precinct_activity
    raw["allocation_method"] = f"{cycle}_legislative_activity_alias"
    return raw


def combine_same_plan_alias_weights(primary: pd.DataFrame,
                                    historical: list[tuple[int, pd.DataFrame]]) -> pd.DataFrame:
    """Add older precinct names without replacing current geographic weights.

    Alabama used the same enacted legislative plan in the 2002, 2006 and 2010
    elections.  Older official legislative returns can therefore supply a
    district allocation for a 2008 precinct name that disappeared by 2010.
    Current-cycle geographic names always win; historical aliases are added
    newest-first only when that county/name is absent from newer layers.
    """
    frames = [primary.assign(alias_source="2010_canonical_geography")]
    used = set(primary[["county_norm", "target_match_norm"]].itertuples(index=False, name=None))
    for cycle, raw in sorted(historical, reverse=True):
        prepared = _prepare_weights(raw, cycle)
        keys = list(prepared[["county_norm", "target_match_norm"]].itertuples(index=False, name=None))
        add = prepared[[key not in used for key in keys]].copy()
        if add.empty:
            continue
        add["alias_source"] = f"{cycle}_legislative_activity"
        frames.append(add)
        used.update(add[["county_norm", "target_match_norm"]].itertuples(index=False, name=None))
    return pd.concat(frames, ignore_index=True, sort=False)


def _match_precincts(votes: pd.DataFrame, weights: pd.DataFrame) -> pd.DataFrame:
    # County-level ballot batches are excluded from the target choice list as
    # well as from the source side (below). Both the source presidential file
    # and the target legislative-activity weights can contain a precinct
    # literally named "ABSENTEE"/"PROVISIONAL", and letting those exact-match
    # each other is actively harmful: in Jefferson County's 2016->2018 pair the
    # only three "matches" in the entire county were BESSEMER ABSENTEE,
    # BIRMINGHAM ABSENTEE and PROVISIONAL, which would have made the absentee
    # batch's district split the basis for redistributing all 290,882 of
    # Jefferson's presidential votes instead of the county's full legislative
    # activity.
    matchable = weights[~weights["target_match_norm"].map(is_county_level_ballot)]
    targets = {
        county: sorted(group["target_match_norm"].dropna().unique())
        for county, group in matchable.groupby("county_norm")
    }
    rows = []
    for row in votes.itertuples(index=False):
        if row.is_county_level:
            rows.append({"source_row_id": row.source_row_id, "target_match_norm": None,
                         "match_method": "county_level_ballot", "match_score": 0.0,
                         "score_margin": 0.0})
            continue
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
            elif score >= 92 and "alias_source" in weights.columns:
                # A textual tie is harmless when every equally scoring alias
                # has exactly the same House/Senate district allocation. This
                # commonly occurs where #1/#2 polling-place suffixes collapse
                # to a shared precinct under the same enacted plan.
                all_found = process.extract(row.match_norm, choices, scorer=fuzz.WRatio, limit=None)
                tied = [item[0] for item in all_found if abs(float(item[1]) - score) < 1e-9]
                vectors = []
                for candidate in tied:
                    vector = (weights[(weights.county_norm.eq(row.county_norm)) &
                                      (weights.target_match_norm.eq(candidate))]
                              .groupby(["office", "district"]).activity_share.sum().round(10))
                    vectors.append(tuple(vector.items()))
                if vectors and len(set(vectors)) == 1:
                    target, method = tied[0], "fuzzy_equivalent_allocation"
        rows.append({"source_row_id": row.source_row_id, "target_match_norm": target,
                     "match_method": method, "match_score": score, "score_margin": margin})
    return pd.DataFrame(rows)


def _source_completeness(
    votes: pd.DataFrame, weights: pd.DataFrame, source_year: int
) -> pd.DataFrame:
    """Flag districts whose presidential figure rests on complete county coverage.

    The 2012 OpenElections file covers only 62 of Alabama's 67 counties
    (Bullock, Butler, Hale, Montgomery and Wilcox are absent upstream). A
    district drawn entirely inside a missing county therefore has no source
    votes at all, and -- more insidiously -- a district that spans a missing
    county plus a present one still gets a margin, just one computed from part
    of its electorate. Neither case is distinguishable from a well-covered
    district by looking at the numbers alone, so record it explicitly:
    ``pres_{year}_source_complete`` is True only when every county that
    contributes target-cycle activity to the district also appears in that
    source year's votes.
    """
    covered = set(
        votes.loc[
            votes["dem_votes"].fillna(0).add(votes["rep_votes"].fillna(0)) > 0, "county_norm"
        ]
    )
    contributing = weights[weights["district_activity"] > 0]
    return (
        contributing.groupby(["office", "district"])["county_norm"]
        .apply(lambda counties: set(counties).issubset(covered))
        .reset_index(name=f"pres_{source_year}_source_complete")
    )


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
    # Absentee/provisional/overseas rows are county-wide ballot batches, not
    # polling places, so they are never name-matched: they go straight to the
    # residual tiers below, which spread them across the county's districts in
    # proportion to legislative activity. That is what the retired VEST-based
    # pipeline did with them, and it is the only defensible treatment for a
    # batch of votes with no geography finer than the county.
    votes["is_county_level"] = votes["precinct_key"].map(is_county_level_ballot)
    votes["source_row_id"] = range(1, len(votes) + 1)

    matches = _match_precincts(
        votes[["county_norm", "match_norm", "is_county_level", "source_row_id"]], weights
    )
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
    # from the 2018 output before this fallback tier was added. The same
    # naming divergence also produces 0/177 direct matches for the
    # 2012->2018 pair, so those 15 Jefferson districts fall back to the
    # county-wide average there too.
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

    # Re-base onto the target cycle's full district universe so a district that
    # received no source votes at all still appears, with null vote/margin
    # columns and source_complete=False, instead of silently vanishing from the
    # output. Before this, the 2012->2014 pair wrote 135 rows rather than 140
    # and the five Montgomery-only districts (HD 74/76/77/78, SD 26) were
    # indistinguishable from rows that were never supposed to exist.
    universe = weights[["office", "district"]].drop_duplicates()
    district = universe.merge(district, on=["office", "district"], how="left")
    district = district.merge(
        _source_completeness(votes, weights, source_year), on=["office", "district"], how="left"
    )
    district[f"pres_{source_year}_source_complete"] = (
        district[f"pres_{source_year}_source_complete"].fillna(False).astype(bool)
    )

    district["chamber"] = district["office"].map({"State House": "house", "State Senate": "senate"})
    district = district.drop(columns="office")
    if "alias_source" in weights.columns:
        matches["allocation_resolution"] = matches.match_method.map({
            "unmatched": "county_distribution_fallback",
            "county_level_ballot": "county_level_distribution",
        }).fillna("direct_precinct_alias")
    return district, matches


def _add_swing_columns(combined: pd.DataFrame, target_cycle: int) -> pd.DataFrame:
    """Add the cross-cycle presidential-swing feature for cycles with two
    presidential source years. Mirrors the original
    build_2012_president_on_2018_map.py, which fed both 2012 and 2016 into
    the 2018 cycle and wrote pres_swing_2012_2016 = 2016 margin - 2012
    margin; the 2022 cycle already did the analogous 2020-minus-2016 swing.
    fit_preliminary_war_model.py (downstream, unmodified) requires
    pres_swing_2012_2016 on 2018 rows.
    """
    if target_cycle == 2022:
        combined["pres_swing_2016_2020"] = (
            combined["pres_2020_dem_margin"] - combined["pres_2016_dem_margin"]
        )
    elif target_cycle == 2018:
        combined["pres_swing_2012_2016"] = (
            combined["pres_2016_dem_margin"] - combined["pres_2012_dem_margin"]
        )
    return combined


# Alabama has 105 House and 35 Senate districts in every cycle covered here.
EXPECTED_DISTRICTS = {"house": 105, "senate": 35}

# The only source year whose upstream file is known to be missing counties.
# openelections-data-al's 20121106 general file has no rows at all for Bullock,
# Butler, Hale, Montgomery or Wilcox. Nulls traceable to that gap are tolerated
# (and flagged via pres_2012_source_complete); a null anywhere else means
# something is being dropped that should not be, which is exactly the failure
# mode this guard exists to catch.
KNOWN_INCOMPLETE_SOURCE_YEARS = {2012}


def check_output_completeness(combined: pd.DataFrame, target_cycle: int, source_years: list[int]) -> None:
    """Fail loudly on any district row or margin lost for an unexplained reason."""
    counts = combined.groupby("chamber").size().to_dict()
    if counts != EXPECTED_DISTRICTS:
        raise AssertionError(
            f"{target_cycle}: expected {EXPECTED_DISTRICTS} district rows, got {counts}"
        )

    for source_year in source_years:
        margin = combined[f"pres_{source_year}_dem_margin"]
        complete = combined[f"pres_{source_year}_source_complete"].astype(bool)
        unexplained = combined.loc[margin.isna() & complete, ["chamber", "district"]]
        if len(unexplained):
            raise AssertionError(
                f"{source_year}->{target_cycle}: {len(unexplained)} district(s) have a null "
                f"presidential margin despite complete source-county coverage, which means votes "
                f"are being dropped somewhere: "
                f"{unexplained.to_dict('records')}"
            )
        gap = combined.loc[margin.isna() & ~complete, ["chamber", "district"]]
        if len(gap) and source_year not in KNOWN_INCOMPLETE_SOURCE_YEARS:
            raise AssertionError(
                f"{source_year}->{target_cycle}: {len(gap)} district(s) have a null presidential "
                f"margin from missing source counties, but {source_year} has no known "
                f"county-coverage gap: {gap.to_dict('records')}"
            )
        partial = int((margin.notna() & ~complete).sum())
        print(
            f"  {source_year}->{target_cycle} completeness: "
            f"{int(complete.sum())}/{len(combined)} districts fully covered, "
            f"{len(gap)} with no source votes, "
            f"{partial} with partial county coverage"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root
    geographic_path = root / "data" / "processed" / "war" / "geographic_precinct_district_weights.csv"
    fallback_weights_path = (geographic_path if geographic_path.exists() else
                             root / "data" / "processed" / "war" / "precinct_district_allocation_weights.csv")
    canonical_weights_path = root / "data" / "processed" / "elections" / "canonical_precinct_district_weights.csv"
    pres_dir = root / "data" / "processed" / "presidential"

    for target_cycle, source_years in TARGET_SOURCES.items():
        # The modern WAR-only export starts in 2014; the canonical warehouse
        # contains the independently derived 2010 VTD/population weights.
        weights_path = canonical_weights_path if target_cycle == 2010 else fallback_weights_path
        print(f"{target_cycle}: using allocation weights {weights_path.name}")
        weights = load_target_weights(weights_path, target_cycle)
        if target_cycle == 2010:
            database = root / "data" / "processed" / "elections" / "alabama_elections.sqlite"
            weights = combine_same_plan_alias_weights(
                weights,
                [(cycle, load_legislative_activity_weights(database, cycle))
                 for cycle in (2002, 2006)],
            )
            print(f"2010: combined target contains {weights.target_match_norm.nunique()} precinct aliases")
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
        combined = _add_swing_columns(combined, target_cycle)
        check_output_completeness(combined, target_cycle, source_years)
        combined.to_csv(pres_dir / f"{target_cycle}_district_presidential_features.csv", index=False)
        print(f"{target_cycle}: {len(combined)} district rows written")


if __name__ == "__main__":
    main()
