from build_candidate_issue_valence_v3 import rating_value


def test_rating_value_parses_percent_and_grades():
    assert rating_value("100%") == 1
    assert rating_value("50%") == 0
    assert rating_value("0%") == -1
    assert rating_value("A") > 0
    assert rating_value("F") == -1
    assert rating_value("unknown") is None
