import pandas as pd

from build_1994_cmo_baseline import CORE, allocate, build_features, build_weights, load_returns


def _built():
    legislative, statewide, candidates = load_returns()
    weights = build_weights(legislative)
    allocated, qa, unmatched = allocate(statewide, weights)
    office, races = build_features(candidates, allocated)
    return weights, qa, unmatched, office, races


def test_1994_ballot_weights_are_complete_probabilities():
    weights, _, _, _, _ = _built()
    sums = weights.groupby(["chamber", "county_key", "precinct_key"]).allocation_weight.sum()
    assert (sums - 1).abs().max() < 1e-10
    single = weights[weights.district_count.eq(1)]
    assert single.allocation_weight.eq(1).all()
    assert single.allocation_method.eq("official_ballot_single_district").all()
    assert weights[weights.district_count.gt(1)].allocation_method.eq(
        "legislative_activity_split_provisional").all()


def test_1994_allocation_reconciles_to_explicit_unmatched_votes():
    _, qa, unmatched, _, _ = _built()
    assert ((qa.source_votes - qa.allocated_votes - qa.unmatched_votes).abs() < 1e-6).all()
    assert qa.allocation_coverage.between(0.98, 1).all()
    review = (unmatched.groupby(["chamber", "office", "party_norm"], as_index=False).votes.sum()
              .rename(columns={"party_norm": "party", "votes": "review_votes"}))
    check = qa.merge(review, on=["chamber", "office", "party"], validate="one_to_one")
    assert ((check.unmatched_votes - check.review_votes).abs() < 1e-6).all()
    assert len(qa) == 2 * len(CORE) * 2


def test_1994_features_cover_plan_and_use_both_core_offices():
    _, _, _, office, races = _built()
    assert set(office.office) == set(CORE)
    assert races[races.chamber.eq("house")].district.nunique() == 104
    assert races[races.chamber.eq("senate")].district.nunique() == 35
    assert races.core_index_complete.all()
    # Legacy legislative-title normalization recovers one additional contest.
    assert int(races.contested_two_party.sum()) == 72
    eligible = races[races.contested_two_party]
    assert eligible.raw_overperformance.notna().all()
