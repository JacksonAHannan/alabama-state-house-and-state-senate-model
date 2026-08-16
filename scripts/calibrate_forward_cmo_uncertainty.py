"""Evaluate expanding-window conformal uncertainty for prospective CMO errors."""
from pathlib import Path
import numpy as np
import pandas as pd
from fit_preliminary_war_model import prepare, estimator

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"data"/"processed"/"war"
CORE=["dem_incumbent_i","rep_incumbent_i","prior_pres_dem_margin","nonwhite_share",
      "white_college_share","prior_pres_swing","pres_trend_available"]

def conformal_radius(errors,coverage):
    values=np.sort(np.asarray(errors,float)); n=len(values)
    rank=min(n-1,int(np.ceil((n+1)*coverage))-1)
    return float(values[rank])

def main():
    source=pd.read_csv(ROOT/"data"/"processed"/"elections"/"canonical_cmo_features.csv")
    data=prepare(source); features=CORE+["cycle","chamber"]
    predictions=[]; cycles=sorted(data.cycle.unique())
    for position in range(1,len(cycles)):
        train=data[data.cycle.isin(cycles[:position])]; test=data[data.cycle.eq(cycles[position])].copy()
        model=estimator(CORE,["cycle","chamber"]); model.fit(train[features],train.raw_overperformance)
        test["expected_overperformance"]=model.predict(test[features])
        test["forecast_error"]=test.raw_overperformance-test.expected_overperformance
        test["absolute_error"]=test.forecast_error.abs(); predictions.append(test)
    errors=pd.concat(predictions,ignore_index=True)
    cols=["cycle","chamber","district","raw_overperformance","expected_overperformance","forecast_error","absolute_error"]
    errors[cols].to_csv(OUT/"cmo_forward_prediction_errors.csv",index=False)
    rows=[]
    for test_cycle in cycles[2:]:
        calibration=errors[errors.cycle.lt(test_cycle)].absolute_error; test=errors[errors.cycle.eq(test_cycle)]
        for nominal in (.80,.95):
            radius=conformal_radius(calibration,nominal)
            rows.append({"test_cycle":test_cycle,"nominal_coverage":nominal,
                         "calibration_races":len(calibration),"test_races":len(test),
                         "interval_radius":radius,"empirical_coverage":test.absolute_error.le(radius).mean(),
                         "method":"expanding_window_split_conformal"})
    summary=pd.DataFrame(rows); summary.to_csv(OUT/"cmo_forward_interval_calibration.csv",index=False)
    print(summary.to_string(index=False))

if __name__=="__main__": main()
