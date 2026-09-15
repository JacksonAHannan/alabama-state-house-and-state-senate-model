"""Contract tests for the 2026 candidate-history carry-forward.

The estimator is new, so these pin the properties that make it defensible: it is
estimated from repeat candidates rather than assumed, it never invents an
identity match, it refuses to carry a result older than the evidence supports,
and a rematch is not counted twice.
"""
import json

import numpy as np
import pandas as pd
import pytest

from scripts import build_forecast_candidate_history as history

OUT = history.OUT


@pytest.fixture(scope="module")
def manifest():
    return json.loads((OUT / f"{history.PREFIX}_manifest.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def roster():
    return pd.read_csv(OUT / f"{history.PREFIX}.csv")


def test_persistence_is_estimated_from_repeat_candidates(manifest):
    fit = manifest["fit"]
    assert 0.0 < fit["persistence"] < 1.0, "a candidate keeps part, not all, of their prior WAR"
    assert abs(fit["persistence_t"]) > 2.0
    assert fit["pairs"] > 1000 and fit["candidates"] > 500
    assert manifest["standard_errors"] == "clustered by candidate identity"


def test_decay_is_applied_only_when_the_data_support_it(manifest):
    fit = manifest["fit"]
    assert fit["decay_supported"] is False
    plain = history.expected_carry(fit, pd.Series([10.0, 10.0]), pd.Series([2.0, 6.0]))
    assert plain.iloc[0] == pytest.approx(plain.iloc[1]), "unsupported decay must not be applied"
    supported = dict(fit, decay_supported=True, decay_per_year=-0.05)
    decayed = history.expected_carry(supported, pd.Series([10.0, 10.0]), pd.Series([2.0, 6.0]))
    assert decayed.iloc[1] < decayed.iloc[0]


def test_results_older_than_the_carry_limit_do_not_move_the_forecast(roster, manifest):
    limit = manifest["coverage"]["carry_limit_years"]
    stale = roster[roster.history_available & roster.years_elapsed.gt(limit)]
    assert not stale.empty, "the roster does contain stale matches, which must stay visible"
    assert stale.expected_candidate_effect.eq(0).all()
    assert stale.history_status.eq("history_older_than_carry_limit_encoded_as_zero").all()
    assert not stale.carry_applied.any()
    carried = roster[roster.carry_applied]
    assert carried.years_elapsed.le(limit).all()
    assert carried.expected_candidate_effect.abs().gt(0).any()


def test_identity_matches_are_evidence_based_never_forced(roster, manifest):
    methods = set(roster.match_method)
    assert methods <= {"verified_prior_winner_crosswalk", "exact_unique_normalized_name",
                       "ambiguous_name_left_unmatched", "no_prior_alabama_race"}
    assert manifest["identity_matching"]["verified_prior_winner_crosswalk"] > 0
    unmatched = roster[roster.match_method.isin({"ambiguous_name_left_unmatched", "no_prior_alabama_race"})]
    assert unmatched.person_id.isna().all()
    assert unmatched.expected_candidate_effect.eq(0).all()


def test_a_rematch_counts_one_race_residual_once():
    """Both candidates' prior WAR values are the same residual with opposite signs."""
    rematch = pd.DataFrame({
        "chamber": ["house"] * 2, "district": [40] * 2, "party": ["D", "R"],
        "expected_candidate_effect": [-0.26, 0.26],
        "last_prior_race": ["2022|house|40", "2022|house|40"],
    })
    adjusted = history.race_adjustments(rematch, ["chamber", "district"])
    assert bool(adjusted.rematch_deduplicated.iloc[0])
    assert adjusted.candidate_war_adjustment.iloc[0] == pytest.approx(-0.26)

    distinct = rematch.assign(last_prior_race=["2022|house|40", "2018|house|12"])
    adjusted = history.race_adjustments(distinct, ["chamber", "district"])
    assert not bool(adjusted.rematch_deduplicated.iloc[0])
    assert adjusted.candidate_war_adjustment.iloc[0] == pytest.approx(-0.52)


def test_race_adjustment_is_oriented_to_the_democratic_margin():
    frame = pd.DataFrame({
        "chamber": ["senate"] * 2, "district": [6] * 2, "party": ["D", "R"],
        "expected_candidate_effect": [3.0, -5.0],
        "last_prior_race": ["2022|senate|6", "2018|senate|6"],
    })
    adjusted = history.race_adjustments(frame, ["chamber", "district"])
    assert adjusted.candidate_war_adjustment.iloc[0] == pytest.approx(8.0)


def test_holdout_uses_only_evidence_from_before_the_tested_cycle():
    pairs = history.repeat_pairs(training_before=2022)
    assert pairs.cycle.lt(2022).all()
    fit = history.fit_persistence(pairs)
    assert fit["decay_estimable"] is False, "a single-gap window cannot identify decay"
    assert fit["decay_per_year"] is None and fit["decay_t"] is None
    assert 0.0 < fit["persistence"] < 1.0
    adjustments = history.holdout_race_adjustments(2022, fit, max(fit["observed_year_gaps"]) + 2)
    assert adjustments.candidate_war_adjustment.abs().gt(0).any()
    assert np.isfinite(adjustments.candidate_war_adjustment).all()
