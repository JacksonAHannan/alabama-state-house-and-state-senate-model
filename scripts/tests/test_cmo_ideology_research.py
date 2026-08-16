import pandas as pd
from pathlib import Path
import re

from scripts.analyze_cmo_ideology_research import mark_temporal_eligibility
from scripts.build_cmo_ideology_blind_review import REVIEW_DIMENSIONS, stable_anonymous_case_id


def test_temporal_eligibility_excludes_later_and_retrospective_evidence():
    evidence = pd.DataFrame({
        "election_cycle": [2014, 2014, 2014, 2014],
        "evidence_date": ["2014-10-01", "2015-01-01", "2014-10-01", "bad-date"],
        "review_status": ["verified", "verified", "retrospective_profile", "verified"],
    })

    result = mark_temporal_eligibility(evidence)

    assert result.temporally_eligible.tolist() == [True, False, False, False]


def test_blind_case_ids_are_stable_opaque_and_cycle_specific():
    first = stable_anonymous_case_id("ALPERSON-EXAMPLE", 2014)

    assert first == stable_anonymous_case_id("ALPERSON-EXAMPLE", 2014)
    assert first != stable_anonymous_case_id("ALPERSON-EXAMPLE", 2018)
    assert first.startswith("CASE-")
    assert "EXAMPLE" not in first


def test_evidence_does_not_split_same_named_case_across_person_ids():
    root = Path(__file__).resolve().parents[2]
    evidence = pd.read_csv(root / "research" / "cmo_ideology" / "evidence_ledger.csv")
    ids_per_case = evidence.groupby(["candidate", "election_cycle"]).person_id.nunique()

    assert ids_per_case.max() == 1


def test_pre_election_other_chamber_service_is_not_labeled_post_election():
    root = Path(__file__).resolve().parents[2]
    matches = pd.read_csv(root / "research" / "cmo_ideology" / "shor_mccarty_matches.csv")
    beasley = matches.loc[matches.person_id.eq("ALPERSON-BILLY-BEASLEY")].iloc[0]

    assert bool(beasley.served_in_either_chamber_by_election)
    assert not bool(beasley.served_in_chamber_by_election)
    assert beasley.temporal_use == "pre_election_other_chamber_service_available"


def test_pending_blind_review_is_identity_free_and_excludes_completed_decisions():
    root = Path(__file__).resolve().parents[2]
    pending = pd.read_csv(root / "research" / "cmo_ideology" / "blind_review_pending.csv")
    decisions = pd.read_csv(root / "research" / "cmo_ideology" / "blind_review_decisions.csv")

    assert "candidate" not in pending.columns
    assert "person_id" not in pending.columns
    assert "source_urls" not in pending.columns
    assert set(pending.dimension).issubset(REVIEW_DIMENSIONS)
    pending_keys = set(zip(pending.anonymous_case_id, pending.dimension))
    decided_keys = set(zip(decisions.anonymous_case_id, decisions.dimension))
    assert pending_keys.isdisjoint(decided_keys)

    ledger = pd.read_csv(root / "research" / "cmo_ideology" / "evidence_ledger.csv")
    pending_text = " ".join(pending.evidence_summary.fillna("").astype(str)).lower()
    for candidate in ledger.candidate.dropna().astype(str).unique():
        tokens = re.findall(r"[A-Za-z']+", candidate.lower())
        for token in tokens:
            token = token.strip("'")
            if len(token) >= 4:
                assert not re.search(rf"\b{re.escape(token)}\b", pending_text)
