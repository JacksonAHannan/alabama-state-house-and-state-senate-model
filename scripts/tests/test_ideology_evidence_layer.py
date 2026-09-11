"""Fixture tests for the ideology evidence layer audit checker functions.

These tests exercise the pure checkers in
``scripts/audit_ideology_evidence_layer.py`` with tiny synthetic frames; they do
not read the repository data files and do not assert repository counts.
"""
from datetime import date

import audit_ideology_evidence_layer as audit


def test_general_election_date_is_tuesday_after_first_monday():
    assert audit.general_election_date(2010) == date(2010, 11, 2)
    assert audit.general_election_date(2018) == date(2018, 11, 6)
    assert audit.general_election_date(2022) == date(2022, 11, 8)
    assert audit.general_election_date(2022).weekday() == 1


def test_norm_id_and_parse_date():
    assert audit.norm_id("12485.0") == "12485"
    assert audit.norm_id("12485") == "12485"
    assert audit.norm_id("nan") == ""
    assert audit.norm_id("") == ""
    assert audit.parse_date("2010-03-04") == date(2010, 3, 4)
    assert audit.parse_date("2010-session-date-unavailable") is None
    assert audit.parse_date("") is None


def test_find_temporal_violations_detects_late_action_and_window_breach():
    rows = [
        {"election_cycle": 2018, "session_year": 2018, "effective_date": date(2018, 3, 1)},
        {"election_cycle": 2018, "session_year": 2018, "effective_date": date(2018, 12, 1)},
        {"election_cycle": 1998, "session_year": 2001, "effective_date": date(1998, 6, 1)},
        {"election_cycle": 2018, "session_year": 2015, "effective_date": None},
    ]
    violations = audit.find_temporal_violations(rows)
    reasons = sorted(item["reason"] for item in violations)
    assert reasons == ["action_after_general_election", "session_outside_cycle_window"]
    # The placeholder-only row inside the window is not a violation.
    assert all(item["row"]["election_cycle"] != 2018 or item["reason"] != "session_outside_cycle_window"
               for item in violations)


def test_find_temporal_violations_accepts_placeholder_within_window():
    rows = [{"election_cycle": 2010, "session_year": 2010, "effective_date": date(2010, 6, 1)}]
    assert audit.find_temporal_violations(rows) == []


def test_detect_double_count_matches_only_shared_candidate_bill_axis():
    vote_rows = [
        {"canonical_candidate_id": "C1", "source_record_id": "R1", "primitive_axis": "gun_access"},
        {"canonical_candidate_id": "C2", "source_record_id": "R2", "primitive_axis": "gun_access"},
    ]
    sponsorship_rows = [
        {"canonical_candidate_id": "C1", "source_record_id": "sponsorship:B1", "primitive_axis": "gun_access"},
        {"canonical_candidate_id": "C2", "source_record_id": "sponsorship:B9", "primitive_axis": "gun_access"},
    ]
    vote_bill = {"R1": "B1", "R2": "B2"}
    sponsorship_bill = {"sponsorship:B1": "B1", "sponsorship:B9": "B9"}
    result = audit.detect_double_count(vote_rows, sponsorship_rows, vote_bill, sponsorship_bill)
    assert result["shared_key_count"] == 1
    assert result["shared_keys"] == [("C1", "B1", "gun_access")]
    assert result["shared_candidate_bill_pairs"] == 1
    assert result["vote_rows_in_shared"] == 1
    assert result["sponsorship_rows_in_shared"] == 1


def test_detect_double_count_ignores_rows_without_a_bill():
    vote_rows = [{"canonical_candidate_id": "C1", "source_record_id": "MISSING", "primitive_axis": "gun_access"}]
    sponsorship_rows = [{"canonical_candidate_id": "C1", "source_record_id": "sponsorship:B1", "primitive_axis": "gun_access"}]
    result = audit.detect_double_count(vote_rows, sponsorship_rows, {}, {"sponsorship:B1": "B1"})
    assert result["shared_key_count"] == 0


