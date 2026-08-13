import pandas as pd
import pytest

from build_presidential_district_features import (
    allocate_to_districts,
    check_output_completeness,
    load_target_weights,
    _add_swing_columns,
    _canonical_county,
)


def _full_district_frame(source_year: int) -> pd.DataFrame:
    rows = [{"chamber": "house", "district": d} for d in range(1, 106)]
    rows += [{"chamber": "senate", "district": d} for d in range(1, 36)]
    frame = pd.DataFrame(rows)
    frame[f"pres_{source_year}_dem_margin"] = -20.0
    frame[f"pres_{source_year}_source_complete"] = True
    return frame


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


def _two_county_weights() -> pd.DataFrame:
    """Two counties, both chambers, with one Senate district spanning both.

    Mirrors the real weights table closely enough to exercise per-chamber vote
    conservation and the three distinct source-coverage states (fully covered,
    partially covered, not covered at all).
    """
    from build_presidential_district_features import _prepare_weights

    rows = [
        # AUTAUGA House: MAIN STREET CHURCH splits 80/20 between HD 10 and 11.
        ("house", "AUTAUGA", "MAIN STREET CHURCH", 10, 80),
        ("house", "AUTAUGA", "MAIN STREET CHURCH", 11, 20),
        ("house", "AUTAUGA", "OAK GROVE SCHOOL", 11, 50),
        # BULLOCK House: a single-county district, entirely inside BULLOCK.
        ("house", "BULLOCK", "PINE HILL LIBRARY", 12, 60),
        # Senate district 1 spans both counties.
        ("senate", "AUTAUGA", "MAIN STREET CHURCH", 1, 100),
        ("senate", "AUTAUGA", "OAK GROVE SCHOOL", 1, 50),
        ("senate", "BULLOCK", "PINE HILL LIBRARY", 1, 60),
    ]
    frame = pd.DataFrame(
        [
            {"cycle": 2018, "chamber": chamber, "county_key": county, "precinct_key": precinct,
             "district": district, "district_activity": activity}
            for chamber, county, precinct, district, activity in rows
        ]
    )
    return _prepare_weights(frame, target_cycle=2018)


def test_county_level_absentee_row_is_redistributed_not_dropped():
    # The critical regression: ABSENTEE/PROVISIONAL rows are real ballots
    # reported at county level rather than at a named polling place. They are
    # deliberately kept by build_oe_president_precinct.py, arrive here with a
    # real county_key and a precinct_key that matches no target precinct, and
    # must land in the district totals via the existing unmatched-residual
    # fallback -- not disappear. Deleting them upstream discarded 303,177 real
    # 2020 votes and flipped the sign of pres_swing_2016_2020.
    weights = _prepared_weights()
    votes = pd.DataFrame(
        [
            {"county_key": "AUTAUGA", "precinct_key": "MAIN STREET CHURCH", "dem_votes": 100.0, "rep_votes": 50.0},
            {"county_key": "AUTAUGA", "precinct_key": "ABSENTEE", "dem_votes": 60.0, "rep_votes": 40.0},
        ]
    )

    district, matches = allocate_to_districts(votes, weights, source_year=2020)

    absentee_match = matches.loc[matches.source_row_id == 2].iloc[0]
    assert absentee_match.match_method == "county_level_ballot"
    assert absentee_match.target_match_norm is None

    # Every absentee vote is still counted: 100 + 60 D and 50 + 40 R.
    assert round(district["pres_2020_dem_votes"].sum(), 6) == 160.0
    assert round(district["pres_2020_rep_votes"].sum(), 6) == 90.0

    # And it is redistributed in proportion to the county's matched activity
    # (HD 10 took 80% of MAIN STREET CHURCH, HD 11 the remaining 20%).
    district = district.set_index(["chamber", "district"])
    assert round(district.loc[("house", 10), "pres_2020_dem_votes"], 6) == 80.0 + 48.0
    assert round(district.loc[("house", 11), "pres_2020_dem_votes"], 6) == 20.0 + 12.0


