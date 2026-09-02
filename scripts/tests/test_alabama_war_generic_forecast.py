import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/processed/forecast_calibration"
PREFIX = "alabama_war_forecast_v1"


def test_forecast_combines_generic_ballot_with_war_structure():
    scenarios = pd.read_csv(OUT / f"{PREFIX}_2026_scenarios.csv")
    assert set(scenarios.scenario) == {
        "headline", "environment_dem_favorable", "environment_rep_favorable",
    }
    assert scenarios.groupby("scenario").size().eq(48).all()
    assert scenarios.candidate_war_adjustment.eq(0).all()
    assert scenarios.candidate_history_used.eq(False).all()
    assert scenarios.finance_used.eq(False).all()
    assert scenarios.generic_candidate_assumption.eq(True).all()
    np.testing.assert_allclose(
        scenarios.predicted_dem_margin,
        scenarios.environment_baseline_margin + scenarios.generic_structural_adjustment,
        atol=1e-10,
    )
    np.testing.assert_allclose(
        scenarios.generic_structural_adjustment,
        scenarios.war_structural_expected_gap,
        atol=1e-10,
    )
    np.testing.assert_allclose(
        scenarios.war_structural_expected_gap,
        scenarios.generic_downballot_lag + scenarios.incumbency_adjustment,
        atol=1e-10,
    )
    assert scenarios.generic_structural_adjustment.abs().gt(1e-8).any()
    assert scenarios.incumbency_adjustment.abs().gt(1e-8).any()
    assert scenarios.model_used.eq("generic_war_environment_adjusted").all()


def test_structural_war_is_selected_with_validation_warning():
    metrics = pd.read_csv(OUT / f"{PREFIX}_forward_metrics.csv").set_index("specification")
    assert metrics.loc["generic_war_structural", "mae"] > metrics.loc["generic_ballot_baseline", "mae"]
    manifest = json.loads((OUT / f"{PREFIX}_manifest.json").read_text(encoding="utf-8"))
    assert manifest["selected_specification"] == "generic_war_structural"
    assert manifest["configuration"]["structural_applied"] is True
    assert manifest["diagnostics"]["structural_improves_baseline_on_holdout"] is False
    assert manifest["configuration"]["incumbency_treatment"] == (
        "included_as_symmetric_race_condition_in_war_structure"
    )
    assert manifest["configuration"]["war_structural_specification"] == "decaying_lag"
    assert manifest["configuration"]["war_training_cutoff_rule"].startswith("cycle > 2016")
    assert "incumbency_balance" in manifest["configuration"]["design_features"]
    assert manifest["configuration"]["candidate_history_used"] is False
    assert manifest["configuration"]["finance_used"] is False
    forbidden = ("candidate", "war", "cmo", "history", "ideology", "fundrais", "receipt", "expenditure")
    assert all(not any(term in feature.lower() for term in forbidden) for feature in manifest["configuration"]["design_features"])


def test_forecast_manifest_hashes_outputs():
    manifest = json.loads((OUT / f"{PREFIX}_manifest.json").read_text(encoding="utf-8"))
    assert manifest["diagnostics"]["max_forecast_identity_error"] < 1e-10
    for record in manifest["outputs"]:
        path = ROOT / record["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]
