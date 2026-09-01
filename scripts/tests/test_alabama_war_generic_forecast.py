import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/processed/forecast_calibration"
PREFIX = "alabama_war_forecast_v1"


def test_forecast_is_generic_ballot_and_zero_candidate_war():
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
    assert scenarios.generic_structural_adjustment.eq(0).all()
    assert scenarios.model_used.eq("generic_ballot_zero_war").all()


def test_failed_structural_candidate_is_not_promoted():
    metrics = pd.read_csv(OUT / f"{PREFIX}_forward_metrics.csv").set_index("specification")
    assert metrics.loc["generic_war_structural", "mae"] > metrics.loc["generic_ballot_baseline", "mae"]
    manifest = json.loads((OUT / f"{PREFIX}_manifest.json").read_text(encoding="utf-8"))
    assert manifest["selected_specification"] == "generic_ballot_baseline"
    assert manifest["configuration"]["structural_promoted"] is False
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
