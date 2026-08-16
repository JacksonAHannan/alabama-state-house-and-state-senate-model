import pandas as pd

from build_yougov_demographic_polling import parse_sheet, election_snapshots


def fixture():
    return pd.DataFrame([
        ["question", "2024-10-20", "2024-10-27"],
        ["The Democratic Party candidate", .48, .50],
        ["The Republican Party candidate", .44, .40],
        ["Unweighted base", 500, 600],
    ])


def test_parse_sheet_calculates_two_party_margin():
    result = parse_sheet(fixture(), "US Registered Voters")
    assert round(result.iloc[0].dem_margin_two_party, 6) == round(100 * .04 / .92, 6)
    assert result.iloc[1].unweighted_base == 600


def test_snapshot_uses_latest_available_waves():
    long = parse_sheet(fixture(), "US Registered Voters")
    result = election_snapshots(long, waves=1)
    row = result[result.cycle.eq(2024)].iloc[0]
    assert row.last_wave == "2024-10-27"
    assert row.waves == 1
