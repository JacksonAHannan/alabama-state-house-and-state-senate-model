from scripts.sos_precinct import _legacy_2008, _office, normalize_workbook


def test_legacy_abbreviated_legislative_labels_resolve_districts():
    assert _office("State Rep. Dist. 88") == ("State House", 88.0)
    assert _office("State Sen. Dist. 30") == ("State Senate", 30.0)
    assert _office("Senator, Dist 9") == ("State Senate", 9.0)
    assert _office("STATE HOUSE 64") == ("State House", 64.0)
    assert _office("State House, District 33") == ("State House", 33.0)
    assert _office("Attorney Gen.") == ("Attorney General", None)
    assert _office("President PSC") == ("Public Service Commission President", None)
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
