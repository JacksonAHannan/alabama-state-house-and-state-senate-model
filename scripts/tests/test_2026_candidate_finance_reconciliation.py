from pathlib import Path
import sys

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from reconcile_2026_candidate_finance import build, ordered_name, score_names


def test_last_first_normalization_and_middle_name_compatibility():
    assert ordered_name("Montgomery, Allison Taylor") == "ALLISON TAYLOR MONTGOMERY"
    score, method = score_names("Allison T Montgomery", "Montgomery, Allison Taylor")
    assert score >= 95
    assert method == "first_last_middle_compatible"


def test_reconciled_finance_is_roster_complete_and_unique():
    result, _ = build()
    roster = pd.read_csv(ROOT / "data/processed/war/2026_final_candidate_roster.csv")
    expected = roster[roster.party.isin(["D", "R"])][["cycle", "chamber", "district", "party", "candidate"]].drop_duplicates()
    assert len(result) == len(expected)
    assert not result.duplicated(["cycle", "chamber", "district", "party", "candidate"]).any()
    matched = result[result.state_candidate.notna()]
    assert not matched.duplicated(["chamber", "source_file", "source_row"]).any()


def test_known_false_zeros_are_recovered():
    result, _ = build()
    by_name = result.set_index("candidate")
    allison = by_name.loc["Allison T Montgomery"]
    assert allison.fundraising_total == 6257.20
    assert allison.expenditures == 3969.71
    assert allison.reconciliation_resolution == "recovered_positive_from_official_summary"
    assert by_name.loc["Scott Ortis"].fundraising_total == 846800.0
    assert by_name.loc["Brent Comer"].fundraising_total == 31235.99


def test_cycle_total_adds_nonoverlapping_2025_and_2026_components():
    result, _ = build()
    givhan = result[result.candidate.eq("Sam Givhan")].squeeze()
    assert givhan.fcpa_2025_fundraising_total == 268708.37
    assert givhan.state_2026_fundraising_total == 101801.47
    assert givhan.fundraising_total == pytest.approx(370509.84)
    assert givhan.finance_source == "fcpa_2025_plus_state_2026_08_14"


def test_missing_is_not_silently_zeroed():
    result, audit = build()
    unresolved = audit[audit.reconciliation_resolution.eq("unresolved_no_official_state_summary")]
    assert unresolved.finance_observation_status.isin(
        ["unverified_live_summary_zero", "not_observed_unknown_not_zero"]
    ).all()
    truly_missing = unresolved[unresolved.prior_aggregation_status.isna()]
    assert truly_missing.fundraising_total.isna().all()
