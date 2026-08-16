import numpy as np
import pandas as pd

from fit_preliminary_war_model import candidate_scores, prepare
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
