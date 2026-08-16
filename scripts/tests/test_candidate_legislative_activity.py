from pathlib import Path

import pandas as pd

from scripts.build_candidate_legislative_activity import named_instrument_pattern


ROOT = Path(__file__).resolve().parents[2]


def test_amendment_bill_links_are_header_validated_before_position_inference():
    validation = pd.read_csv(
        ROOT / "data" / "processed" / "legislative"
        / "focal_amendment_bill_link_validation.csv"
    )
    assert set(validation.bill_link_status) <= {"matched", "mismatch", "no_explicit_reference"}
    assert validation.loc[validation.position_inference_allowed, "bill_link_status"].eq(
        "matched"
    ).all()
    positions = pd.read_csv(
        ROOT / "research" / "cmo_ideology"
        / "candidate_amendment_position_evidence.csv"
    )
    valid_ids = set(validation.loc[validation.position_inference_allowed, "amendment_id"])
    assert set(positions.amendment_id) <= valid_ids
RESEARCH = ROOT / "research" / "cmo_ideology"
DATA = ROOT / "data" / "processed" / "legislative"


def test_named_amendment_pattern_excludes_ways_and_means_committee():
    series = pd.Series([
        "House Ways and Means Education first Amendment Offered",
        "Senate Means Amendment Offered",
    ])
    matched = series.str.contains(named_instrument_pattern("Means"), case=False, regex=True)
    assert matched.tolist() == [False, True]


def test_activity_outputs_preserve_priority_position_distinction():
    sponsored = pd.read_csv(RESEARCH / "candidate_sponsored_bill_evidence.csv")
    amendments = pd.read_csv(RESEARCH / "candidate_attributed_amendments.csv")
    committee = pd.read_csv(RESEARCH / "candidate_sponsored_bill_committee_events.csv")
    assert sponsored.bill_id.nunique() == 3705
    assert amendments.amendment_id.nunique() == 72
    assert not committee.individual_member_action_observed.any()
    assert committee.inference_limit.notna().all()
    december_2010 = sponsored.loc[
        sponsored.election_cycle.eq(2010)
        & pd.to_datetime(sponsored.activity_date).gt(pd.Timestamp("2010-11-02"))
    ]
    assert not december_2010.empty
    assert december_2010.activity_timing.eq("post_election").all()
    assert amendments.activity_timing.eq("post_election").all()


def test_state_issue_long_matrix_includes_activity_without_fabricated_stance():
    matrix = pd.read_csv(RESEARCH / "candidate_state_issue_matrix_long.csv")
    expected = {
        "sponsored_bills_pre", "sponsored_bills_post",
        "attributed_amendments_pre", "attributed_amendments_post",
    }
    assert expected.issubset(matrix.columns)
    priority_only = matrix.loc[matrix.sponsored_bills_pre.gt(0) & ~matrix.documented]
    assert not priority_only.empty
    assert priority_only.stance_code.isna().all()


def test_human_coded_sponsorship_positions_remain_temporally_honest():
    evidence = pd.read_csv(RESEARCH / "candidate_sponsorship_position_evidence.csv")
    assert evidence.review_status.eq("reviewed").all()
    assert evidence.temporal_status.isin(["pre_election", "post_election"]).all()
    sponsored = pd.read_csv(RESEARCH / "candidate_sponsored_bill_evidence.csv")
    expected = sponsored[["person_id", "election_cycle", "bill_id", "activity_timing"]].drop_duplicates()
    checked = evidence.merge(
        expected,
        on=["person_id", "election_cycle", "bill_id"],
        how="left",
        validate="many_to_one",
    )
    assert checked.activity_timing.notna().all()
    mapped = checked.activity_timing.map({
        "pre_or_during_election": "pre_election",
        "post_election": "post_election",
    })
    assert checked.temporal_status.eq(mapped).all()


def test_sponsorship_review_texts_match_internal_bill_identity_and_content():
    validation = pd.read_csv(
        DATA / "sponsorship_bill_text_link_validation.csv"
    )
    queue = pd.read_csv(
        RESEARCH / "candidate_sponsorship_direction_review_queue.csv"
    )
    assert validation.bill_id.nunique() == queue.bill_id.nunique()
    assert validation.bill_text_link_status.eq("matched").all()
    assert validation.position_review_allowed.eq(True).all()
    repaired = validation.loc[validation.text_source_override_applied.eq(True)]
    assert set(repaired.bill_id) == {416049, 416076, 416092}
    assert repaired.official_source_url.str.contains("/2010FS/").all()
