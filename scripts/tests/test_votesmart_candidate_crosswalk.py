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
