import pandas as pd

from scripts.build_alabama_legislative_ideology import bill_type, election_cycle


def test_election_cycle_groups_odd_year_with_following_even_year():
    values = election_cycle(pd.Series([2010, 2011, 2012, 2025, 2026]))
    assert values.tolist() == [2010, 2012, 2012, 2026, 2026]


def test_bill_type_distinguishes_bills_from_resolutions():
    assert bill_type("HB40") == "HB"
    assert bill_type("SJR 2") == "SJR"
