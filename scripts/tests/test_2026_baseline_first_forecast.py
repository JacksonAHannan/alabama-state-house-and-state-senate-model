from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
WAR = ROOT / "data" / "processed" / "war"


def test_legacy_forecast_is_archived():
    assert (WAR / "2026_prospective_features_and_forecast_legacy_core_20260815.csv").exists()


def test_headline_uses_poll_adjusted_baseline_when_layers_fail_gate():
    forecast = pd.read_csv(WAR / "2026_prospective_features_and_forecast.csv")
    assert forecast.selected_specification.eq("poll_adjusted_direct_baseline").all()
    assert (forecast.predicted_dem_margin - forecast.poll_adjusted_dem_margin).abs().max() < 1e-9


def test_sd2_smell_test_and_decomposition():
    d = pd.read_csv(WAR / "2026_forecast_decomposition.csv")
    row = d[(d.chamber.eq("senate")) & (d.district.eq(2))].iloc[0]
    assert row.structural_2024_pres_margin < 0
    assert row.environment_adjustment > 0
    assert row.predicted_dem_margin > 0
    assert row.incumbency_adjustment == 0


def test_only_baseline_passes_declared_promotion_gate():
    result = pd.read_csv(WAR / "2026_residual_layer_backtest_summary.csv")
    selected = set(result.loc[result.promoted, "specification"])
    assert selected == {"baseline"}


def test_current_state_fundraising_reaches_forecast_features():
    forecast = pd.read_csv(WAR / "2026_prospective_features_and_forecast.csv")
    assert "scenario_finance_scenario_adjustment" in forecast
    assert forecast.ftm_finance_complete.sum() > 0
    observed = forecast[forecast.ftm_finance_complete.eq(1)]
    assert observed.log_fundraising_ratio_d_to_r.notna().all()


def test_federal_realign_specification_is_forward_tested():
    result = pd.read_csv(WAR / "2026_residual_layer_backtest_summary.csv")
    assert "federal_realign_finance" in set(result.specification)
    assert result.loc[result.specification.eq("federal_realign_finance"), "forward_cycles"].iloc[0] >= 2


def test_simulation_probabilities_and_intervals_are_valid():
    forecast = pd.read_csv(WAR / "2026_prospective_features_and_forecast.csv")
    assert forecast.dem_win_probability.between(0, 1).all()
    assert (forecast.margin_80_low <= forecast.predicted_dem_margin).all()
    assert (forecast.predicted_dem_margin <= forecast.margin_80_high).all()
