import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
PANEL = ROOT / "data/processed/forecast_calibration/historical_southern_extended_v2_panel.csv"
OUTPUT = ROOT / "data/processed/war/extended_v2_historical_southern"


def test_v2_residuals_cover_all_races_symmetrically():
    panel = pd.read_csv(PANEL, low_memory=False)
    candidates = pd.read_csv(OUTPUT / "historical_southern_cmo_candidate_residuals.csv", low_memory=False)
    assert len(panel) == 2402
    assert len(candidates) == 4804
    keys = ["state", "year", "chamber", "district", "party"]
    assert not candidates.duplicated(keys).any()
    paired = candidates.pivot(index=keys[:-1], columns="party", values="candidate_quality_residual")
    assert np.allclose(paired["D"], -paired["R"])


def test_v2_selection_and_manifest_counts_reconcile():
    ranking = pd.read_csv(OUTPUT / "historical_southern_cmo_ranking.csv")
    manifest = json.loads((OUTPUT / "historical_southern_cmo_manifest.json").read_text(encoding="utf-8"))
    assert ranking["selected"].sum() == 1
    assert ranking.loc[ranking["selected"], "model"].iloc[0] == "portable_temporal"
    assert bool(ranking.loc[ranking["selected"], "forward_guardrail_pass"].iloc[0])
    assert manifest["selected_model"] == "portable_temporal"
    assert manifest["row_counts"] == {"input": 2402, "predictions": 32067, "candidate_residuals": 4804}


def test_v2_tennessee_rows_reach_selected_candidate_output():
    panel = pd.read_csv(PANEL, low_memory=False)
    candidates = pd.read_csv(OUTPUT / "historical_southern_cmo_candidate_residuals.csv", low_memory=False)
    tn_panel = panel.loc[panel["state"].eq("TN") & panel["year"].eq(1998)]
    tn_candidates = candidates.loc[candidates["state"].eq("TN") & candidates["year"].eq(1998)]
    assert len(tn_panel) == 19
    assert len(tn_candidates) == 38
    assert set(tn_panel[["chamber", "district"]].itertuples(index=False, name=None)) == set(
        tn_candidates[["chamber", "district"]].itertuples(index=False, name=None)
    )
