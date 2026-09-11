from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_heda_historical_precinct_staging import district_aggregate, normalize_legislative, vote_columns


def test_vote_columns_treats_missing_suffix_and_one_as_first_slot():
    mapping = vote_columns(["g2010_STH_dv", "g2010_STH_rv", "g2010_STH_tv1", "g2010_STH_dv2"])
    assert mapping[(2010, "STH", 1)] == {
        "dv": "g2010_STH_dv",
        "rv": "g2010_STH_rv",
        "tv": "g2010_STH_tv1",
    }
    assert mapping[(2010, "STH", 2)]["dv"] == "g2010_STH_dv2"


def test_split_precinct_slots_are_preserved_and_missing_is_not_zeroed():
    source = pd.DataFrame(
        {
            "county": ["Example"],
            "precinct": ["One"],
            "ld": [7],
            "ld2": [8],
            "g2010_STH_dv": [10],
            "g2010_STH_rv": [20],
            "g2010_STH_tv": [31],
            "g2010_STH_dv2": [5],
            "g2010_STH_rv2": [pd.NA],
        }
    )
    result = normalize_legislative(source, "FL", 2010, "FL_2010.dta", "hash")
    assert result["district"].tolist() == [7, 8]
    assert result["district_slot"].tolist() == [1, 2]
    assert pd.isna(result.loc[result["district"] == 8, "rep_votes"]).all()


def test_district_aggregate_reproduces_precinct_fragment_sums():
    source = pd.DataFrame(
        {
            "state": ["FL", "FL"],
            "year": [2010, 2010],
            "chamber": ["house", "house"],
            "district": [7, 7],
            "dem_votes": [10, 5],
            "rep_votes": [20, 15],
            "total_votes": [31, 21],
        }
    )
    result = district_aggregate(source).iloc[0]
    assert result["dem_votes"] == 15
    assert result["rep_votes"] == 35
    assert result["precinct_fragment_rows"] == 2


def test_built_florida_2010_staging_has_complete_district_sets_and_unique_fragments():
    root = Path(__file__).resolve().parents[2]
    output = root / "data/processed/precinct_history/heda"
    precincts = pd.read_csv(output / "florida_2010_legislative_precinct_fragments.csv", low_memory=False)
    districts = pd.read_csv(output / "florida_2010_legislative_district_totals.csv")
    assert not precincts.duplicated(["source_member", "source_row", "chamber", "district_slot"]).any()
    assert districts.loc[districts["chamber"].eq("house"), "district"].nunique() == 120
    assert districts.loc[districts["chamber"].eq("senate"), "district"].nunique() == 40
    expected = precincts.groupby(["chamber", "district"])[["dem_votes", "rep_votes"]].sum().reset_index()
    actual = districts[["chamber", "district", "dem_votes", "rep_votes"]]
    pd.testing.assert_frame_equal(
        expected.sort_values(["chamber", "district"]).reset_index(drop=True),
        actual.sort_values(["chamber", "district"]).reset_index(drop=True),
        check_dtype=False,
    )
