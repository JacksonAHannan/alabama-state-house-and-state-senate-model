"""Test finance transforms on the adopted definitive zero-policy panel."""
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from run_forecast_experiment_tournament import prepare_data

ROOT=Path(__file__).resolve().parents[1]; WAR=ROOT/"data/processed/war"

def panel():
    c=pd.read_csv(WAR/"candidate_finance_matches.csv")
    c=c[c.cycle.isin([2014,2018,2022])&c.party.isin(["D","R"])].copy()
    c["matched"]=~c.finance_match_method.eq("unmatched")
    amount=c.pivot(index=["cycle","chamber","district"],columns="party",values="candidate_expenditures")
    matched=c.pivot(index=["cycle","chamber","district"],columns="party",values="matched")
    out=amount.rename(columns={"D":"dem_spending","R":"rep_spending"}).reset_index()
    out["dem_matched"]=matched.D.reindex(amount.index).eq(True).to_numpy(int)
    out["rep_matched"]=matched.R.reindex(amount.index).eq(True).to_numpy(int)
    for scale in (10_000,50_000,100_000):
        out[f"log_gap_{scale//1000}k"]=np.log1p(out.dem_spending/scale)-np.log1p(out.rep_spending/scale)
    out["sqrt_gap"]=(np.sqrt(out.dem_spending)-np.sqrt(out.rep_spending))/np.sqrt(50_000)
    result=prepare_data().merge(out,on=["cycle","chamber","district"],how="inner",validate="one_to_one")
    return result.dropna(subset=["legislative_dem_margin","ramp_baseline"])

def main():
    data=panel(); predictions=[]
    specs={"ramp_only":[],"spend_log10":["log_gap_10k","dem_matched","rep_matched"],
           "spend_log50":["log_gap_50k","dem_matched","rep_matched"],
           "spend_log100":["log_gap_100k","dem_matched","rep_matched"],
           "spend_sqrt":["sqrt_gap","dem_matched","rep_matched"]}
    for cycle in (2018,2022):
        train=data[data.cycle.lt(cycle)]; test=data[data.cycle.eq(cycle)]
        for name,features in specs.items():
            variants=[("none",0,0)] if not features else [(f"a{a}_b{b}",a,b) for a in (5,20,100) for b in (.25,.5,1)]
            for suffix,alpha,blend in variants:
                margin=test.ramp_baseline.to_numpy(copy=True)
                if features:
                    model=Pipeline([("impute",SimpleImputer(strategy="median")),("scale",StandardScaler()),("model",Ridge(alpha=alpha))])
                    model.fit(train[features],train.legislative_dem_margin-train.ramp_baseline)
                    margin+=blend*model.predict(test[features])
                spec=name if suffix=="none" else f"{name}_{suffix}"
                predictions.extend({"specification":spec,"test_cycle":cycle,"chamber":race.chamber,
                    "district":race.district,"actual":race.legislative_dem_margin,"prediction":value,
                    "absolute_error":abs(race.legislative_dem_margin-value)} for race,value in zip(test.itertuples(),margin))
    predictions=pd.DataFrame(predictions)
    cycle=predictions.groupby(["specification","test_cycle"],as_index=False).absolute_error.mean()
    summary=cycle.groupby("specification",as_index=False).agg(mean_mae=("absolute_error","mean"),latest_mae=("absolute_error","last"),worst_mae=("absolute_error","max"))
    base=summary.set_index("specification").loc["ramp_only"]
    summary["mean_delta_vs_ramp"]=summary.mean_mae-base.mean_mae; summary["latest_delta_vs_ramp"]=summary.latest_mae-base.latest_mae
    coverage=(pd.read_csv(WAR/"candidate_finance_coverage.csv").query("cycle in [2014,2018,2022]")
              .assign(coverage_definition="candidate_name_matched_to_definitive_finance_source"))
    data.to_csv(WAR/"forecast_challenger_finance_panel.csv",index=False)
    predictions.to_csv(WAR/"forecast_challenger_finance_predictions.csv",index=False)
    summary.sort_values("mean_mae").to_csv(WAR/"forecast_challenger_finance_summary.csv",index=False)
    coverage.to_csv(WAR/"forecast_challenger_finance_coverage.csv",index=False)
    print(coverage.to_string(index=False)); print("\n"+summary.sort_values("mean_mae").head(12).round(3).to_string(index=False))

if __name__=="__main__": main()