def test_absentee_never_name_matches_a_target_precinct_called_absentee():
    # Regression test for a live collision: build_war_database.py derives the
    # target weights from the same OpenElections files, so the 2014 and 2018
    # weights genuinely contain precincts named ABSENTEE / BESSEMER ABSENTEE /
    # PROVISIONAL. If a source-side absentee batch were allowed to exact-match
    # one of those, an entire county's presidential votes could be redistributed
    # by that one batch's narrow district split. Real case: Jefferson County
    # 2016->2018, where those three names were the ONLY matches in the county.
    from build_presidential_district_features import _prepare_weights

    weights = _prepare_weights(
        pd.DataFrame(
            [
                {"cycle": 2018, "chamber": "house", "county_key": "AUTAUGA",
                 "precinct_key": "MAIN STREET CHURCH", "district": 10, "district_activity": 90},
                {"cycle": 2018, "chamber": "house", "county_key": "AUTAUGA",
                 "precinct_key": "MAIN STREET CHURCH", "district": 11, "district_activity": 10},
                # A target precinct literally named ABSENTEE, weighted almost
                # entirely to district 11 -- the unrepresentative sliver.
                {"cycle": 2018, "chamber": "house", "county_key": "AUTAUGA",
                 "precinct_key": "ABSENTEE", "district": 11, "district_activity": 20},
            ]
        ),
        target_cycle=2018,
    )
    votes = pd.DataFrame(
        [{"county_key": "AUTAUGA", "precinct_key": "ABSENTEE", "dem_votes": 100.0, "rep_votes": 0.0}]
    )

    district, matches = allocate_to_districts(votes, weights, source_year=2020)

    assert matches.match_method.tolist() == ["county_level_ballot"]
    # No precinct matched directly, so the county-activity tier applies and the
    # batch splits 90:30 across districts 10 and 11 by total county activity --
    # NOT 0:100 as an exact match on the target's own ABSENTEE row would give.
    district = district.set_index(["chamber", "district"])
    assert round(district.loc[("house", 10), "pres_2020_dem_votes"], 6) == 75.0
    assert round(district.loc[("house", 11), "pres_2020_dem_votes"], 6) == 25.0


def test_allocation_conserves_every_input_vote_within_each_chamber():
    # Vote-conservation invariant: allocation redistributes votes, it never
    # creates or destroys them. Each chamber independently receives 100% of the
    # source votes, whether a row matched a precinct directly, fell back to the
    # county's matched-activity split, or fell back to the county's own
    # legislative activity.
    weights = _two_county_weights()
    votes = pd.DataFrame(
        [
            {"county_key": "AUTAUGA", "precinct_key": "MAIN STREET CHURCH", "dem_votes": 100.0, "rep_votes": 50.0},
            {"county_key": "AUTAUGA", "precinct_key": "ABSENTEE", "dem_votes": 60.0, "rep_votes": 40.0},
            {"county_key": "BULLOCK", "precinct_key": "PINE HILL LIBRARY", "dem_votes": 30.0, "rep_votes": 70.0},
            {"county_key": "BULLOCK", "precinct_key": "PROVISIONAL", "dem_votes": 10.0, "rep_votes": 5.0},
        ]
    )
    input_dem = votes.dem_votes.sum()
    input_rep = votes.rep_votes.sum()

    district, _ = allocate_to_districts(votes, weights, source_year=2020)

    for chamber in ("house", "senate"):
        part = district[district.chamber.eq(chamber)]
        assert round(part["pres_2020_dem_votes"].sum(), 6) == input_dem, chamber
        assert round(part["pres_2020_rep_votes"].sum(), 6) == input_rep, chamber


