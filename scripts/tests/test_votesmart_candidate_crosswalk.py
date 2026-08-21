import pandas as pd

from build_votesmart_candidate_crosswalk import build_crosswalk


def test_crosswalk_uses_year_chamber_district_and_party():
    canonical = pd.DataFrame([{
        "canonical_candidate_id": "C1", "person_id": "P1", "year": 1998,
        "chamber": "house", "district": 30, "party": "R", "ballot_name": "Blaine Galliher",
    }])
    roster = pd.DataFrame([
        {"election_year": 1998, "votesmart_candidate_id": 5646, "candidate": "Blaine Galliher",
         "chamber": "house", "district": 30, "party": "Republican"},
        {"election_year": 1998, "votesmart_candidate_id": 9999, "candidate": "Other Person",
         "chamber": "house", "district": 30, "party": "Democratic"},
    ])
    result = build_crosswalk(canonical, roster).iloc[0]
    assert result.accepted
    assert result.votesmart_candidate_id == 5646
    assert result.match_method == "same_race_party"


def test_1994_match_requires_exceptional_unique_name():
    canonical = pd.DataFrame([{
        "canonical_candidate_id": "C1", "person_id": "P1", "year": 1994,
        "chamber": "house", "district": 1, "party": "D", "ballot_name": "Jane Q. Doe",
    }])
    roster = pd.DataFrame([
        {"election_year": 1998, "votesmart_candidate_id": 12, "candidate": "Jane Q Doe",
         "chamber": "house", "district": 1, "party": "Democratic"},
        {"election_year": 1998, "votesmart_candidate_id": 13, "candidate": "Unrelated Person",
         "chamber": "house", "district": 2, "party": "Democratic"},
    ])
    result = build_crosswalk(canonical, roster).iloc[0]
    assert result.accepted
    assert result.match_method == "1994_unique_person_name"


def test_1994_match_propagates_verified_later_person_identity():
    canonical = pd.DataFrame([
        {"canonical_candidate_id": "C94", "person_id": "P1", "year": 1994,
         "chamber": "house", "district": 1, "party": "D", "ballot_name": "Doe"},
        {"canonical_candidate_id": "C98", "person_id": "P1", "year": 1998,
         "chamber": "house", "district": 1, "party": "D", "ballot_name": "Jane Doe"},
    ])
    roster = pd.DataFrame([
        {"election_year": 1998, "votesmart_candidate_id": 12, "candidate": "Jane Doe",
         "chamber": "house", "district": 1, "party": "Democratic"},
    ])
    result = build_crosswalk(canonical, roster).set_index("canonical_candidate_id")
    assert result.loc["C94", "accepted"]
    assert result.loc["C94", "votesmart_candidate_id"] == 12
    assert result.loc["C94", "match_method"] == "canonical_person_id_propagation"


def test_1994_match_does_not_propagate_ambiguous_surname_person_id():
    canonical = pd.DataFrame([
        {"canonical_candidate_id": "C94A", "person_id": "ALPERSON-DOE", "year": 1994,
         "chamber": "house", "district": 1, "party": "D", "ballot_name": "Doe"},
        {"canonical_candidate_id": "C94B", "person_id": "ALPERSON-DOE", "year": 1994,
         "chamber": "house", "district": 2, "party": "R", "ballot_name": "Doe"},
        {"canonical_candidate_id": "C98", "person_id": "ALPERSON-DOE", "year": 1998,
         "chamber": "house", "district": 1, "party": "D", "ballot_name": "Jane Doe"},
    ])
    roster = pd.DataFrame([
        {"election_year": 1998, "votesmart_candidate_id": 12, "candidate": "Jane Doe",
         "chamber": "house", "district": 1, "party": "Democratic"},
    ])
    result = build_crosswalk(canonical, roster).set_index("canonical_candidate_id")
    assert not result.loc["C94A", "accepted"]
    assert not result.loc["C94B", "accepted"]


def test_encoded_2022_ballot_identifier_uses_unique_race_party_slot():
    canonical = pd.DataFrame([{
        "canonical_candidate_id": "C22", "person_id": "P22", "year": 2022,
        "chamber": "house", "district": 1, "party": "R", "ballot_name": "GSL001RPET",
    }])
    roster = pd.DataFrame([{
        "election_year": 2022, "votesmart_candidate_id": 149977, "candidate": "Phillip Pettus",
        "chamber": "house", "district": 1, "party": "Republican",
    }])
    result = build_crosswalk(canonical, roster).iloc[0]
    assert result.accepted
    assert result.votesmart_candidate_id == 149977
    assert result.match_method == "unique_race_party_encoded_ballot_slot"
