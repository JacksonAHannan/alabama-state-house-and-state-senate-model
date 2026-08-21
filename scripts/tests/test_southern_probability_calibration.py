from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "data" / "processed" / "forecast_calibration"


def test_panel_has_expected_scope_and_demographics():
    panel = pd.read_csv(DIR / "southern_legislative_probability_panel.csv")
    eligible = panel[panel.primary_calibration_eligible.astype(bool)]
    assert len(eligible) >= 1100
    assert set(eligible.year) == {2018, 2020, 2022, 2024}
    assert set(eligible.state) == {"AR", "GA", "TN", "TX"}
    assert eligible[["prior_pres_margin", "nonwhite_share", "white_college_share"]].notna().all().all()


def test_probability_tournament_is_forward_and_geographic():
    metrics = pd.read_csv(DIR / "southern_probability_tournament_metrics.csv")
    assert set(metrics.validation) == {"forward_cycle", "leave_state_out"}
    assert set(metrics[metrics.validation.eq("forward_cycle")].holdout.astype(str)) == {"2020", "2022", "2024"}
    assert metrics.brier.between(0, 1).all()


def test_demographic_reactivity_does_not_beat_direct_baseline():
    summary = pd.read_csv(DIR / "southern_demographic_forecast_summary.csv").set_index("specification")
    direct = summary.loc["direct_environment_baseline"]
    reactive = summary.loc["demographic_reactivity"]
    assert direct.mae < reactive.mae
    assert direct.brier < reactive.brier


def test_hd21_southern_calibration_favors_republican():
    forecast = pd.read_csv(DIR / "alabama_2026_southern_calibrated_probabilities.csv")
    hd21 = forecast[(forecast.chamber.eq("house")) & (forecast.district.eq(21))]
    assert len(hd21) == 2
    assert (hd21.dem_probability_calibrated < .15).all()
