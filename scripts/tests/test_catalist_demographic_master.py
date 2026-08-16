from scripts.build_catalist_demographic_master import (
    add_historical_rows,
    group_dimension,
    normalize_header,
    parse_workbook,
)


def test_header_and_group_normalization():
    assert normalize_header("CD\n2022") == ("us_house", 2022)
    assert normalize_header("Pres 2024") == ("president", 2024)
    assert normalize_header("2024") is None
    assert group_dimension("White Non-College") == "intersectional"
    assert group_dimension("18-29") == "age"


def test_workbook_contains_core_current_series():
    frame = parse_workbook()
    row = frame[(frame.year == 2022) & (frame.election_type == "us_house") & (frame.group == "Black")]
    assert len(row) == 1
    assert abs(row.iloc[0].value - 88.11) < 1e-9


def test_historical_chart_backfills_2010_without_overlap():
    frame = add_historical_rows(parse_workbook())
    row = frame[(frame.year == 2010) & (frame.election_type == "us_house") & (frame.group == "White Non-College")]
    assert len(row) == 1
    assert row.iloc[0].value == 38.5
