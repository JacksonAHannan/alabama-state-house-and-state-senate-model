import pandas as pd


def test_survivorship_outputs_distinguish_raw_and_residual_performance():
    status = pd.read_csv("research/cmo_ideology/incumbency_survivorship/incumbent_nonincumbent_comparison.csv")
    tests = pd.read_csv("research/cmo_ideology/incumbency_survivorship/survivorship_diagnostic_tests.csv")
    assert set(status.incumbent) == {0, 1}
    assert {"raw_mean", "residual_cmo_mean"}.issubset(status.columns)
    assert tests.comparison.str.contains("within_person").sum() == 2
