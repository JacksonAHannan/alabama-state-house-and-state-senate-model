import numpy as np
import pandas as pd

from scripts.build_ces_demographic_panel import (
    build_panel,
    effective_n,
    recode_demographics,
    weighted_mean,
)


def test_weighted_helpers():
    values = pd.Series([1.0, 0.0, 1.0])
    weights = pd.Series([2.0, 1.0, np.nan])
    assert weighted_mean(values, weights) == 2 / 3
    assert effective_n(pd.Series([1.0, 1.0, 1.0])) == 3


def test_demographic_recodes_match_yougov_groups():
    frame = pd.DataFrame({
        "age": [29, 30, 45, 65],
        "educ": ["No HS", "Some College", "4-Year", "Post-Grad"],
        "gender": pd.Series(["Male", "Female", "Male", "Female"], dtype="string"),
        "race_h": ["White", "Black", "Hispanic", "Asian"],
    })
    result = recode_demographics(frame)
    assert result.age_group.tolist() == ["under_30", "30_44", "45_64", "65_plus"]
    assert result.education_group.tolist() == ["hs_or_less", "some_college", "college_grad", "postgrad"]
    assert result.gender_group.tolist() == ["male", "female", "male", "female"]
    assert result.race_group.tolist() == ["white", "black", "hispanic", "other"]


def test_panel_is_two_party_and_keeps_weight_methods_separate():
    frame = pd.DataFrame({
        "year": [2018] * 5,
        "state": ["Alabama", "Alabama", "Alabama", "Texas", "Texas"],
        "weight": [1.0] * 5,
        "weight_post": [2.0, 1.0, 1.0, 1.0, 1.0],
        "voted_rep_party": ["Democratic", "Republican", "Independent", "Democratic", "Republican"],
        "age": [25, 50, 70, 25, 50],
        "educ": ["4-Year"] * 5,
        "gender": pd.Series(["Female", "Male", "Male", "Female", "Male"], dtype="string"),
        "race_h": ["Black", "White", "White", "Black", "White"],
    })
    result = build_panel(frame)
    overall = result[(result.year == 2018) & (result.geography == "alabama") & (result.dimension == "overall")]
    primary = overall[overall.weight_method == "year_specific_weight"].iloc[0]
    post = overall[overall.weight_method == "post_election_weight"].iloc[0]
    assert primary.unweighted_n == 2
    assert primary.dem_two_party_share == 0.5
    assert post.dem_two_party_share == 2 / 3
