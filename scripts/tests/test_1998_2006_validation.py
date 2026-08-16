import pandas as pd
from validate_1998_2006_model_readiness import baseline_audit, source_statewide

def test_historical_activity_weights_conserve_each_precinct():
    _,_,weights,_=baseline_audit(source_statewide())
    assert weights.max_weight_sum_error.max()<1e-9

def test_validation_outputs_have_explicit_cycle_gates():
    gates=pd.read_csv('data/processed/elections/validation/historical_cmo_readiness_gates.csv')
    assert set(gates.cycle)=={1998,2002,2006}
    assert gates.groupby('cycle').gate.nunique().eq(7).all()
