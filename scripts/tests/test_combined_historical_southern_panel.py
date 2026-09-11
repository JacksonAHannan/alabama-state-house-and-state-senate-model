from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_combined_historical_southern_panel import strict_cycle_gate


def test_explicit_cycle_gates():
    assert strict_cycle_gate(pd.Series({"state": "MO", "year": 2000, "chamber": "house", "district": 1}))
    assert not strict_cycle_gate(pd.Series({"state": "MO", "year": 2014, "chamber": "house", "district": 1}))
    assert not strict_cycle_gate(pd.Series({"state": "GA", "year": 2016, "chamber": "senate", "district": 13}))
    assert not strict_cycle_gate(pd.Series({"state": "AR", "year": 2008, "chamber": "house", "district": 1}))


def test_combined_release_is_unique_and_additive():
    root = Path(__file__).resolve().parents[2]
    combined = pd.read_csv(root / "data/processed/forecast_calibration/historical_southern_combined_panel.csv", low_memory=False)
    heda = pd.read_csv(root / "data/processed/forecast_calibration/historical_southern_heda_panel.csv", low_memory=False)
    assert not combined.duplicated(["state", "year", "chamber", "district"]).any()
    assert len(combined) >= int(heda["model_eligible"].sum())
    assert combined["model_eligible"].eq(True).all()
    assert not combined["baseline_allocation_quality"].eq("partial_unresolved").any()
    oe = combined[combined["panel_source"].str.startswith("OpenElections")]
    assert oe["legislative_turnout_join_coverage"].ge(0.95).all()
