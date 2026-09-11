import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
PANEL = ROOT / "data/processed/forecast_calibration/historical_southern_combined_panel.csv"
OUTPUT = ROOT / "data/processed/war/combined_historical_southern"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_combined_candidate_residuals_cover_every_strict_race_symmetrically():
    panel = pd.read_csv(PANEL)
    candidates = pd.read_csv(OUTPUT / "historical_southern_cmo_candidate_residuals.csv")
    eligible = panel.loc[panel["model_eligible"].eq(True)]

    assert len(eligible) == 2273
    assert len(candidates) == 2 * len(eligible)
    keys = ["state", "year", "chamber", "district", "party"]
    assert not candidates.duplicated(keys).any()

    paired = candidates.pivot(
        index=["state", "year", "chamber", "district"],
        columns="party",
        values="candidate_quality_residual",
    )
    assert paired.notna().all(axis=None)
    assert np.allclose(paired["D"], -paired["R"])


def test_combined_manifest_and_selection_reconcile():
    manifest_path = OUTPUT / "historical_southern_cmo_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    ranking = pd.read_csv(OUTPUT / "historical_southern_cmo_ranking.csv")
    predictions = pd.read_csv(OUTPUT / "historical_southern_cmo_predictions.csv")

    assert manifest["input"]["sha256"] == sha256(PANEL)
    assert manifest["row_counts"] == {
        "input": 2273,
        "predictions": len(predictions),
        "candidate_residuals": 4546,
    }
    assert ranking["selected"].sum() == 1
    selected = ranking.loc[ranking["selected"], "model"].iloc[0]
    assert selected == manifest["selected_model"] == "full_temporal"
    assert bool(ranking.loc[ranking["selected"], "forward_guardrail_pass"].iloc[0])

    for output in manifest["outputs"]:
        path = ROOT / output["path"]
        assert path.stat().st_size == output["bytes"]
        assert sha256(path) == output["sha256"]
