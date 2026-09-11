"""Retained calibration-panel and evaluation checks for research/compatibility."""

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
