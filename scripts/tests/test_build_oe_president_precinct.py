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
