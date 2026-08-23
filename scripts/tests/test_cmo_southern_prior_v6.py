import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
WAR = ROOT / "data/processed/war"
KEYS = ["cycle", "chamber", "district"]


def load(name: str) -> pd.DataFrame:
    return pd.read_csv(WAR / name, low_memory=False)


def test_direct_cmo_is_unchanged_and_prior_excludes_alabama():
    old = load("cmo_v5_races.csv")
    new = load("cmo_v6_southern_races.csv")
    joined = old[KEYS + ["direct_cmo"]].merge(
        new[KEYS + ["direct_cmo"]], on=KEYS, suffixes=("_v5", "_v6"), validate="one_to_one")
    assert len(joined) == len(old) == len(new) == 509
    np.testing.assert_allclose(joined.direct_cmo_v5, joined.direct_cmo_v6, atol=1e-12)
    manifest = json.loads((WAR / "cmo_v6_southern_manifest.json").read_text(encoding="utf-8"))
    assert manifest["southern_training_excludes_alabama"] is True
    assert manifest["status"] == "validated_historical_decomposition"
    assert manifest["forecast_promotion_status"] == "rejected_modern_era_gate"
    assert {row["path"] for row in manifest["code_inputs"]} == {
        "scripts/rebuild_cmo_southern_prior_v6.py",
        "scripts/rebuild_cmo_candidate_quality_v5.py",
        "scripts/run_historical_southern_cmo_tournament.py",
    }
    assert new.southern_prior_training_rows.eq(2350).all()


def test_expectations_and_incumbency_decomposition_are_explicit():
    races = load("cmo_v6_southern_races.csv")
    required = ["southern_expected_gap", "southern_incumbent_neutral_gap",
                "generic_incumbency_gap", "southern_candidate_quality_residual"]
    assert races[required].notna().all().all()
    np.testing.assert_allclose(
        races.southern_candidate_quality_residual,
        races.direct_cmo - races.southern_expected_gap,
    )
    np.testing.assert_allclose(
        races.generic_incumbency_gap,
        races.southern_expected_gap - races.southern_incumbent_neutral_gap,
    )
    assert np.allclose(races.loc[races.incumbency_balance.eq(0), "generic_incumbency_gap"], 0)


def test_candidate_orientations_are_symmetric_and_total_value_is_a_separate_measure():
    candidates = load("cmo_v6_southern_candidates.csv")
    for column in ["candidate_direct_cmo", "candidate_southern_expected_gap", "candidate_quality_residual"]:
        paired = candidates.pivot(index=KEYS, columns="canonical_party", values=column)
        np.testing.assert_allclose(paired.D, -paired.R, atol=1e-9)
    assert candidates.candidate_total_electoral_value.notna().all()
    assert candidates.southern_candidate_quality_index.notna().all()


def test_external_prior_improves_all_era_average_but_fails_recent_gate():
    validation = load("cmo_v6_southern_validation.csv")
    means = validation.groupby("model").mae.mean()
    assert means["southern_portable_temporal"] < means["ticket_baseline_only"]
    recent = validation[validation.cycle.ge(2018)].groupby("model").mae.mean()
    assert recent["southern_portable_temporal"] > recent["ticket_baseline_only"]


def test_named_smell_tests_are_retained():
    cases = load("cmo_v6_southern_case_studies.csv")
    mike = cases[cases.normalized_candidate_name.eq("MIKE CURTIS")]
    boyd = cases[cases.canonical_name.str.contains("BARBARA.*BOYD|BOYD.*BARBARA", case=False, na=False)]
    assert set(mike.cycle) == {2010, 2014}
    assert mike.candidate_direct_cmo.gt(10).all()
    assert len(boyd) >= 4
