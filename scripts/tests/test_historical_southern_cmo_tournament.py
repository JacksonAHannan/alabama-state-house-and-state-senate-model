from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run_historical_southern_cmo_tournament import add_features, candidate_residuals, prediction_rows


def tiny_frame():
    return add_features(pd.DataFrame({
        "state": ["AA", "AA", "BB", "BB"], "year": [2002, 2004, 2002, 2004],
        "chamber": ["house"] * 4, "district": [1, 1, 1, 1], "office": ["USS"] * 4,
        "baseline_dem_margin": [-10, -8, 5, 6], "legislative_dem_margin": [-5, -2, 2, 4],
        "incumbency_balance": [0, 1, 0, -1], "dem_candidate": ["D1", "D2", "D3", "D4"],
        "rep_candidate": ["R1", "R2", "R3", "R4"], "baseline_allocation_quality": ["whole_precincts"] * 4,
    }))


def test_baseline_only_predicts_the_context_margin():
    frame = tiny_frame()
    result = prediction_rows(frame.iloc[:2], frame.iloc[2:], "baseline_only", "test", "x")
    assert np.allclose(result["predicted_dem_margin"], frame.iloc[2:]["baseline_dem_margin"])


def test_candidate_residual_sign_is_symmetric():
    frame = tiny_frame()
    prediction = prediction_rows(frame.iloc[:2], frame.iloc[2:], "pooled_lag", "leave_state_out", "BB")
    candidates = candidate_residuals(frame, prediction, "pooled_lag")
    paired = candidates.pivot(index=["state", "year", "chamber", "district"], columns="party", values="candidate_quality_residual")
    assert np.allclose(paired["D"], -paired["R"])


def test_release_outputs_use_strict_sample_and_unique_loso_candidate_keys():
    root = Path(__file__).resolve().parents[2]
    panel = pd.read_csv(root / "data/processed/forecast_calibration/historical_southern_heda_panel.csv")
    candidates = pd.read_csv(root / "data/processed/war/historical_southern_cmo_candidate_residuals.csv")
    ranking = pd.read_csv(root / "data/processed/war/historical_southern_cmo_ranking.csv")
    assert len(candidates) == 2 * int(panel["model_eligible"].sum())
    assert not candidates.duplicated(["state", "year", "chamber", "district", "party"]).any()
    assert ranking["selected"].sum() == 1
