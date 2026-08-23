import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/processed/forecast_calibration"


def load(name: str) -> pd.DataFrame:
    return pd.read_csv(OUT / name, low_memory=False)


def test_all_eligible_2024_races_and_candidates_are_preserved():
    races = load("southern_2024_incumbency_races.csv")
    candidates = load("southern_2024_incumbency_candidates.csv")
    assert len(races) == 335
    assert len(candidates) == 670
    assert not races.duplicated(["state", "year", "chamber", "district"]).any()
    assert candidates.groupby(["state", "year", "chamber", "district"]).party.nunique().eq(2).all()


def test_staggered_chambers_use_2020_and_2022_winners():
    winners = load("southern_2022_winner_roster.csv")
    assert set(winners.prior_year) == {2020, 2022}
    tn_upper = load("southern_2024_incumbency_races.csv").query("state == 'TN' and chamber == 'upper'")
    assert tn_upper.incumbency_model_ready.all()
    assert tn_upper.incumbency_status.eq("incumbent_running").sum() == 8


def test_ambiguous_names_remain_missing_and_conflicts_do_not_pass():
    candidates = load("southern_2024_incumbency_candidates.csv")
    races = load("southern_2024_incumbency_races.csv")
    ambiguous = candidates.match_method.str.startswith("ambiguous")
    assert candidates.loc[ambiguous, "incumbent"].isna().all()
    assert races.loc[~races.incumbency_model_ready, "incumbency_balance"].isna().all()
    ready = races.loc[races.incumbency_model_ready]
    assert ready.incumbency_balance.isin([-1, 0, 1]).all()
    assert not (ready.dem_incumbent.astype(bool) & ready.rep_incumbent.astype(bool)).any()


def test_coverage_is_high_and_party_switch_requires_full_name_evidence():
    races = load("southern_2024_incumbency_races.csv")
    candidates = load("southern_2024_incumbency_candidates.csv")
    assert races.incumbency_model_ready.sum() == 323
    switches = candidates.loc[candidates.party_switch]
    assert len(switches) == 1
    assert switches.candidate.str.contains("MAINOR", case=False).all()
    assert ~switches.match_method.str.contains("surname").any()


def test_manifest_hashes_declared_outputs():
    manifest = json.loads((OUT / "southern_2024_incumbency_manifest.json").read_text())
    assert manifest["status"] == "staging"
    assert len(manifest["inputs"]) == 3
    assert {row["rows"] for row in manifest["outputs"]} >= {335, 670}
