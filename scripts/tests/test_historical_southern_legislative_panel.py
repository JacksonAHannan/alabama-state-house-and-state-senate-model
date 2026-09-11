from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_historical_southern_legislative_panel import aggregate_baselines, allocate_context


def fixture_frames():
    legislative = pd.DataFrame({
        "state": ["FL", "FL"], "year": [2010, 2010], "source_member": ["x", "x"],
        "source_row": [1, 1], "chamber": ["house", "house"], "district": [7, 8],
        "district_slot": [1, 2], "dem_votes": [30, 10], "rep_votes": [60, 0],
        "total_votes": [90, 10],
    })
    context = pd.DataFrame({
        "state": ["FL"], "year": [2010], "source_member": ["x"], "source_row": [1],
        "office": ["USS"], "dem_votes": [40], "rep_votes": [60], "total_votes": [100],
    })
    return legislative, context


def test_split_context_allocation_conserves_source_votes():
    legislative, context = fixture_frames()
    result = allocate_context(legislative, context)
    assert round(result["allocation_weight"].sum(), 10) == 1
    assert round(result["allocated_dem_votes"].sum(), 10) == 40
    assert round(result["allocated_rep_votes"].sum(), 10) == 60


def test_baseline_priority_prefers_presidential_then_senate_then_governor():
    legislative, context = fixture_frames()
    context = pd.concat([context.assign(office="GOV"), context.assign(office="USP")], ignore_index=True)
    result = aggregate_baselines(allocate_context(legislative, context))
    assert set(result["office"]) == {"USP"}


def test_unallocatable_split_is_carried_as_partial_not_silently_dropped():
    legislative, context = fixture_frames()
    legislative[["dem_votes", "rep_votes", "total_votes"]] = legislative[["dem_votes", "rep_votes", "total_votes"]].astype("Float64")
    legislative.loc[:, ["dem_votes", "rep_votes", "total_votes"]] = pd.NA
    allocated = allocate_context(legislative, context)
    result = aggregate_baselines(allocated)
    assert len(allocated) == 2
    assert not allocated["allocation_complete"].any()
    assert result.iloc[0]["incomplete_context_groups"] == 1
    assert result.iloc[0]["baseline_allocation_quality"] == "partial_unresolved"
    assert pd.isna(result.iloc[0]["baseline_dem_margin"])


def test_built_panel_has_unique_keys_and_preserves_missing_baselines():
    root = Path(__file__).resolve().parents[2]
    panel = pd.read_csv(root / "data/processed/forecast_calibration/historical_southern_heda_panel.csv")
    assert not panel.duplicated(["state", "year", "chamber", "district"]).any()
    assert panel["baseline_dem_margin"].isna().any()
    assert ((panel["baseline_allocation_quality"].isna()) == (panel["baseline_dem_margin"].isna())).all()
    assert not panel.loc[panel["model_eligible"], ["klarner_dem_votes", "klarner_rep_votes", "baseline_dem_margin"]].isna().any().any()
    assert not panel.loc[panel["model_eligible"], "baseline_allocation_quality"].eq("partial_unresolved").any()
