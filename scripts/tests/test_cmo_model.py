import numpy as np
import pandas as pd

from fit_preliminary_war_model import add_longitudinal_candidate_features, candidate_scores, prepare
from calibrate_forward_cmo_uncertainty import conformal_radius


def test_conformal_radius_uses_finite_sample_order_statistic():
    assert conformal_radius([1, 2, 3, 4], .80) == 4


def test_prepare_selects_cycle_specific_presidential_margin():
    frame = pd.DataFrame({
        "war_eligible": [True, True, True], "cycle": [2014, 2018, 2022],
        "dem_incumbent": [False] * 3, "rep_incumbent": [False] * 3,
        "pres_2012_dem_margin": [1, 2, 3], "pres_2016_dem_margin": [4, 5, 6],
        "pres_2020_dem_margin": [7, 8, 9], "pres_swing_2012_2016": [1, 1, 1],
        "pres_swing_2016_2020": [2, 2, 2], "finance_complete": [True] * 3,
    })
    got = prepare(frame)
    assert got.prior_pres_dem_margin.tolist() == [1, 5, 9]
    assert np.isnan(got.prior_pres_swing.iloc[0])


def test_prepare_selects_2008_margin_for_2010_cycle():
    frame = pd.DataFrame({
        "war_eligible": [True], "cycle": [2010],
        "dem_incumbent": [False], "rep_incumbent": [False],
        "pres_2008_dem_margin": [-12], "pres_2012_dem_margin": [np.nan],
        "pres_2016_dem_margin": [np.nan], "pres_2020_dem_margin": [np.nan],
        "pres_swing_2012_2016": [np.nan], "pres_swing_2016_2020": [np.nan],
        "finance_complete": [False],
    })
    assert prepare(frame).prior_pres_dem_margin.tolist() == [-12]


def test_prepare_excludes_provisional_historical_extension():
    frame = pd.DataFrame({
        "war_eligible": [True, True], "model_eligible": [False, True], "cycle": [1998, 2018],
        "dem_incumbent": [False] * 2, "rep_incumbent": [False] * 2,
        "pres_2012_dem_margin": [np.nan] * 2, "pres_2016_dem_margin": [np.nan, 2],
        "pres_2020_dem_margin": [np.nan] * 2, "pres_swing_2012_2016": [np.nan, 1],
        "pres_swing_2016_2020": [np.nan] * 2, "finance_complete": [False] * 2,
    })
    assert prepare(frame).cycle.tolist() == [2018]


def test_candidate_cmo_is_zero_sum_and_reverses_stability_band():
    races = pd.DataFrame({
        "cycle": [2022], "chamber": ["house"], "district": [1],
        "raw_overperformance": [5.0],
        "cmo_total_oof": [3.0], "cmo_total_final": [2.0],
        "cmo_total_stability_low": [1.0], "cmo_total_stability_high": [5.0],
        "cmo_resource_adjusted_oof": [4.0],
        "cmo_resource_adjusted_final": [3.0],
        "cmo_resource_adjusted_stability_low": [2.0],
        "cmo_resource_adjusted_stability_high": [6.0],
    })
    candidates = pd.DataFrame({
        "cycle": [2022, 2022], "chamber": ["house", "house"],
        "district": [1, 1], "party": ["D", "R"], "candidate": ["A", "B"]})
    got = candidate_scores(races, candidates).set_index("party")
    assert got.loc["D", "candidate_cmo_total_oof"] == 3
    assert got.loc["R", "candidate_cmo_total_oof"] == -3
    assert got.loc["R", "candidate_cmo_total_stability_low"] == -5
    assert got.loc["R", "candidate_cmo_total_stability_high"] == -1


def test_longitudinal_features_are_lagged_and_candidate_directional():
    races = pd.DataFrame({
        "cycle": [2014, 2018], "chamber": ["house", "house"], "district": [1, 2],
        "raw_overperformance": [12.0, -3.0],
        "contest_status": ["contested_two_party", "contested_two_party"],
    })
    candidates = pd.DataFrame({
        "year": [2014, 2014, 2018, 2018], "chamber": ["house"] * 4,
        "district": [1, 1, 2, 2], "canonical_party": ["D", "R", "D", "R"],
        "canonical_votes": [60, 40, 45, 55], "person_id": ["D1", "R1", "D2", "R1"],
        "incumbent": [0, 0, 0, 1], "winner": [1, 0, 0, 1],
    })
    got = add_longitudinal_candidate_features(races, candidates).set_index("cycle")
    assert np.isnan(got.loc[2014, "rep_prior_candidate_overperformance"])
    assert got.loc[2018, "rep_prior_candidate_overperformance"] == -12
    assert got.loc[2018, "rep_first_term_incumbent"] == 0
    assert got.loc[2018, "rep_unclassified_incumbent"] == 1


def test_unopposed_prior_race_is_not_candidate_strength():
    races = pd.DataFrame({
        "cycle": [2014, 2018], "chamber": ["house", "house"], "district": [1, 1],
        "raw_overperformance": [90.0, 5.0],
        "contest_status": ["unopposed_democrat", "contested_two_party"],
    })
    candidates = pd.DataFrame({
        "year": [2014, 2018], "chamber": ["house", "house"], "district": [1, 1],
        "canonical_party": ["D", "D"], "canonical_votes": [100, 55],
        "person_id": ["D1", "D1"], "incumbent": [0, 1], "winner": [1, 1],
    })
    got = add_longitudinal_candidate_features(races, candidates).set_index("cycle")
    assert np.isnan(got.loc[2018, "dem_prior_candidate_overperformance"])
    assert got.loc[2018, "dem_prior_unopposed"] == 1
    assert got.loc[2018, "dem_first_term_incumbent"] == 1
