from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "research" / "cmo_ideology"


def test_vote_profile_outputs_cover_reviewed_evidence_and_full_cohort():
    evidence = pd.read_csv(RESEARCH / "candidate_rollcall_position_evidence.csv").drop_duplicates(
        ["person_id", "roll_call_id", "human_issue_code"], keep="last"
    )
    summary = pd.read_csv(RESEARCH / "candidate_vote_issue_summary.csv")
    cohort = pd.read_csv(RESEARCH / "candidate_cohort.csv")
    report = (RESEARCH / "CANDIDATE_VOTE_ISSUE_PROFILES.md").read_text(encoding="utf-8")

    assert summary.reviewed_vote_records.sum() == len(evidence)
    assert summary.person_id.nunique() == evidence.person_id.nunique()
    assert set(summary.issue) == set(evidence.human_issue_code)
    assert sum(line.startswith("### ") and not line.startswith("#### ")
               for line in report.splitlines()) == len(cohort)
    assert "would affirms" not in report
    assert "would prohibits" not in report
    assert "No reviewed roll-call evidence is available" in report


def test_every_profile_vote_has_a_source_and_binary_vote():
    evidence = pd.read_csv(RESEARCH / "candidate_rollcall_position_evidence.csv")
    assert set(evidence.vote) <= {"Yea", "Nay"}
    assert evidence.source_url.fillna("").ne("").all()
    assert evidence.policy_direction_of_yea.fillna("").ne("").all()
