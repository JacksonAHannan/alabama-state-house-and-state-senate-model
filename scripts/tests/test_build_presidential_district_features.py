import pandas as pd

from build_presidential_district_features import allocate_to_districts, load_target_weights, _canonical_county


def _weights_frame() -> pd.DataFrame:
    # Two precincts in one county, split between two House districts by
    # legislative-contest activity, mirroring precinct_district_allocation_weights.csv.
    # NOTE: names deliberately avoid a trailing bare digit 1-3 (e.g. "PRECINCT 1"),
    # since normalize_for_match strips that suffix by design (it collapses
    # same-building multi-box precincts like "COLISEUM 1"/"COLISEUM 2" in the
    # real weights data) -- using it here would make these two fixture
    # precincts collide onto the same normalized name.
    return pd.DataFrame(
        [
            {"cycle": 2018, "chamber": "house", "county_key": "AUTAUGA", "precinct_key": "MAIN STREET CHURCH",
             "district": 10, "district_activity": 80, "precinct_activity": 100, "allocation_weight": 0.8},
            {"cycle": 2018, "chamber": "house", "county_key": "AUTAUGA", "precinct_key": "MAIN STREET CHURCH",
             "district": 11, "district_activity": 20, "precinct_activity": 100, "allocation_weight": 0.2},
            {"cycle": 2018, "chamber": "house", "county_key": "AUTAUGA", "precinct_key": "OAK GROVE SCHOOL",
             "district": 11, "district_activity": 50, "precinct_activity": 50, "allocation_weight": 1.0},
        ]
    )


def _prepared_weights() -> pd.DataFrame:
    from build_presidential_district_features import _prepare_weights

    return _prepare_weights(_weights_frame(), target_cycle=2018)


def test_prepare_weights_filters_cycle_and_computes_share():
    weights = _prepared_weights()
    row10 = weights[(weights.target_match_norm == "MAIN STREET CHURCH") & (weights.district == 10)].iloc[0]
    assert round(row10.activity_share, 2) == 0.8


def test_allocate_to_districts_splits_precinct_by_activity_share():
    weights = _prepared_weights()
    votes = pd.DataFrame(
        [
            {"county_key": "AUTAUGA", "precinct_key": "MAIN STREET CHURCH", "dem_votes": 100.0, "rep_votes": 50.0},
            {"county_key": "AUTAUGA", "precinct_key": "OAK GROVE SCHOOL", "dem_votes": 40.0, "rep_votes": 60.0},
        ]
    )

    district, matches = allocate_to_districts(votes, weights, source_year=2016)
    district = district.set_index(["chamber", "district"])

    # Precinct 1 (150 two-party votes) splits 80/20 across districts 10/11.
    assert round(district.loc[("house", 10), "pres_2016_dem_votes"], 2) == 80.0
    assert round(district.loc[("house", 10), "pres_2016_rep_votes"], 2) == 40.0
    # District 11 gets precinct 1's 20% share plus all of precinct 2.
    assert round(district.loc[("house", 11), "pres_2016_dem_votes"], 2) == 20.0 + 40.0
    assert round(district.loc[("house", 11), "pres_2016_rep_votes"], 2) == 10.0 + 60.0
    assert (matches.match_method == "exact").all()


def test_allocate_to_districts_falls_back_for_unmatched_precinct():
    weights = _prepared_weights()
    votes = pd.DataFrame(
        [
            {"county_key": "AUTAUGA", "precinct_key": "MAIN STREET CHURCH", "dem_votes": 100.0, "rep_votes": 50.0},
            {"county_key": "AUTAUGA", "precinct_key": "SOME BRAND NEW PRECINCT NAME", "dem_votes": 10.0, "rep_votes": 10.0},
        ]
    )

    district, matches = allocate_to_districts(votes, weights, source_year=2016)

    # The unmatched precinct's votes must still show up somewhere (as
    # fallback), not silently vanish.
    total_dem = district["pres_2016_dem_votes"].sum()
    assert round(total_dem, 2) == 110.0
    assert "unmatched" in matches.match_method.values


def test_allocate_to_districts_uses_county_activity_when_no_precinct_in_county_matches():
    # Regression test: if NOT ONE precinct in a county matches directly for
    # an office, there is no precinct-activity fallback share to fall back
    # to either (that share is itself built from directly-matched
    # precincts). Naively inner-joining the residual against that empty
    # per-county share table drops the county's votes entirely -- this is
    # what happened for Jefferson county in the real 2016->2018 and
    # 2016->2022 runs (0/171 precincts matched because 2018/2022's
    # legislative-weights precinct names carry a "PREC " prefix that 2016's
    # source names lack). The allocator must fall back further, to the
    # target cycle's own county-level district-activity split.
    weights = _prepared_weights()
    votes = pd.DataFrame(
        [
            {"county_key": "AUTAUGA", "precinct_key": "TOTALLY UNKNOWN PRECINCT ONE", "dem_votes": 80.0, "rep_votes": 20.0},
            {"county_key": "AUTAUGA", "precinct_key": "TOTALLY UNKNOWN PRECINCT TWO", "dem_votes": 20.0, "rep_votes": 80.0},
        ]
    )

    district, matches = allocate_to_districts(votes, weights, source_year=2016)
    assert (matches.match_method == "unmatched").all()

    district = district.set_index(["chamber", "district"])
    # County-level district_activity from the fixture: district 10 = 80
    # (MAIN STREET CHURCH only), district 11 = 20 + 50 = 70 (MAIN STREET
    # CHURCH's other share plus all of OAK GROVE SCHOOL). Total 150, so the
    # county-level split is 80/150 and 70/150.
    total_dem = 100.0  # 80 + 20
    total_rep = 100.0  # 20 + 80
    assert round(district.loc[("house", 10), "pres_2016_dem_votes"], 2) == round(total_dem * 80 / 150, 2)
    assert round(district.loc[("house", 11), "pres_2016_dem_votes"], 2) == round(total_dem * 70 / 150, 2)
    assert round(district["pres_2016_dem_votes"].sum(), 2) == total_dem
    assert round(district["pres_2016_rep_votes"].sum(), 2) == total_rep
    assert round(district.loc[("house", 10), "pres_2016_fallback_share"], 4) == 1.0


def test_canonical_county_reconciles_st_clair_spelling_variants():
    # Regression test: normalize_name() only expands the "ST" token to
    # "SAINT" when it's whitespace-delimited, so "St. Clair" -> "SAINT
    # CLAIR" but "StClair" (no separator, how some raw OpenElections cycles
    # spell the county) -> "STCLAIR", unchanged. Confirmed in the real
    # 2016->2022 and 2020->2022 runs: source votes spelled it "StClair" (->
    # "STCLAIR") while the 2022 target weights spelled it "St. Clair" (->
    # "SAINT CLAIR"), so every St. Clair precinct silently failed to match
    # any target county at all.
    assert _canonical_county("STCLAIR") == "SAINT CLAIR"
    assert _canonical_county("SAINT CLAIR") == "SAINT CLAIR"
    assert _canonical_county("AUTAUGA") == "AUTAUGA"
