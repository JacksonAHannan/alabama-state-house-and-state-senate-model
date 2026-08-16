from extract_historical_senate_journal_rollcalls import member_names, parse_document


def test_senate_rollcall_and_final_passage_pair():
    text = """\n<<<PAGE 1>>>\nTHE BILL: SB477\nwas read a third time at length and passed, and ordered sent to the House.\nYeas 3 Nays 1 Abstaining 1\nYeas: Senators: Bedford, Butler, and Callahan -3\nNay: Senator Denton - 1\nAbstaining: Senator Dial - 1\n"""
    rollcalls, votes, passages = parse_document(text, "2001_RegularSession", "Day25", "day25.pdf")
    assert len(rollcalls) == 1
    assert rollcalls[0]["count_valid"]
    assert rollcalls[0]["motion_type"] == "final_passage"
    assert rollcalls[0]["bill_type"] == "SB"
    assert len(votes) == 5
    assert passages[0]["named_rollcall_detected"]
    assert passages[0]["matched_rollcall_same_measure"]
    assert passages[0]["audit_status"] == "matched_same_measure_count_valid"


def test_senate_header_and_line_hyphen_cleanup():
    block = "Senators: Smith,\n<<<PAGE 20>>>\nREGULAR SESSION\n245\n14th Day - April 13, 1999\nSmitherman, and Wag-\n goner"
    assert member_names(block) == ["Smith", "Smitherman", "Waggoner"]
