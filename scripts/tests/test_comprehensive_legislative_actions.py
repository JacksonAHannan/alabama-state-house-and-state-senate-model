from scripts.build_comprehensive_legislative_actions import amendment_author


def test_amendment_author_parsing():
    assert amendment_author("House Smith first Amendment Offered") == "Smith"
    assert amendment_author("Senate Jones Substitute Offered") == "Jones"


def test_committee_is_not_person():
    assert amendment_author("House Committee Amendment Offered") == ""