def test_source_complete_flags_districts_with_missing_source_counties():
    # The 2012 OpenElections file has no rows at all for five Alabama counties,
    # so some districts get no margin and others get a margin computed from only
    # part of their electorate. Both are indistinguishable from a well-covered
    # district by the numbers alone, hence the explicit flag.
    weights = _two_county_weights()
    votes = pd.DataFrame(
        [
            {"county_key": "AUTAUGA", "precinct_key": "MAIN STREET CHURCH", "dem_votes": 100.0, "rep_votes": 50.0},
            {"county_key": "AUTAUGA", "precinct_key": "OAK GROVE SCHOOL", "dem_votes": 40.0, "rep_votes": 60.0},
        ]
    )

    district, _ = allocate_to_districts(votes, weights, source_year=2012)
    district = district.set_index(["chamber", "district"])

    # Districts wholly inside a covered county: complete.
    assert bool(district.loc[("house", 10), "pres_2012_source_complete"])
    assert bool(district.loc[("house", 11), "pres_2012_source_complete"])
    # District wholly inside the missing county: still present as a row (not
    # silently dropped), but with a null margin and flagged incomplete.
    assert ("house", 12) in district.index
    assert not bool(district.loc[("house", 12), "pres_2012_source_complete"])
    assert pd.isna(district.loc[("house", 12), "pres_2012_dem_margin"])
    # District spanning both: gets a margin, but one built from only part of
    # its electorate -- exactly the silently-wrong case worth flagging.
    assert not bool(district.loc[("senate", 1), "pres_2012_source_complete"])
    assert pd.notna(district.loc[("senate", 1), "pres_2012_dem_margin"])


def test_completeness_guard_accepts_a_fully_covered_cycle():
    check_output_completeness(_full_district_frame(2020), target_cycle=2022, source_years=[2020])


def test_completeness_guard_rejects_a_missing_district_row():
    frame = _full_district_frame(2020).drop(index=0)
    with pytest.raises(AssertionError, match="expected"):
        check_output_completeness(frame, target_cycle=2022, source_years=[2020])


def test_completeness_guard_rejects_an_unexplained_null_margin():
    # A null margin on a district whose counties were all present in the source
    # means votes are being dropped somewhere -- the exact silent-drop failure
    # this guard exists to catch.
    frame = _full_district_frame(2020)
    frame.loc[0, "pres_2020_dem_margin"] = None
    with pytest.raises(AssertionError, match="complete source-county coverage"):
        check_output_completeness(frame, target_cycle=2022, source_years=[2020])


def test_completeness_guard_tolerates_the_known_2012_county_gap():
    # 2012's upstream file genuinely lacks five counties, so a null margin
    # flagged incomplete is expected there and must not fail the build...
    frame = _full_district_frame(2012)
    frame.loc[0, "pres_2012_dem_margin"] = None
    frame.loc[0, "pres_2012_source_complete"] = False
    check_output_completeness(frame, target_cycle=2014, source_years=[2012])

    # ...but the same shape in a source year with no known gap must fail.
    frame = _full_district_frame(2020)
    frame.loc[0, "pres_2020_dem_margin"] = None
    frame.loc[0, "pres_2020_source_complete"] = False
    with pytest.raises(AssertionError, match="no known"):
        check_output_completeness(frame, target_cycle=2022, source_years=[2020])


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


def test_add_swing_columns_computes_2012_2016_swing_for_2018():
    # 2018 combines two presidential source years (2012, 2016), mirroring
    # the original build_2012_president_on_2018_map.py, which fed both into
    # the 2018 cycle and wrote pres_swing_2012_2016 = 2016 margin - 2012
    # margin. fit_preliminary_war_model.py (downstream) requires this column
    # on 2018 rows.
    combined = pd.DataFrame(
        [{"chamber": "house", "district": 1, "pres_2012_dem_margin": -20.0, "pres_2016_dem_margin": -10.0}]
    )
    result = _add_swing_columns(combined, target_cycle=2018)
    assert round(result.loc[0, "pres_swing_2012_2016"], 2) == 10.0
    assert "pres_swing_2016_2020" not in result.columns


def test_add_swing_columns_computes_2016_2020_swing_for_2022():
    combined = pd.DataFrame(
        [{"chamber": "house", "district": 1, "pres_2016_dem_margin": -10.0, "pres_2020_dem_margin": 5.0}]
    )
    result = _add_swing_columns(combined, target_cycle=2022)
    assert round(result.loc[0, "pres_swing_2016_2020"], 2) == 15.0
    assert "pres_swing_2012_2016" not in result.columns


def test_add_swing_columns_is_noop_for_2014():
    combined = pd.DataFrame([{"chamber": "house", "district": 1, "pres_2012_dem_margin": -20.0}])
    result = _add_swing_columns(combined, target_cycle=2014)
    assert "pres_swing_2012_2016" not in result.columns
    assert "pres_swing_2016_2020" not in result.columns
