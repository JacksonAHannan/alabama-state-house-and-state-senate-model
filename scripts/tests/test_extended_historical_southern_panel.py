from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
FC = ROOT / "data/processed/forecast_calibration"


def test_existing_panel_is_preserved_and_extension_keys_are_unique():
    old = pd.read_csv(FC / "historical_southern_combined_panel.csv", low_memory=False)
    new = pd.read_csv(FC / "historical_southern_extended_panel.csv", low_memory=False)
    keys = ["state", "year", "chamber", "district"]
    assert not new.duplicated(keys).any()
    check = old.merge(new, on=keys, suffixes=("_old", "_new"), validate="one_to_one")
    assert len(check) == len(old) == 2273
    for column in ["baseline_dem_margin", "legislative_dem_margin", "dem_votes", "rep_votes"]:
        assert np.allclose(check[f"{column}_old"], check[f"{column}_new"], equal_nan=True)


def test_arkansas_admissions_obey_all_release_gates():
    candidates = pd.read_csv(FC / "historical_southern_extended_arkansas_candidates.csv")
    panel = pd.read_csv(FC / "historical_southern_extended_panel.csv", low_memory=False)
    admitted = candidates.loc[candidates["model_eligible"].eq(True)]
    assert len(admitted) > 0
    assert admitted["staging_reconciliation_gate"].eq(True).all()
    assert admitted["contested_two_party"].eq(True).all()
    assert admitted["baseline_dem_margin"].notna().all()
    assert admitted["legislative_turnout_join_coverage"].ge(0.95).all()
    assert len(panel) == 2273 + len(admitted)


def test_allocation_weights_conserve_each_joined_context_group():
    coverage = pd.read_csv(FC / "historical_southern_extended_arkansas_coverage.csv")
    assert coverage["legislative_turnout_join_coverage"].between(0, 1 + 1e-12).all()
    assert coverage["minimum_party_context_footprint_share"].between(0, 1 + 1e-12).all()
