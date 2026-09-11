from scripts.sos_precinct import _contest_sheets, _legacy_1994, _legacy_2002, _legacy_2008, _office, _wide_sheet, normalize_workbook


def test_jefferson_total_is_not_a_precinct():
    rows = [["Contest Title", "Party Code", "Candidate Name",
             "Total Of Registered Voters", "1010", "ABSENTEE"],
            ["GOVERNOR", "DEM", "Example", 14, 10, 4]]
    data = _wide_sheet(rows, "Jefferson")
    assert data.votes.sum() == 14
    assert data.precinct.tolist() == ["1010", "ABSENTEE"]


def test_marshall_2002_uses_printed_metadata_columns():
    rows = [["", "", "", "", "", "", "PRECINCT NAME"],
            ["", "", "", "", "", "", "Total Of Number Votes", "ABSENTEE", "P1"],
            ["County Code", "County", "Contest Title", "Contest Title", "Party Code", "Candidate"],
            ["48", "MARSHALL", "MARSHALL", "GOVERNOR", "DEM", "Example", 14, 4, 10]]
    data = _legacy_2002(rows, "MARSHALL")
    assert data.office.tolist() == ["Governor", "Governor"]
    assert set(data.party) == {"DEM"} and set(data.candidate) == {"Example"}
    assert data.votes.sum() == 14


def test_standard_2002_layout_is_unchanged():
    rows = [["", "", "", "", "", "PRECINCT NAME"],
            ["", "", "", "", "", "Total Of Number Votes", "ABSENTEE", "P1"],
            ["County Code", "County", "Contest Title", "Party Code", "Candidate"],
            ["01", "AUTAUGA", "GOVERNOR", "DEM", "Example", 14, 4, 10]]
    data = _legacy_2002(rows, "AUTAUGA")
    assert data.votes.tolist() == [4, 10]
    assert set(data.office) == {"Governor"}


def test_1994_retains_distinct_source_codes_and_ag_export_encoding():
    rows = [["", "", "", "Attorney General", ""], ["", "", "Precinct", "", ""],
            ["Line", "Precinct Name", "Number", "Evans", "Sessions"],
            ["", "", "PRECINCT", "AG1", "AG2"],
            [1, "Same place", 38249, 10, 20], [2, "Same place", 38248, 11, 21],
            [3, "", 26001, 12, 144.4]]
    data = _legacy_1994(rows, "Example")
    assert data.precinct_key.nunique() == 3
    assert data.precinct_code.tolist() == ["38249", "38249", "38248", "38248", "26001", "26001"]
    assert set(data[data.candidate.eq("Sessions")].party) == {"R"}
    assert data.votes.iloc[-1] == 144.4  # Preserve the source error, never round it.
    assert data.source_row.tolist() == [5, 5, 6, 6, 7, 7]
    assert data.source_column.tolist() == [4, 5, 4, 5, 4, 5]


def test_legacy_abbreviated_legislative_labels_resolve_districts():
    assert _office("State Rep. Dist. 88") == ("State House", 88.0)
    assert _office("State Sen. Dist. 30") == ("State Senate", 30.0)
    assert _office("Senator, Dist 9") == ("State Senate", 9.0)
    assert _office("STATE HOUSE 64") == ("State House", 64.0)
    assert _office("State House, District 33") == ("State House", 33.0)
    assert _office("Attorney Gen.") == ("Attorney General", None)
    assert _office("President PSC") == ("Public Service Commission President", None)
    assert _office("Public Service Commission, Place 1") == ("Public Service Commission, Place 1", None)
    assert _office("FOR UNITED STATES SENATOR") == ("U.S. Senate", None)
    assert _office("FOR UNITED STATES REPRESENTATIVE, DISTRICT 2") == ("U.S. House", 2.0)


def test_2008_parser_excludes_reported_totals_and_distinguishes_psc():
    rows = [
        ["General 2008", "", ""],
        ["Example County", "", ""],
        ["", "President", "President PSC"],
        ["Precinct", "Barack Obama (D)", "Lucy Baxley (D)"],
        ["P1", 10, 8],
        ["Calculated", 10, 8],
        ["Reported", 10, 8],
    ]
    data = _legacy_2008({"Example": rows}, "Example")
    assert data[["office", "votes"]].to_dict("records") == [
        {"office": "President", "votes": 10.0},
        {"office": "Public Service Commission President", "votes": 8.0},
    ]

