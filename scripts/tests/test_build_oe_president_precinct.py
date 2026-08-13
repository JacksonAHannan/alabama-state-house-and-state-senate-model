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


def test_filters_out_total_and_non_geographic_precincts(tmp_path):
    """Verify that TOTAL/ABSENTEE/PROVISIONAL rows are excluded.

    2012 OE data includes county-level TOTAL summary rows (e.g.,
    precinct="TOTAL") that replicate the sum of all real precincts in that
    county. Without filtering, these cause 2x vote inflation.
    """
    csv_text = (
        "county,precinct,office,district,party,candidate,votes\n"
        "Autauga,Precinct 1,President,,DEM,BARACK OBAMA / JOE BIDEN,500\n"
        "Autauga,Precinct 1,President,,REP,MITT ROMNEY / PAUL RYAN,750\n"
        "Autauga,Precinct 2,President,,DEM,BARACK OBAMA / JOE BIDEN,300\n"
        "Autauga,Precinct 2,President,,REP,MITT ROMNEY / PAUL RYAN,450\n"
        "Autauga,TOTAL,President,,DEM,BARACK OBAMA / JOE BIDEN,800\n"
        "Autauga,TOTAL,President,,REP,MITT ROMNEY / PAUL RYAN,1200\n"
        "Autauga,ABSENTEE,President,,DEM,BARACK OBAMA / JOE BIDEN,100\n"
        "Autauga,ABSENTEE,President,,REP,MITT ROMNEY / PAUL RYAN,200\n"
    )
    path = tmp_path / "sample.csv"
    path.write_text(csv_text)

    result = extract_president_precinct_votes(path)
    result = result.set_index(["county_key", "precinct_key"])

    # Only 2 real precincts should be in result: TOTAL and ABSENTEE filtered out
    assert len(result) == 2
    assert ("AUTAUGA", "PRECINCT 1") in result.index
    assert ("AUTAUGA", "PRECINCT 2") in result.index
    assert ("AUTAUGA", "TOTAL") not in result.index
    assert ("AUTAUGA", "ABSENTEE") not in result.index

    # Verify vote totals are NOT doubled
    assert result.loc[("AUTAUGA", "PRECINCT 1"), "dem_votes"] == 500
    assert result.loc[("AUTAUGA", "PRECINCT 1"), "rep_votes"] == 750
    assert result.loc[("AUTAUGA", "PRECINCT 2"), "dem_votes"] == 300
    assert result.loc[("AUTAUGA", "PRECINCT 2"), "rep_votes"] == 450


def test_infers_party_from_candidate_name_when_null(tmp_path):
    """Verify party inference from candidate names for null party field.

    2012 OE data has no party field for President rows; party must be
    inferred from candidate names.
    """
    csv_text = (
        "county,precinct,office,district,party,candidate,votes\n"
        "Autauga,Precinct 1,President,,DEM,BARACK OBAMA / JOE BIDEN,100\n"
        "Autauga,Precinct 1,President,,REP,MITT ROMNEY / PAUL RYAN,150\n"
        "Autauga,Precinct 2,President,,DEM,BARACK OBAMA / JOE BIDEN,80\n"
        "Autauga,Precinct 2,President,,REP,MITT ROMNEY / PAUL RYAN,120\n"
    )
    path = tmp_path / "sample.csv"
    path.write_text(csv_text)

    result = extract_president_precinct_votes(path)
    result = result.set_index(["county_key", "precinct_key"])

    # Verify correct party is inferred and votes are tallied
    assert result.loc[("AUTAUGA", "PRECINCT 1"), "dem_votes"] == 100
    assert result.loc[("AUTAUGA", "PRECINCT 1"), "rep_votes"] == 150
    assert result.loc[("AUTAUGA", "PRECINCT 2"), "dem_votes"] == 80
    assert result.loc[("AUTAUGA", "PRECINCT 2"), "rep_votes"] == 120
