from __future__ import annotations

import numpy as np
import pandas as pd


RACES = "data/processed/war/cmo_v3_races.csv"
CANDIDATES = "data/processed/war/cmo_v3_candidates.csv"


def test_headline_cmo_has_auditable_arithmetic() -> None:
    races = pd.read_csv(RACES)
    expected = races.legislative_dem_margin - races.baseline_ensemble_margin
    assert np.allclose(races.headline_cmo, expected)


def test_candidate_scores_are_zero_sum() -> None:
    candidates = pd.read_csv(CANDIDATES)
    paired = candidates.pivot_table(index=["cycle", "chamber", "district"],
                                    columns="canonical_party",
                                    values="candidate_headline_cmo", aggfunc="first").dropna()
    assert np.allclose(paired.D + paired.R, 0)


def test_morrow_1998_hd18_is_not_context_extrapolation() -> None:
    candidates = pd.read_csv(CANDIDATES)
    row = candidates[(candidates.cycle.eq(1998)) & candidates.chamber.eq("house")
                     & candidates.district.eq(18) & candidates.canonical_party.eq("D")]
    assert len(row) == 1
    assert .4 < row.iloc[0].candidate_headline_cmo < .6


def test_context_residual_is_not_a_public_score() -> None:
    races = pd.read_csv(RACES)
    candidates = pd.read_csv(CANDIDATES)
    assert "context_cmo" not in races
    assert "candidate_context_cmo" not in candidates


def test_uncertainty_contains_headline_score() -> None:
    races = pd.read_csv(RACES)
    assert (races.headline_cmo_low < races.headline_cmo).all()
    assert (races.headline_cmo < races.headline_cmo_high).all()
