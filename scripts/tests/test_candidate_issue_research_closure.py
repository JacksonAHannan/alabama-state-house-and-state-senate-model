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


def test_terminal_disposition_follows_the_current_evidence_layer():
    status = pd.read_csv(
        "research/cmo_ideology/candidate_issue_research/candidate_research_final_status.csv"
    )
    positions = pd.read_csv(
        "data/processed/ideology/candidate_issue_valence_v3.csv",
        usecols=["canonical_candidate_id"],
    )
    observed = set(positions.canonical_candidate_id)
    recovered = set(status.loc[status.has_issue_evidence, "canonical_candidate_id"])
    # Disposition rule: evidence_recovered iff the cycle carries a valence
    # profile in the current layer; everything else stays searched-without-
    # evidence and is never imputed.
    assert recovered == observed
    assert set(status.loc[status.has_issue_evidence, "final_research_status"]) == {
        "evidence_recovered"
    }
    missing = status[~status.has_issue_evidence]
    assert len(missing) > 0
    assert set(missing.final_research_status) == {"searched_no_recoverable_evidence"}
    assert not missing.neutrality_imputed.any()
    assert len(status) == len(recovered) + len(missing)


def test_restatement_preserves_prior_dispositions_and_records_the_delta():
    status = pd.read_csv(
        "research/cmo_ideology/candidate_issue_research/candidate_research_final_status.csv"
    )
    prior = pd.read_csv(
        "research/cmo_ideology/candidate_issue_research/"
        "candidate_research_final_status.2026-08-17.csv",
        usecols=["canonical_candidate_id", "final_research_status"],
    )
    prior_map = prior.set_index("canonical_candidate_id").final_research_status
    # Every prior disposition is carried verbatim in prior_status.
    assert status.canonical_candidate_id.isin(prior_map.index).all()
    snapshot_status = status.canonical_candidate_id.map(prior_map)
    assert status.prior_status.eq(snapshot_status).all()
    # Rows whose disposition moved are exactly the rows flagged as restated.
    changed = snapshot_status.ne(status.final_research_status)
    assert changed.any()
    assert status.restated_at_utc.fillna("").ne("").eq(changed).all()
    moved = status[changed]
    assert moved.prior_status.eq("searched_no_recoverable_evidence").all()
    assert moved.final_research_status.eq("evidence_recovered").all()
    assert moved.new_evidence_source_types.fillna("").ne("").all()
    unchanged = status[~changed]
    assert unchanged.new_evidence_source_types.fillna("").eq("").all()
    assert unchanged.restated_at_utc.fillna("").eq("").all()


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
