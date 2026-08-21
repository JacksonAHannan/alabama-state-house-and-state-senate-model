import pandas as pd


def test_post_election_evidence_is_archived_but_not_scored():
    evidence = pd.read_csv(
        "data/processed/ideology/candidate_position_evidence_v3_all_sources.csv",
        low_memory=False,
    )
    post = evidence.temporal_status.fillna("").str.contains(
        "post_election|retrospective", case=False, regex=True)
    assert post.any()
    assert not evidence.loc[post, "temporal_model_eligible"].fillna(False).any()
    years = pd.to_numeric(
        evidence.evidence_date.astype(str).str.extract(r"(19\d{2}|20\d{2})")[0],
        errors="coerce",
    )
    cycles = pd.to_numeric(evidence.election_cycle, errors="coerce")
    assert not (evidence.temporal_model_eligible.fillna(False) & years.gt(cycles)).any()


def test_terminal_missing_status_is_explicit_and_never_neutral():
    status = pd.read_csv(
        "research/cmo_ideology/candidate_issue_research/candidate_research_final_status.csv"
    )
    missing = status[~status.has_issue_evidence]
    assert len(missing) > 0
    assert set(missing.final_research_status) == {"searched_no_recoverable_evidence"}
    assert not missing.neutrality_imputed.any()


def test_minimum_evidence_thresholds_are_applied():
    positions = pd.read_csv("data/processed/ideology/candidate_issue_valence_v3.csv")
    scored = positions[positions.issue_score_available]
    assert scored.absolute_evidence_weight.ge(0.65).all()
    assert scored.conflict_ratio.lt(0.5).all()
    assert scored.issue_valence.abs().gt(0.15).all()
    candidates = pd.read_csv(
        "data/processed/elections/canonical_cmo_candidates_with_ideology_v3.csv",
        low_memory=False,
    )
    eligible = candidates[candidates.ideology_v3_model_eligible]
    assert eligible.ideology_v3_scored_issue_count.ge(3).all()
    assert eligible.ideology_v3_scored_family_count.ge(2).all()
