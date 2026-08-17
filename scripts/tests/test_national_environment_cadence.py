from pathlib import Path

import pandas as pd


ROOT = Path(__file__).parents[2]
WAR = ROOT / "data" / "processed" / "war"


def test_official_national_environment_covers_full_archive():
    environment = pd.read_csv(ROOT / "data" / "manual" / "national_midterm_environment.csv")
    assert list(environment.cycle) == [1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022]
    calculated = (100 * (environment.midterm_house_dem_votes - environment.midterm_house_rep_votes) /
                  (environment.midterm_house_dem_votes + environment.midterm_house_rep_votes) -
                  100 * (environment.pres_dem_votes - environment.pres_rep_votes) /
                  (environment.pres_dem_votes + environment.pres_rep_votes))
    assert (calculated - environment.national_environment_swing).abs().max() < 1e-5


def test_cycle_weights_capture_post2016_jump():
    weights = pd.read_csv(WAR / "national_environment_cycle_weights.csv").set_index("cycle")
    assert weights.loc[2010, "optimal_nonnegative_weight"] == 0
    assert weights.loc[2014, "optimal_nonnegative_weight"] == 0
    assert weights.loc[2018, "optimal_nonnegative_weight"] > 0
    assert weights.loc[2022, "optimal_nonnegative_weight"] > weights.loc[2018, "optimal_nonnegative_weight"]


def test_ml_comparison_is_expanding_cycle_only():
    comparison = pd.read_csv(WAR / "national_environment_ml_forward_comparison.csv")
    assert set(comparison.test_cycle) == {1998, 2002, 2006, 2010, 2014, 2018, 2022}
    assert comparison[comparison.test_cycle.eq(2022)].train_cycles.eq(
        "1994,1998,2002,2006,2010,2014,2018").all()
    assert comparison.groupby("model").test_cycle.nunique().eq(7).all()


def test_2026_saturating_extrapolation_is_heavier_but_diminishing():
    weights = pd.read_csv(WAR / "national_environment_cycle_weights.csv").set_index("cycle")
    future = pd.read_csv(WAR / "national_environment_2026_extrapolations.csv").set_index("cadence")
    projected = future.loc["post2016_saturating_curve", "weight_2026"]
    assert projected > weights.loc[2022, "optimal_nonnegative_weight"]
    assert projected < future.loc["half_last_jump", "weight_2026"]