def test_polarity_consistency_flags_mismatched_pole():
    vote_rows = [{"canonical_candidate_id": "C1", "source_record_id": "R1",
                  "primitive_axis": "gun_access", "policy_pole": "expand", "raw_answer": "Yea"}]
    sponsorship_rows = [{"canonical_candidate_id": "C1", "source_record_id": "sponsorship:B1",
                         "primitive_axis": "gun_access", "policy_pole": "restrict", "raw_answer": "sponsor"}]
    result = audit.polarity_consistency(vote_rows, sponsorship_rows, {"R1": "B1"}, {"sponsorship:B1": "B1"})
    assert result["shared_cells"] == 1
    assert result["mismatch_count"] == 1
    assert result["fraction"] == 0.0


def test_polarity_consistency_agrees_and_filters_by_answer():
    vote_rows = [{"canonical_candidate_id": "C1", "source_record_id": "R1",
                  "primitive_axis": "gun_access", "policy_pole": "expand", "raw_answer": "Yea"}]
    sponsorship_rows = [{"canonical_candidate_id": "C1", "source_record_id": "sponsorship:B1",
                         "primitive_axis": "gun_access", "policy_pole": "expand", "raw_answer": "sponsor"}]
    assert audit.polarity_consistency(vote_rows, sponsorship_rows, {"R1": "B1"},
                                      {"sponsorship:B1": "B1"})["fraction"] == 1.0
    # A Nay-only row no longer shares the cell once Yes votes are required.
    vote_rows[0]["raw_answer"] = "Nay"
    assert audit.polarity_consistency(vote_rows, sponsorship_rows, {"R1": "B1"},
                                      {"sponsorship:B1": "B1"}, vote_answer="Yea")["shared_cells"] == 0


def test_apply_min_evidence_requires_three_issues_and_two_families():
    universe = ["A", "B", "C", "D"]
    issue_rows = (
        [{"canonical_candidate_id": "A", "issue_score_available": True}] * 3
        + [{"canonical_candidate_id": "B", "issue_score_available": True}] * 2
        + [{"canonical_candidate_id": "C", "issue_score_available": True}] * 3
        + [{"canonical_candidate_id": "D", "issue_score_available": True}] * 3
        + [{"canonical_candidate_id": "D", "issue_score_available": False}]
    )
    family_rows = (
        [{"canonical_candidate_id": "A", "family_score_available": True}] * 2
        + [{"canonical_candidate_id": "B", "family_score_available": True}] * 2
        + [{"canonical_candidate_id": "C", "family_score_available": True}]
        + [{"canonical_candidate_id": "D", "family_score_available": False}] * 2
    )
    result = audit.apply_min_evidence(issue_rows, family_rows, universe)
    assert result["universe"] == 4
    assert result["meeting_three_issue_floor"] == 3
    assert result["meeting_two_family_floor"] == 2
    assert result["model_eligible"] == 1
    assert result["eligible_ids"] == ["A"]
    assert result["with_observed_profile"] == 4


def test_identity_cardinality_flags_same_cycle_collision_and_counts_repeats():
    rows = [
        {"people_id": "P1", "year": "2010", "canonical_candidate_id": "AL-2010-house-1-D-A"},
        {"people_id": "P1", "year": "2014", "canonical_candidate_id": "AL-2014-house-1-D-A"},
        {"people_id": "P2", "year": "2010", "canonical_candidate_id": "AL-2010-house-2-D-B"},
        {"people_id": "P2", "year": "2010", "canonical_candidate_id": "AL-2010-house-2-R-C"},
        {"people_id": "", "year": "2010", "canonical_candidate_id": "AL-2010-house-3-D-D"},
    ]
    result = audit.identity_cardinality(rows)
    assert result["distinct_people"] == 2          # the blank id is not an identity
    assert result["cardinality_violations"] == 1   # P2 maps to two candidates in 2010
    assert result["repeated_people"] == 1          # P1 spans two cycles
    assert result["candidate_cycles_held_by_repeated_people"] == 2
