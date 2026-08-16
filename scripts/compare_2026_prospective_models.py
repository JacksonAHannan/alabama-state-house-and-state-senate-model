"""Compare prospective benchmarks across eras, chambers, and finance variants."""
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score
from fit_preliminary_war_model import prepare,estimator

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"data"/"processed"/"war"
CORE=["dem_incumbent_i","rep_incumbent_i","prior_pres_dem_margin","nonwhite_share",
      "white_college_share","prior_pres_swing","pres_trend_available"]
SPECS={
    "presidential_only":["prior_pres_dem_margin"],
    "presidential_incumbency":["prior_pres_dem_margin","dem_incumbent_i","rep_incumbent_i"],
    "core_nonfinance":CORE,
    "core_ftm_fundraising":CORE+["log_fundraising_ratio_d_to_r","ftm_finance_complete"],
    "core_transaction_expenditures":CORE+["log_spending_ratio_d_to_r","finance_complete"],
}

def metrics(y,pred):
    return {"mae":mean_absolute_error(y,pred),"rmse":mean_squared_error(y,pred)**.5,
            "r2":r2_score(y,pred) if len(y)>1 else np.nan}

def fit_predict(train,test,columns):
    model=estimator(columns,["cycle","chamber"]); features=columns+["cycle","chamber"]
    model.fit(train[features],train.legislative_dem_margin)
    return model.predict(test[features])

def main():
    data=prepare(pd.read_csv(ROOT/"data"/"processed"/"elections"/"canonical_cmo_features.csv"))
    cycles=sorted(data.cycle.unique()); rows=[]; predictions=[]
    for test_cycle in cycles[1:]:
        for start_cycle in cycles:
            train=data[(data.cycle.ge(start_cycle))&(data.cycle.lt(test_cycle))]
            test=data[data.cycle.eq(test_cycle)]
            if train.empty: continue
            for scope in ("all","house","senate"):
                train_scope=train if scope=="all" else train[train.chamber.eq(scope)]
                test_scope=test if scope=="all" else test[test.chamber.eq(scope)]
                if len(train_scope)<10 or test_scope.empty: continue
                # Transparent direct presidential benchmark uses no fitted data.
                direct=test_scope.prior_pres_dem_margin
                if direct.notna().all():
                    result={"specification":"direct_prior_presidential","train_start":start_cycle,
                            "test_cycle":test_cycle,"scope":scope,"train_races":len(train_scope),"test_races":len(test_scope),**metrics(test_scope.legislative_dem_margin,direct)}
                    rows.append(result)
                # Chamber-offset benchmark estimates the historical legislative
                # margin premium over the prior presidential margin.
                usable=train_scope.dropna(subset=["prior_pres_dem_margin"])
                if len(usable):
                    offsets=usable.assign(offset=usable.legislative_dem_margin-usable.prior_pres_dem_margin).groupby("chamber").offset.mean()
                    pred=test_scope.prior_pres_dem_margin+test_scope.chamber.map(offsets).fillna(usable.legislative_dem_margin.sub(usable.prior_pres_dem_margin).mean())
                    if pred.notna().all(): rows.append({"specification":"chamber_uniform_offset","train_start":start_cycle,
                        "test_cycle":test_cycle,"scope":scope,"train_races":len(train_scope),"test_races":len(test_scope),**metrics(test_scope.legislative_dem_margin,pred)})
                for name,columns in SPECS.items():
                    pred=fit_predict(train_scope,test_scope,columns)
                    rows.append({"specification":name,"train_start":start_cycle,"test_cycle":test_cycle,
                                 "scope":scope,"train_races":len(train_scope),"test_races":len(test_scope),
                                 **metrics(test_scope.legislative_dem_margin,pred)})
                    predictions.extend({"specification":name,"train_start":start_cycle,"test_cycle":test_cycle,
                        "scope":scope,"chamber":race.chamber,"district":race.district,"actual_margin":race.legislative_dem_margin,
                        "predicted_margin":value,"error":race.legislative_dem_margin-value}
                        for race,value in zip(test_scope.itertuples(index=False),pred))
    detail=pd.DataFrame(rows); detail.to_csv(OUT/"2026_model_era_sensitivity.csv",index=False)
    pd.DataFrame(predictions).to_csv(OUT/"2026_model_era_predictions.csv",index=False)
    primary=detail[(detail.scope.eq("all"))&(detail.train_start.eq(2010))]
    summary=(primary.groupby("specification",as_index=False)
             .agg(forward_cycles=("test_cycle","nunique"),mean_mae=("mae","mean"),latest_mae=("mae","last"),
                  mean_rmse=("rmse","mean"),mean_r2=("r2","mean")).sort_values("mean_mae"))
    common=(primary[primary.test_cycle.isin([2018,2022])].groupby("specification",as_index=False)
            .agg(common_2018_2022_mae=("mae","mean"),common_2018_2022_rmse=("rmse","mean")))
    summary=summary.merge(common,on="specification",how="left").sort_values("common_2018_2022_mae")
    summary.to_csv(OUT/"2026_model_benchmark_summary.csv",index=False)
    print(summary.to_string(index=False))
    print(f"\nSensitivity cells: {len(detail)}")

if __name__=="__main__": main()
