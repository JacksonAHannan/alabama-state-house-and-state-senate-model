from build_social_ideology_research_queue import build_queue


def test_queue_contains_only_missing_social_scores_and_is_person_unique():
    queue = build_queue()
    assert queue.person_id.is_unique
    assert len(queue) > 100


def test_queue_prioritizes_researchability_not_only_raw_1994_surnames():
    queue = build_queue()
    top = queue.head(20)
    assert top.identity_researchable.mean() >= .75
    assert top.extreme_cmo.abs().gt(30).all()


def test_queue_includes_both_electoral_tails():
    queue = build_queue()
    assert set(queue.research_tail) == {"high_overperformance", "low_overperformance"}
    assert queue.nsmallest(20, "low_tail_rank").min_cmo.lt(0).all()
