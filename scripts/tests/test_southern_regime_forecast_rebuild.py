import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
WAR = ROOT / "data/processed/war"


def load(name: str) -> pd.DataFrame:
    return pd.read_csv(WAR / name, low_memory=False)


def test_normalized_panel_preserves_both_source_eras_and_missing_incumbency():
    panel = load("forecast_regime_v1_panel.csv")
    assert len(panel) == 3590
    assert panel.source_era.value_counts().to_dict() == {
        "historical_1994_2016": 2402, "recent_2018_2024": 1188}
    assert not panel.duplicated(["state", "year", "chamber", "district"]).any()
    assert panel.loc[panel.year.eq(2024), "incumbency_balance"].isna().all()
    assert panel.loc[panel.year.ne(2024), "incumbency_balance"].notna().all()


def test_forward_predictions_have_no_temporal_leakage():
    predictions = load("forecast_regime_v1_predictions.csv")
    trained = predictions.loc[predictions.train_rows.gt(0)]
    assert trained.train_max_year.lt(trained.year).all()
    recent = trained.loc[trained.model.isin(["pooled_recent", "ridge_recent_only"])]
    assert recent.train_min_year.ge(2018).all()
    assert set(predictions.year) == {2018, 2020, 2022, 2024}


def test_selection_uses_prespecified_recent_cycles_and_keeps_baseline():
    ranking = load("forecast_regime_v1_ranking.csv")
    assert ranking.selected.sum() == 1
    assert ranking.loc[ranking.selected, "model"].iloc[0] == "baseline_only"
    assert not ranking.loc[ranking.model.ne("baseline_only"), "guardrail_pass"].any()
    manifest = json.loads((WAR / "forecast_regime_v1_manifest.json").read_text(encoding="utf-8"))
    assert manifest["selection_years"] == [2020, 2022, 2024]
    assert manifest["selected_model"] == "baseline_only"


def test_2026_views_reconcile_to_baseline_plus_declared_weight():
    forecast = load("forecast_regime_v1_2026.csv")
    assert len(forecast) == 96
    assert not forecast.duplicated(["forecast_view", "chamber", "district"]).any()
    assert set(forecast.forecast_view) == {"basic", "fundamentals_plus"}
    np.testing.assert_allclose(
        forecast.predicted_dem_margin,
        forecast.environment_baseline_margin + forecast.applied_gap_adjustment,
    )
    assert np.allclose(forecast.full_expected_gap, 0)
    assert np.allclose(forecast.applied_gap_adjustment, 0)


def test_recent_baseline_beats_every_challenger_on_mean_mae():
    ranking = load("forecast_regime_v1_ranking.csv").set_index("model")
    baseline = ranking.loc["baseline_only", "mean_mae_2020_2024"]
    assert ranking.drop(index="baseline_only").mean_mae_2020_2024.gt(baseline).all()
