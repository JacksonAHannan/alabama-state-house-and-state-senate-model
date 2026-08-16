import numpy as np
import pandas as pd
from compare_expanded_cycle_cmo_models import prepare

def test_prepare_unifies_historical_and_current_presidential_context():
    frame=pd.DataFrame({
        'war_eligible':[True,True,True],'cycle':[1998,2014,2018],
        'dem_incumbent':[False]*3,'rep_incumbent':[False]*3,
        'prior_pres_dem_margin':[2,np.nan,np.nan],
        'pres_2012_dem_margin':[np.nan,4,np.nan],
        'pres_2016_dem_margin':[np.nan,np.nan,6],
        'pres_2020_dem_margin':[np.nan]*3,
    })
    assert prepare(frame).prior_pres_dem_margin.tolist()==[2,4,6]

def test_prepare_keeps_only_contested_two_party_races():
    frame=pd.DataFrame({'war_eligible':[True,False],'cycle':[1998,1998],
        'dem_incumbent':[False]*2,'rep_incumbent':[False]*2})
    assert len(prepare(frame))==1

def test_prepare_does_not_treat_false_string_as_incumbent():
    frame=pd.DataFrame({'war_eligible':[True],'cycle':[1998],
        'dem_incumbent':['False'],'rep_incumbent':['0']})
    result=prepare(frame)
    assert result.dem_incumbent_i.iloc[0]==0
    assert result.rep_incumbent_i.iloc[0]==0