def test_spreadsheetml_contest_parser_uses_total_vote_columns():
    xml = b'''<?xml version="1.0"?><Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"><Worksheet ss:Name="2"><Table><Row><Cell><Data ss:Type="String">FOR GOVERNOR (Vote For 1)</Data></Cell></Row><Row><Cell/><Cell/><Cell><Data ss:Type="String">Alice</Data></Cell><Cell/><Cell><Data ss:Type="String">Bob</Data></Cell></Row><Row><Cell><Data ss:Type="String">Precinct</Data></Cell><Cell><Data ss:Type="String">Registered</Data></Cell><Cell><Data ss:Type="String">Polling</Data></Cell><Cell><Data ss:Type="String">Total Votes</Data></Cell><Cell><Data ss:Type="String">Polling</Data></Cell><Cell><Data ss:Type="String">Total Votes</Data></Cell></Row><Row><Cell><Data ss:Type="String">P1</Data></Cell><Cell><Data ss:Type="Number">100</Data></Cell><Cell><Data ss:Type="Number">9</Data></Cell><Cell><Data ss:Type="Number">10</Data></Cell><Cell><Data ss:Type="Number">19</Data></Cell><Cell><Data ss:Type="Number">20</Data></Cell></Row></Table></Worksheet></Workbook>'''
    data = normalize_workbook(xml, "Autauga", 2010)
    assert data[["candidate", "votes"]].to_dict("records") == [{"candidate":"Alice","votes":10.0},{"candidate":"Bob","votes":20.0}]

def test_wide_parser_keeps_absentee_and_party():
    xml = b'''<?xml version="1.0"?><Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"><Worksheet ss:Name="Precinct Results"><Table><Row><Cell><Data ss:Type="String">Contest Title</Data></Cell><Cell><Data ss:Type="String">Party</Data></Cell><Cell><Data ss:Type="String">Candidate</Data></Cell><Cell><Data ss:Type="String">P1</Data></Cell><Cell><Data ss:Type="String">ABSENTEE</Data></Cell></Row><Row><Cell><Data ss:Type="String">FOR STATE REPRESENTATIVE, DISTRICT 1</Data></Cell><Cell><Data ss:Type="String">DEM</Data></Cell><Cell><Data ss:Type="String">Alice</Data></Cell><Cell><Data ss:Type="Number">10</Data></Cell><Cell><Data ss:Type="Number">4</Data></Cell></Row></Table></Worksheet></Workbook>'''
    data = normalize_workbook(xml, "Autauga", 2014)
    assert data.votes.sum() == 14 and set(data.party_norm) == {"D"}


def test_contest_cells_preserve_repeated_labels_and_physical_lineage():
    sheet = [
        ["PROPOSED STATEWIDE AMENDMENT NUMBER ONE (1) (Vote For 1)"],
        ["", "", " YES ", "", " YES ", ""],
        ["Precinct", "Registered Voters", "Polling", "Total Votes", "Polling", "Total Votes"],
        ["Same place", 100, 8, 10, 18, 20],
        ["Same place ", 200, 28, 30, 38, 40],
        ["TOTAL", 300, 36, 40, 56, 60],
    ]
    data = _contest_sheets({"Registered Voters": sheet, "29": sheet, "30": sheet}, "Example")
    assert data.precinct.tolist() == ["Same place"] * 8
    assert data.candidate.tolist() == ["YES"] * 8
    assert data.party.tolist() == [""] * 8
    assert data.votes.tolist() == [10.0, 20.0, 30.0, 40.0] * 2
    assert data.source_sheet.tolist() == ["29"] * 4 + ["30"] * 4
    assert data.source_row.tolist() == [4, 4, 5, 5] * 2
    assert data.source_column.tolist() == [4, 6, 4, 6] * 2
    assert data.printed_precinct.tolist() == ["Same place", "Same place", "Same place ", "Same place "] * 2
    assert data.printed_candidate.tolist() == [" YES "] * 8
    assert not data.duplicated(["source_sheet", "source_row", "source_column"]).any()
