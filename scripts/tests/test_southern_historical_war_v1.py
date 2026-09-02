from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/processed/war/southern_historical_war_v1"


def test_southern_historical_war_release_contract() -> None:
    races = pd.read_csv(OUT / "race_war.csv", low_memory=False)
    candidates = pd.read_csv(OUT / "candidate_cycle_war.csv", low_memory=False)
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    assert len(races) == 3418
    assert len(candidates) == 6836
    assert races.state_code.nunique() == 14
    assert set(races.cycle) == {2016, 2018, 2019, 2020, 2022}
    assert not races.duplicated(["state_code", "cycle", "chamber", "district"]).any()
    assert manifest["diagnostics"]["backcast_races"] == 620
    np.testing.assert_allclose(
        races.war, races.raw_gap - races.fitted_structural_expected_gap, atol=1e-10
    )


def test_2016_is_backcast_and_later_scores_are_published_residuals() -> None:
    races = pd.read_csv(OUT / "race_war.csv", low_memory=False)
    assert races.loc[races.cycle.eq(2016), "scoring_scope"].eq(
        "post2016_southern_model_backcast"
    ).all()
    assert races.loc[races.cycle.gt(2016), "scoring_scope"].eq(
        "published_same_cycle_residual"
    ).all()
    published = pd.read_csv(
        ROOT / "data/processed/war/post2016_southern_war_v3/race_war.csv", low_memory=False
    )
    keys = ["state_code", "cycle", "chamber", "district"]
    check = races[races.cycle.gt(2016)].merge(
        published[keys + ["war"]], on=keys, validate="one_to_one", suffixes=("", "_published")
    )
    np.testing.assert_allclose(check.war, check.war_published, atol=1e-10)


def test_candidate_orientation_names_and_finance_missingness() -> None:
    races = pd.read_csv(OUT / "race_war.csv", low_memory=False)
    candidates = pd.read_csv(OUT / "candidate_cycle_war.csv", low_memory=False)
    paired = candidates.pivot(index="war_outcome_id", columns="canonical_party", values="candidate_cycle_war")
    np.testing.assert_allclose(paired.D + paired.R, 0.0, atol=1e-10)
    assert not candidates.candidate_name.str.fullmatch(r"[A-Z]{3}\d{2,3}[A-Z]{3,}", na=False).any()
    assert not candidates.candidate_name.str.contains("committee", case=False, na=False).any()
    assert not candidates.candidate_name.astype(str).str.strip().str.lower().isin({"", "nan", "none", "null"}).any()
    names = candidates.set_index(["state_code", "cycle", "chamber", "district", "canonical_party"])
    assert names.loc[("AL", 2022, "lower", 12, "D"), "candidate_name"] == "James C. Fields, Jr."
    assert names.loc[("AL", 2022, "lower", 27, "D"), "candidate_name"] == "Herb Neu"
    assert names.loc[("AL", 2022, "lower", 47, "D"), "candidate_name"] == "Christian Coleman"
    incomplete = races.finance_complete.eq(0)
    assert races.loc[incomplete, ["democratic_fundraising", "republican_fundraising", "log_fundraising_ratio_d_to_r"]].isna().all().all()
