from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
LEG = ROOT / "data" / "processed" / "legislative"


def test_every_archive_bill_has_one_terminal_frontier_disposition():
    bills = pd.read_csv(LEG / "legiscan_alabama_bills.csv", low_memory=False)
    ledger = pd.read_csv(LEG / "frontier_archive_bill_ledger.csv", low_memory=False)
    assert ledger.bill_id.is_unique
    assert set(ledger.bill_id) == set(bills.bill_id)
    assert ledger.terminal_disposition.fillna(False).all()
    assert ledger.archive_disposition.notna().all()


def test_candidate_vote_scoring_requires_a_reviewed_rollcall_bill():
    ledger = pd.read_csv(LEG / "frontier_archive_bill_ledger.csv", low_memory=False)
    eligible = ledger[ledger.candidate_vote_scoring_eligible]
    assert eligible.recorded_individual_rollcall.all()
    assert set(eligible.archive_disposition) <= {"map", "multi_axis"}
    no_vote = ledger[~ledger.recorded_individual_rollcall]
    assert no_vote.archive_disposition.eq("no_recorded_individual_rollcall").all()
    assert not no_vote.candidate_vote_scoring_eligible.any()


def test_ambiguous_rollcall_bills_are_explicitly_non_scoring():
    ledger = pd.read_csv(LEG / "frontier_archive_bill_ledger.csv", low_memory=False)
    unresolved = ledger[ledger.archive_disposition.eq("insufficient_text")]
    assert len(unresolved) == 2
    assert unresolved.text_available.all()
    assert not unresolved.candidate_vote_scoring_eligible.any()
