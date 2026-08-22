from __future__ import annotations

import numpy as np
import pandas as pd

RACES = "data/processed/war/cmo_v4_races.csv"
CANDIDATES = "data/processed/war/cmo_v4_candidates.csv"


def test_war_arithmetic_reconciles() -> None:
    r = pd.read_csv(RACES)
    assert np.allclose(r.raw_ticket_gap, r.legislative_dem_margin - r.war_baseline_margin)
    expected = r.structural_expected_gap + r.demographic_adjustment + r.campaign_effort_adjustment
    assert np.allclose(r.predicted_structural_gap, expected)
    structural = (r.structural_base_adjustment + r.incumbency_adjustment
                  + r.lagged_partisanship_adjustment)
    assert np.allclose(r.structural_expected_gap, structural)
    assert np.allclose(r.war_cmo, r.raw_ticket_gap - r.predicted_structural_gap)


def test_primary_baseline_is_same_cycle_federal() -> None:
    r = pd.read_csv(RACES)
    primary = r[r.federal_primary]
    assert primary.war_baseline_source.eq("same_cycle_federal").all()
    assert len(primary) >= 400


def test_minor_adjustments_are_capped() -> None:
    r = pd.read_csv(RACES)
    assert r.demographic_adjustment.abs().max() <= 3
    assert r.campaign_effort_adjustment.abs().max() <= 2


def test_candidate_scores_are_zero_sum() -> None:
    c = pd.read_csv(CANDIDATES)
    paired = c.pivot_table(index=["cycle", "chamber", "district"], columns="canonical_party",
                           values="candidate_war_cmo", aggfunc="first").dropna()
    assert np.allclose(paired.D + paired.R, 0)


def test_ideology_is_not_a_model_feature() -> None:
    r = pd.read_csv(RACES)
    assert not any("ideolog" in col.lower() for col in r.columns)


def test_morrow_is_finite_and_decomposed() -> None:
    r = pd.read_csv(RACES)
    row = r[(r.cycle.eq(1998)) & r.chamber.eq("house") & r.district.eq(18)].squeeze()
    assert np.isfinite(row.war_cmo)
    assert abs(row.war_cmo) < 30
