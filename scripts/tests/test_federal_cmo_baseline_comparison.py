import pandas as pd
from compare_federal_cmo_baselines import metrics

def test_metrics_reports_signed_observed_minus_prediction_error():
    got=metrics(pd.Series([2.,4.]),pd.Series([1.,2.]))
    assert got['mae']==1.5 and got['mean_error']==1.5
