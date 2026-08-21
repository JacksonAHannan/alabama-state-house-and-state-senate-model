import pandas as pd

from build_candidate_issue_research_loop import ATTEMPTS, ROOT, CORE_ISSUES, build


def test_gap_matrix_is_unique_and_excludes_observed_positions():
    gaps, _, _ = build()
    assert not gaps.duplicated(["canonical_candidate_id", "primitive_axis"]).any()
    assert set(gaps.issue_priority) == {1, 2}


def test_research_batch_balances_both_cmo_tails():
    _, subjects, batch = build()
    available = subjects.groupby("cmo_tail").size().to_dict()
    expected = {tail: min(20, count) for tail, count in available.items()}
    assert set(batch.cmo_tail) == set(available)
    assert batch.groupby("cmo_tail").size().to_dict() == expected


def test_every_core_issue_is_in_gap_or_observed_for_each_candidate():
    gaps, subjects, _ = build()
    assert set(CORE_ISSUES).issubset(set(gaps.primitive_axis))
    assert subjects.canonical_candidate_id.is_unique


def test_roster_artifacts_are_not_researched_as_candidates():
    gaps, subjects, batch = build()
    excluded = {"AL-1994-house-8-R-NEW", "AL-1994-house-32-R-MONTGOMERY"}
    assert excluded.isdisjoint(set(gaps.canonical_candidate_id))
    assert excluded.isdisjoint(set(subjects.canonical_candidate_id))
    assert excluded.isdisjoint(set(batch.canonical_candidate_id))


def test_corrupted_cmo_is_not_used_for_research_priority():
    _, subjects, _ = build()
    flagged = subjects[subjects.canonical_candidate_id.isin({
        "AL-1994-senate-25-D-ANDERSON", "AL-1994-senate-25-R-DIXON"})]
    if not flagged.empty:
        assert not flagged.cmo_priority_valid.any()


def test_every_research_attempt_targets_a_canonical_candidate():
    canonical = set(pd.read_csv(
        ROOT / "data" / "processed" / "elections" / "canonical_cmo_candidates.csv"
    ).canonical_candidate_id)
    attempts = pd.read_csv(ATTEMPTS, dtype=str)
    unknown = sorted(set(attempts.canonical_candidate_id) - canonical)
    assert not unknown, f"research attempts use unknown candidate IDs: {unknown}"
