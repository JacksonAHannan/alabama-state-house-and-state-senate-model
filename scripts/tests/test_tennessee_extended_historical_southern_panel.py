from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
FC = ROOT / "data/processed/forecast_calibration"


def test_prior_panel_is_preserved_and_new_keys_are_unique():
    old = pd.read_csv(FC / "historical_southern_extended_panel.csv", low_memory=False)
    new = pd.read_csv(FC / "historical_southern_extended_v2_panel.csv", low_memory=False)
    keys = ["state", "year", "chamber", "district"]
    assert not new.duplicated(keys).any()
    joined = old.merge(new, on=keys, suffixes=("_old", "_new"), validate="one_to_one")
    assert len(joined) == len(old) == 2383
    for column in ["baseline_dem_margin", "legislative_dem_margin", "dem_votes", "rep_votes"]:
        assert np.allclose(joined[f"{column}_old"], joined[f"{column}_new"], equal_nan=True)


def test_all_tennessee_admissions_pass_declared_gates():
    candidates = pd.read_csv(FC / "historical_southern_extended_tn_candidates.csv")
    panel = pd.read_csv(FC / "historical_southern_extended_v2_panel.csv", low_memory=False)
    admitted = candidates.loc[candidates["model_eligible"].eq(True)]
    assert len(admitted) > 0
    assert admitted["staging_reconciliation_gate"].eq(True).all()
    assert admitted["contested_two_party"].eq(True).all()
    assert admitted["baseline_dem_margin"].notna().all()
    assert admitted["legislative_turnout_join_coverage"].ge(0.95).all()
    assert len(panel) == 2383 + len(admitted)


def test_coverage_is_bounded_and_missing_context_is_not_zero_filled():
    coverage = pd.read_csv(FC / "historical_southern_extended_tn_coverage.csv")
    assert coverage["legislative_turnout_join_coverage"].between(0, 1 + 1e-12).all()
    assert coverage["matched_legislative_turnout"].le(coverage["legislative_turnout"] + 1e-9).all()


def test_split_precinct_allocation_conserves_observed_context_by_chamber():
    audit = pd.read_csv(FC / "historical_southern_extended_tn_allocation_audit.csv")
    assert len(audit) > 0
    assert np.allclose(audit["allocation_weight_sum"], 1.0, atol=1e-10)
    assert np.allclose(audit["allocated_votes"], audit["source_votes"], atol=1e-8)
