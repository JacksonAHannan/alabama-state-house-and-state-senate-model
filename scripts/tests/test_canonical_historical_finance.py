from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from build_canonical_historical_finance import SMOOTHING_DOLLARS, build


def test_canonical_finance_preserves_unknowns_and_observed_zeros() -> None:
    candidates, races, coverage = build()
    assert len(races) == 509
    assert int(races.canonical_finance_complete.sum()) == 352
    assert candidates.loc[candidates.finance_observation_status.eq("unknown_unmatched"), "total_fundraising"].isna().all()
    zeros = candidates.finance_observation_status.eq("observed_zero")
    assert zeros.any()
    assert candidates.loc[zeros, "total_fundraising"].eq(0).all()
    assert set(coverage.cycle) == {1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022}


def test_race_ratio_uses_declared_smoothing_only_when_complete() -> None:
    _, races, _ = build()
    complete = races.canonical_finance_complete.eq(1)
    expected = ((races.dem_fundraising + SMOOTHING_DOLLARS) /
                (races.rep_fundraising + SMOOTHING_DOLLARS)).map(__import__("math").log)
    pd.testing.assert_series_equal(
        races.loc[complete, "canonical_log_fundraising_ratio_d_to_r"].reset_index(drop=True),
        expected.loc[complete].reset_index(drop=True), check_names=False,
    )
    assert races.loc[~complete, "canonical_log_fundraising_ratio_d_to_r"].isna().all()
