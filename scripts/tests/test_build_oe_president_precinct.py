from build_oe_president_precinct import extract_president_precinct_votes


def test_extract_pivots_president_votes_by_precinct(tmp_path):
    csv_text = (
        "county,precinct,office,district,party,candidate,votes\n"
        "Autauga,Precinct 1,President,,DEM,Joseph R. Biden,100\n"
        "Autauga,Precinct 1,President,,REP,Donald J. Trump,150\n"
        "Autauga,Precinct 1,President,,GRN,Jo Jorgensen,5\n"
        "Autauga,Precinct 2,President,,REP,Donald J. Trump,80\n"
        "Autauga,Precinct 1,State House,10,DEM,Smith,40\n"
    )
    path = tmp_path / "sample.csv"
    path.write_text(csv_text)

    result = extract_president_precinct_votes(path)
    result = result.set_index(["county_key", "precinct_key"])

    assert result.loc[("AUTAUGA", "PRECINCT 1"), "dem_votes"] == 100
    assert result.loc[("AUTAUGA", "PRECINCT 1"), "rep_votes"] == 150
    assert result.loc[("AUTAUGA", "PRECINCT 1"), "two_party_votes"] == 250
    assert round(result.loc[("AUTAUGA", "PRECINCT 1"), "pres_dem_margin"], 2) == -20.0

    # Precinct with only Republican votes: Democratic column fills with 0.
    assert result.loc[("AUTAUGA", "PRECINCT 2"), "dem_votes"] == 0
    assert result.loc[("AUTAUGA", "PRECINCT 2"), "rep_votes"] == 80

    # Only 2 precincts total: the State House row and the Green candidate
    # row must not leak into the President pivot.
    assert len(result) == 2


def test_drops_total_rows_but_keeps_county_level_ballot_rows(tmp_path):
    """TOTAL rows are duplicates and must go; ABSENTEE rows are real votes and must stay.

    2012/2014 OE data includes county-level TOTAL summary rows (e.g.,
    precinct="TOTAL") that restate the sum of all real precincts in that
    county; counting them doubles the county. ABSENTEE/PROVISIONAL rows are the
    opposite: distinct ballots that simply are not attributed to a named polling
    place. Dropping those was discarding 311,836 real 2020 two-party votes
    (13.6% of the electorate, 65.1% Democratic). They are kept here and redistributed within
    county by build_presidential_district_features.py's fallback tier.
    """
    csv_text = (
        "county,precinct,office,district,party,candidate,votes\n"
        "Autauga,Precinct 1,President,,DEM,BARACK OBAMA / JOE BIDEN,500\n"
        "Autauga,Precinct 1,President,,REP,MITT ROMNEY / PAUL RYAN,750\n"
        "Autauga,Precinct 2,President,,DEM,BARACK OBAMA / JOE BIDEN,300\n"
        "Autauga,Precinct 2,President,,REP,MITT ROMNEY / PAUL RYAN,450\n"
        "Autauga,TOTAL,President,,DEM,BARACK OBAMA / JOE BIDEN,900\n"
        "Autauga,TOTAL,President,,REP,MITT ROMNEY / PAUL RYAN,1400\n"
        "Autauga,ABSENTEE,President,,DEM,BARACK OBAMA / JOE BIDEN,100\n"
        "Autauga,ABSENTEE,President,,REP,MITT ROMNEY / PAUL RYAN,200\n"
    )
    path = tmp_path / "sample.csv"
    path.write_text(csv_text)

    result = extract_president_precinct_votes(path)
    result = result.set_index(["county_key", "precinct_key"])

    assert ("AUTAUGA", "TOTAL") not in result.index
    assert ("AUTAUGA", "ABSENTEE") in result.index
    assert len(result) == 3

    # Verify vote totals are NOT doubled by the TOTAL row...
    assert result.loc[("AUTAUGA", "PRECINCT 1"), "dem_votes"] == 500
    assert result.loc[("AUTAUGA", "PRECINCT 1"), "rep_votes"] == 750
    assert result.loc[("AUTAUGA", "PRECINCT 2"), "dem_votes"] == 300
    assert result.loc[("AUTAUGA", "PRECINCT 2"), "rep_votes"] == 450
    # ...and that the absentee ballots survive with their own vote counts.
    assert result.loc[("AUTAUGA", "ABSENTEE"), "dem_votes"] == 100
    assert result.loc[("AUTAUGA", "ABSENTEE"), "rep_votes"] == 200

    # The county's real electorate is precincts + absentee, matching the
    # TOTAL row exactly -- which is precisely why TOTAL must not be added on top.
    assert result.dem_votes.sum() == 900
    assert result.rep_votes.sum() == 1400


def test_infers_party_from_candidate_name_when_null(tmp_path):
    """Verify party inference from candidate names for unmapped party field.

    2012 OE data has no party field for President rows; party must be
    inferred from candidate names. This test uses party="UNK" which
    norm_party() maps to "O", triggering the inference logic.
    """
    csv_text = (
        "county,precinct,office,district,party,candidate,votes\n"
        "Autauga,Precinct 1,President,,UNK,BARACK OBAMA / JOE BIDEN,100\n"
        "Autauga,Precinct 1,President,,UNK,MITT ROMNEY / PAUL RYAN,150\n"
        "Autauga,Precinct 2,President,,UNK,BARACK OBAMA / JOE BIDEN,80\n"
        "Autauga,Precinct 2,President,,UNK,MITT ROMNEY / PAUL RYAN,120\n"
    )
    path = tmp_path / "sample.csv"
    path.write_text(csv_text)

    result = extract_president_precinct_votes(path)
    result = result.set_index(["county_key", "precinct_key"])

    # Verify correct party is inferred from candidate names and votes are tallied correctly.
    # With party="UNK", norm_party() returns "O", then infer_president_party_from_candidate()
    # is called to map candidate names to D/R.
    assert result.loc[("AUTAUGA", "PRECINCT 1"), "dem_votes"] == 100
    assert result.loc[("AUTAUGA", "PRECINCT 1"), "rep_votes"] == 150
    assert result.loc[("AUTAUGA", "PRECINCT 2"), "dem_votes"] == 80
    assert result.loc[("AUTAUGA", "PRECINCT 2"), "rep_votes"] == 120
    # Only 2 precincts should be in result (real precincts, not summary rows)
    assert len(result) == 2
