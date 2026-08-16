from index_historical_alabama_acts import normalize_measure, parse_volume


def test_parse_act_with_split_header_and_title():
    text = """
Act No. 98-10 H.J.R. 25 - Rep. Smith
HOUSE JOINT RESOLUTION
COMMENDING A LOCAL PROGRAM FOR OUTSTANDING ACHIEVEMENT.
WHEREAS, the program did useful work; now therefore,
Approved January 26, 1998
Time: 9:09 A.M.
"""
    rows = parse_volume(text, "volume.txt", 1998)
    assert len(rows) == 1
    row = rows[0]
    assert row["act_year"] == 1998
    assert row["act_number"] == 10
    assert row["measure_type"] == "HJR"
    assert row["measure_number"] == 25
    assert row["origin_chamber"] == "H"
    assert row["title"] == "COMMENDING A LOCAL PROGRAM FOR OUTSTANDING ACHIEVEMENT"
    assert row["approval_date_raw"] == "January 26, 1998"


def test_measure_normalization():
    assert normalize_measure("S. B.") == "SB"
    assert normalize_measure("H.J.R.") == "HJR"
    assert normalize_measure("H.") == "H"


def test_measure_can_precede_act_label_at_page_break():
    text = "Approved January 1, 1998\nS.J.R. 5 - Senators Example\nAct No. 98-17\nSENATE JOINT RESOLUTION\nA COMMENDATION.\nWHEREAS, something"
    row = parse_volume(text, "volume.txt", 1998)[0]
    assert row["measure_type"] == "SJR"
    assert row["measure_number"] == 5
