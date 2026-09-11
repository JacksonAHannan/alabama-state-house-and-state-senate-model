import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "data/processed/war/extended_historical_southern"


def test_extended_residuals_cover_all_races_symmetrically():
    panel = pd.read_csv(ROOT / "data/processed/forecast_calibration/historical_southern_extended_panel.csv")
    candidates = pd.read_csv(OUTPUT / "historical_southern_cmo_candidate_residuals.csv")
    assert len(panel) == 2383
    assert len(candidates) == 4766
    keys = ["state", "year", "chamber", "district", "party"]
    assert not candidates.duplicated(keys).any()
    paired = candidates.pivot(index=keys[:-1], columns="party", values="candidate_quality_residual")
    assert np.allclose(paired["D"], -paired["R"])


def test_extended_selection_and_manifest_counts_reconcile():
    ranking = pd.read_csv(OUTPUT / "historical_southern_cmo_ranking.csv")
    manifest = json.loads((OUTPUT / "historical_southern_cmo_manifest.json").read_text(encoding="utf-8"))
    assert ranking["selected"].sum() == 1
    assert ranking.loc[ranking["selected"], "model"].iloc[0] == "portable_temporal"
    assert bool(ranking.loc[ranking["selected"], "forward_guardrail_pass"].iloc[0])
    assert manifest["selected_model"] == "portable_temporal"
    assert manifest["row_counts"] == {"input": 2383, "predictions": 31934, "candidate_residuals": 4766}
