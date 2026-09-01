from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/processed/war/alabama_historical_war_v1"
PUBLISHED = ROOT / "data/processed/war/alabama_war_v1"
KEYS = ["cycle", "chamber", "district"]


def load(name: str) -> pd.DataFrame:
    return pd.read_csv(OUT / name, low_memory=False)


def test_historical_coverage_and_arithmetic() -> None:
    races = load("race_war.csv")
    candidates = load("candidate_cycle_war.csv")
    assert len(races) == 509
    assert len(candidates) == 1018
    assert set(races.cycle) == {1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022}
    assert not races.duplicated(KEYS).any()
    assert not candidates.duplicated(KEYS + ["canonical_party"]).any()
    np.testing.assert_allclose(
        races.war, races.raw_gap - races.fitted_structural_expected_gap, atol=1e-9
    )
    paired = candidates.pivot(index=KEYS, columns="canonical_party", values="candidate_cycle_war")
    np.testing.assert_allclose(paired.D, -paired.R, atol=1e-9)


def test_pre2016_scores_are_modern_model_backcasts() -> None:
    races = load("race_war.csv")
    historical = races[races.cycle.le(2014)]
    assert len(historical) == 412
    assert historical.scoring_scope.eq("post2016_southern_model_backcast").all()
    np.testing.assert_allclose(
        historical.fitted_structural_expected_gap,
        historical.modern_backcast_structural_expected_gap,
        atol=1e-12,
    )
    source = (ROOT / "scripts/build_alabama_historical_war_v1.py").read_text(encoding="utf-8")
    assert 'SPECIFICATION = "decaying_lag"' in source
    assert "ALPHA = 100.0" in source
    assert "modern.cycle.gt(2016).all()" in source


def test_2018_and_2022_exactly_preserve_published_alabama_war() -> None:
    historical = load("race_war.csv")
    current = pd.read_csv(PUBLISHED / "race_war.csv", low_memory=False)
    current["chamber"] = current.chamber.map({"lower": "house", "upper": "senate"})
    joined = historical[historical.cycle.gt(2016)].merge(
        current[KEYS + ["war", "fitted_structural_expected_gap"]],
        on=KEYS,
        suffixes=("_historical", "_published"),
        validate="one_to_one",
    )
    assert len(joined) == 97
    np.testing.assert_allclose(joined.war_historical, joined.war_published, atol=1e-12)
    np.testing.assert_allclose(
        joined.fitted_structural_expected_gap_historical,
        joined.fitted_structural_expected_gap_published,
        atol=1e-12,
    )
    assert historical.loc[
        historical.cycle.gt(2016), "scoring_scope"
    ].eq("published_same_cycle_residual").all()


def test_candidate_display_names_cannot_come_from_finance_committees() -> None:
    candidates = load("candidate_cycle_war.csv")
    assert candidates.display_name_source.eq("canonical_alabama_election_candidate").all()
    committee = re.compile(
        r"committee|campaign|friends of|\bfor (?:house|senate|representative)\b|\bpac\b",
        re.IGNORECASE,
    )
    assert not candidates.candidate_name.astype(str).str.contains(committee, na=False).any()
    source = (ROOT / "scripts/build_alabama_historical_war_v1.py").read_text(encoding="utf-8")
    assert "provider_candidate_name" not in source
    assert "committee_id" not in source


def test_manifest_records_extrapolation_and_no_pooling_or_finance() -> None:
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["configuration"]["training_cutoff_rule"] == "cycle > 2016"
    assert manifest["configuration"]["candidate_pooling"] is False
    assert manifest["configuration"]["finance_in_war"] is False
    assert manifest["configuration"]["committee_names_allowed"] is False
    assert manifest["diagnostics"]["race_rows"] == 509
    assert manifest["diagnostics"]["committee_like_candidate_names"] == 0
    assert manifest["status"] == "validated_historical_backcast_with_extrapolation_warning"
