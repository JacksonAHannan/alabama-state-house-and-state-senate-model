from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]


def read(relative):
    return pd.read_csv(ROOT / relative, dtype=str).fillna("")


def test_candidate_outputs_share_authoritative_universe():
    canonical = read("data/processed/elections/canonical_cmo_candidates.csv")
    expected = set(canonical.canonical_candidate_id)
    assert len(canonical) == len(expected)
    for relative in [
        "data/processed/elections/canonical_cmo_candidates_with_votesmart.csv",
        "data/processed/elections/canonical_cmo_candidates_with_ideology_v3.csv",
        "data/processed/ideology/candidate_ideology_full_universe.csv",
        "data/processed/ideology/votesmart_candidate_crosswalk_resolved.csv",
    ]:
        frame = read(relative)
        assert len(frame) == len(expected)
        assert set(frame.canonical_candidate_id) == expected


def test_matched_evidence_has_canonical_ids_and_unique_profiles():
    canonical = read("data/processed/elections/canonical_cmo_candidates.csv")
    expected = set(canonical.canonical_candidate_id)
    evidence = read("data/processed/ideology/candidate_position_evidence_v3_all_sources.csv")
    positions = read("data/processed/ideology/candidate_issue_valence_v3.csv")
    families = read("data/processed/ideology/candidate_family_valence_v3_all_sources.csv")
    assert evidence.canonical_candidate_id.ne("").all()
    assert set(evidence.canonical_candidate_id) <= expected
    assert not positions.duplicated(["canonical_candidate_id", "primitive_axis"]).any()
    assert not families.duplicated(["canonical_candidate_id", "family"]).any()


def test_legislative_and_votesmart_identities_are_one_to_one_within_cycle():
    legislative = read("data/processed/ideology/candidate_ideology_full_universe.csv")
    assigned = legislative[legislative.member_source_id.ne("")]
    assert not assigned.duplicated(["year", "member_source_id"]).any()
    crosswalk = read("data/processed/ideology/votesmart_candidate_crosswalk_resolved.csv")
    accepted = crosswalk[crosswalk.accepted.str.lower().eq("true")]
    assert not accepted.duplicated(["election_year", "votesmart_candidate_id"]).any()


def test_unmatched_evidence_is_quarantined():
    unmatched = read("data/processed/ideology/candidate_position_evidence_v3_unmatched.csv")
    assert unmatched.canonical_candidate_id.eq("").all()
