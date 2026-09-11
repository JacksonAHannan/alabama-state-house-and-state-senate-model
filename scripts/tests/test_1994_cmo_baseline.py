"""Arithmetic contract of the 1994 CMO baseline on explicit eligible input.

The live 1994 source slice is fail-closed: `vote_observations` retains the
unresolved 144.4 Morgan Attorney General cell, so `load_returns` refuses to
aggregate it (see
`project_docs/audits/MORGAN_1994_FRACTIONAL_CELL_QUARANTINE_2026_09_10.md`).
These tests therefore drive `build_weights`, `allocate` and `build_features`
directly with deterministic integer fixtures and never depend on warehouse
contents. Scale assertions about the real source (104 House districts, 35
Senate districts, 72 contested races) are recorded in that audit as the last
pre-quarantine build's observed coverage; they cannot be re-executed while the
quarantine stands. The live refusal itself is pinned by
`scripts/tests/test_morgan_1994_quarantine.py`.
"""
import pandas as pd

from build_1994_cmo_baseline import CORE, allocate, build_features, build_weights


def _legislative():
    rows = [
        # County A1 splits its House ballot activity across two districts and
        # votes a single Senate district; A2 and B1 are single-district.
        ("A", "A1", "State House", 1, 600),
        ("A", "A1", "State House", 2, 400),
        ("A", "A1", "State Senate", 1, 1000),
        ("A", "A2", "State House", 1, 1000),
        ("A", "A2", "State Senate", 1, 1000),
        ("B", "B1", "State House", 1, 50),
    ]
    return pd.DataFrame(rows, columns=["county_key", "precinct_key", "office", "district", "votes"])


def _statewide():
    rows = []
    for county, precinct, (ag_d, ag_r, gov_d, gov_r) in [
        ("A", "A1", (800, 1000, 900, 900)),
        ("A", "A2", (700, 700, 950, 850)),
        # B1 has no Senate ballot activity, so its statewide votes stay unmatched there.
        ("B", "B1", (3, 2, 2, 3)),
    ]:
        rows += [
            (county, precinct, "Attorney General", "EVANS", "D", ag_d),
            (county, precinct, "Attorney General", "SESSIONS", "R", ag_r),
            (county, precinct, "Governor", "FOLSOM", "D", gov_d),
            (county, precinct, "Governor", "JAMES", "R", gov_r),
        ]
    return pd.DataFrame(rows, columns=[
        "county_key", "precinct_key", "office", "candidate_key", "party_norm", "votes"])


def _candidates():
    rows = [
        ("house", 1, "D", 1200), ("house", 1, "R", 900),
        ("house", 2, "D", 400), ("house", 2, "R", 380),
        ("senate", 1, "D", 2000), ("senate", 1, "R", 1900),
    ]
    return pd.DataFrame(rows, columns=["chamber", "district", "canonical_party", "votes"])


def _built():
    weights = build_weights(_legislative())
    allocated, qa, unmatched = allocate(_statewide(), weights)
    office, races = build_features(_candidates(), allocated)
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
    assert set(weights[weights.chamber.eq("house")].district) == {1, 2}


def test_1994_allocation_reconciles_to_explicit_unmatched_votes():
    _, qa, unmatched, _, _ = _built()
    assert ((qa.source_votes - qa.allocated_votes - qa.unmatched_votes).abs() < 1e-6).all()
    assert qa.allocation_coverage.between(0.98, 1).all()
    review = (unmatched.groupby(["chamber", "office", "party_norm"], as_index=False).votes.sum()
              .rename(columns={"party_norm": "party", "votes": "review_votes"}))
    check = qa.merge(review, on=["chamber", "office", "party"], validate="one_to_one")
    assert ((check.unmatched_votes - check.review_votes).abs() < 1e-6).all()
    assert len(qa) == 2 * len(CORE) * 2
    # Only B1 lacks Senate ballot activity; every House precinct is matched.
    assert set(unmatched[unmatched.chamber.eq("senate")].precinct_key) == {"B1"}
    assert unmatched[unmatched.chamber.eq("house")].empty
    assert qa[qa.chamber.eq("house")].allocation_coverage.eq(1).all()


def test_1994_features_cover_plan_and_use_both_core_offices():
    _, _, _, office, races = _built()
    assert set(office.office) == set(CORE)
    assert races[races.chamber.eq("house")].district.nunique() == 2
    assert races[races.chamber.eq("senate")].district.nunique() == 1
    assert races.core_index_complete.all()
    assert int(races.contested_two_party.sum()) == 3
    eligible = races[races.contested_two_party]
    assert eligible.raw_overperformance.notna().all()
    assert eligible.legislative_dem_margin.notna().all()
    # The split precinct's House activity is shared, so the two House races
    # receive different core-index baselines from the same statewide votes.
    house = eligible[eligible.chamber.eq("house")].set_index("district")
    assert house.loc[1, "core_index_margin"] != house.loc[2, "core_index_margin"]
