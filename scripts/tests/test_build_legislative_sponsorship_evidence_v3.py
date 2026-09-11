"""Network-free tests for the bill-sponsorship ontology-v3 evidence builder."""
from pathlib import Path

import pandas as pd

import build_legislative_sponsorship_evidence_v3 as spon
from ideology_ontology_v3 import validate_primitive

ROOT = Path(__file__).resolve().parents[2]
IDE = ROOT / "data" / "processed" / "ideology"
SPON = IDE / "candidate_legislative_sponsorship_evidence_v3.csv"
VOTE = IDE / "candidate_legislative_position_evidence_v3.csv"


def test_norm_id_strips_float_suffix():
    assert spon.norm_id("12485.0") == "12485"
    assert spon.norm_id("12485") == "12485"
    assert spon.norm_id("nan") == ""
    assert spon.norm_id("") == ""


def test_bill_admitted_pairs_are_valid_exact_ontology_pairs():
    bills = spon.bill_admitted_pairs()
    assert len(bills) > 0
    for admitted, session_year, bill_number in list(bills.values())[:100]:
        assert isinstance(session_year, int)
        for axis, pole, src_axis, src_pole, rule, confidence in admitted:
            validate_primitive(axis, pole)  # raises if invalid


def test_output_schema_matches_vote_channel():
    spon_cols = list(pd.read_csv(SPON, nrows=5).columns)
    vote_cols = list(pd.read_csv(VOTE, nrows=1).columns)
    assert spon_cols == vote_cols


def test_all_rows_are_weighted_sponsorship():
    df = pd.read_csv(SPON, low_memory=False)
    assert len(df) > 0
    assert (df.source_type == "bill_sponsorship").all()
    assert (df.evidence_weight == 1.2).all()
    assert (df.response_mode == "sponsorship").all()
    assert (df.position_value == 1.0).all()
    assert (df.candidate_stance == "support").all()
    assert df.evidence_id.is_unique


def test_all_pairs_validate_against_ontology():
    df = pd.read_csv(SPON, low_memory=False)
    for axis, pole in df[["primitive_axis", "policy_pole"]].drop_duplicates().itertuples(index=False):
        validate_primitive(axis, pole)
