import pandas as pd

from analyze_canonical_baselines import clean_vtd, definitions


def test_clean_vtd_normalizes_equivalent_identifiers():
    assert clean_vtd("123") == "000123"
    assert clean_vtd("123.0") == "000123"
    assert clean_vtd(123) == "000123"


def test_expanded_baseline_excludes_uncontested_office():
    office = pd.DataFrame([
        {"scenario":"strict_consensus","cycle":2022,"chamber":"house","district":1,
         "office":"Governor","D":40.0,"R":60.0,"two_party_votes":100.0,"office_margin":-20.0},
        {"scenario":"strict_consensus","cycle":2022,"chamber":"house","district":1,
         "office":"State Treasurer","D":None,"R":None,"two_party_votes":100.0,"office_margin":None},
    ])
    result = definitions(office)
    expanded = result.loc[result.baseline_definition.eq("expanded_equal"), "baseline_margin"].iloc[0]
    weighted = result.loc[result.baseline_definition.eq("expanded_turnout_weighted"), "baseline_margin"].iloc[0]
    assert expanded == -20.0
    assert weighted == -20.0
