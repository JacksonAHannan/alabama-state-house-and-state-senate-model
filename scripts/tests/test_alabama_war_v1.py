import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/processed/war/alabama_war_v1"


def test_alabama_war_is_complete_residual_filter():
    races = pd.read_csv(OUT / "race_war.csv", low_memory=False)
    candidates = pd.read_csv(OUT / "candidate_cycle_war.csv", low_memory=False)
    assert len(races) == 97
    assert len(candidates) == 194
    assert races.state_code.eq("AL").all()
    assert set(races.cycle) == {2018, 2022}
    assert not races.duplicated(["cycle", "chamber", "district"]).any()
    np.testing.assert_allclose(races.war, races.raw_gap - races.fitted_structural_expected_gap, atol=1e-10)
    oriented = candidates.pivot(
        index=["cycle", "chamber", "district"], columns="canonical_party", values="candidate_cycle_war"
    )
    np.testing.assert_allclose(oriented.D, -oriented.R, atol=1e-10)
    assert not {"candidate_war", "selected_penalty", "candidate_war_differential"}.intersection(candidates.columns)


def test_grimsley_is_unpooled_race_residual():
    races = pd.read_csv(OUT / "race_war.csv")
    candidates = pd.read_csv(OUT / "candidate_cycle_war.csv")
    grimsley_2018 = candidates[
        candidates.candidate_name.eq("Dexter Grimsley") & candidates.canonical_party.eq("D")
    ].squeeze()
    race_2018 = races[
        races.cycle.eq(2018) & races.chamber.eq("lower") & races.district.eq(85)
    ].squeeze()
    race_2022 = races[
        races.cycle.eq(2022) & races.chamber.eq("lower") & races.district.eq(85)
    ].squeeze()
    assert abs(grimsley_2018.candidate_cycle_war - race_2018.war) < 1e-10
    assert grimsley_2018.score_identification == "race_differential_party_orientation"
    assert race_2022.dem_incumbent == 1
    assert race_2022.rep_incumbent == 0
    assert abs(race_2022.war - (race_2022.raw_gap - race_2022.fitted_structural_expected_gap)) < 1e-10
    assert 18 < race_2022.war < 21


def test_alabama_war_manifest_hashes_outputs():
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["configuration"]["war_definition"] == "raw_gap - fitted_structural_expected_gap"
    assert manifest["configuration"]["candidate_pooling"] is False
    assert manifest["diagnostics"]["race_rows"] == 97
    for record in manifest["outputs"]:
        path = ROOT / record["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]
