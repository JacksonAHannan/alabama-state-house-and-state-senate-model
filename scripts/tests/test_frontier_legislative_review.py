from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
MANUAL = ROOT / "data" / "manual" / "ideology" / "frontier_legislative_bill_adjudications.csv"
LEDGER = ROOT / "research" / "cmo_ideology" / "frontier_legislative_review" / "bill_review_ledger.csv"
FOLLOWUP = ROOT / "research" / "cmo_ideology" / "frontier_legislative_review" / "full_text_followup_queue.csv"


def test_frontier_bill_adjudications_are_unique_and_well_formed():
    rows = pd.read_csv(MANUAL)
    assert rows.bill_id.notna().all()
    assert not rows.bill_id.duplicated().any()
    assert set(rows.decision) <= {
        "map",
        "multi_axis",
        "mixed_no_scalar_direction",
        "procedural",
        "local_non_generalizable",
        "symbolic",
        "insufficient_text",
    }
    assert rows.confidence.isin(["low", "medium", "high"]).all()
    assert rows.rationale.fillna("").str.len().ge(40).all()


def test_scalar_frontier_decisions_have_aligned_axes_and_poles():
    rows = pd.read_csv(MANUAL)
    scalar = rows[rows.decision.isin(["map", "multi_axis"])]
    for row in scalar.itertuples():
        axes = str(row.primitive_axes).split(";")
        poles = str(row.policy_poles).split(";")
        assert len(axes) == len(poles), row.bill_id
        assert all(value.strip() for value in axes + poles)


def test_frontier_ledger_covers_the_complete_bill_archive():
    bills = pd.read_csv(ROOT / "data" / "processed" / "legislative" / "legiscan_alabama_bills.csv")
    ledger = pd.read_csv(LEDGER, low_memory=False)
    assert len(ledger) == len(bills)
    assert set(ledger.bill_id) == set(bills.bill_id)
    assert not ledger.bill_id.duplicated().any()


def test_low_confidence_and_insufficient_text_rows_enter_followup_queue():
    ledger = pd.read_csv(LEDGER, low_memory=False)
    followup = pd.read_csv(FOLLOWUP, low_memory=False)
    expected = ledger[
        ledger.frontier_review_status.eq("reviewed")
        & (
            ledger.frontier_confidence.eq("low")
            | ledger.frontier_decision.eq("insufficient_text")
        )
    ]
    assert set(followup.bill_id) == set(expected.bill_id)
    assert not followup.bill_id.duplicated().any()
    assert followup.followup_reason.isin(
        ["low_confidence_synopsis_judgment", "explicit_insufficient_text"]
    ).all()
    assert followup.full_text_available.eq(followup.documents_present.gt(0)).all()
