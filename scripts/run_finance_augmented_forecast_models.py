"""Stack conservative finance adjustments onto safe forecast challengers."""
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT=Path(__file__).resolve().parents[1]; WAR=ROOT/"data/processed/war"; SEED=20260817
BASES=["public_80_20_total_ridge","stable_bayesian_blend_25","stable_bayesian_cap_1"]

def finance_features(cycles):
    c=pd.read_csv(WAR/"candidate_finance_matches.csv")
    c=c[c.cycle.isin(cycles)&c.party.isin(["D","R"])].copy()
    c["matched"]=~c.finance_match_method.eq("unmatched")
    amount=c.pivot(index=["cycle","chamber","district"],columns="party",values="candidate_expenditures")
    matched=c.pivot(index=["cycle","chamber","district"],columns="party",values="matched")
    out=amount.rename(columns={"D":"dem_spending","R":"rep_spending"}).reset_index()
    out["dem_matched"]=matched.D.reindex(amount.index).eq(True).to_numpy(int)
    out["rep_matched"]=matched.R.reindex(amount.index).eq(True).to_numpy(int)
    for scale in (10_000,50_000,100_000):
        out[f"log_gap_{scale//1000}k"]=np.log1p(out.dem_spending/scale)-np.log1p(out.rep_spending/scale)
    return out

def model(alpha):
    return Pipeline([("impute",SimpleImputer(strategy="median")),("scale",StandardScaler()),("model",Ridge(alpha=alpha))])

def specification(base,scale,alpha,blend,cap):
    return f"{base}__finance_log{scale}__a{alpha}__b{blend:g}__cap{cap}"

def evaluate():
    base=pd.read_csv(WAR/"forecast_challenger_predictions.csv")
    base=base[base.specification.isin(BASES)&base.test_cycle.isin([2014,2018,2022])]
    finance=finance_features([2014,2018,2022]).rename(columns={"cycle":"test_cycle"})
    panel=base.merge(finance,on=["test_cycle","chamber","district"],how="inner",validate="many_to_one")
    rows=[]
    for test_cycle in (2018,2022):
        for base_name in BASES:
            train=panel[(panel.specification.eq(base_name))&panel.test_cycle.lt(test_cycle)].copy()
            test=panel[(panel.specification.eq(base_name))&panel.test_cycle.eq(test_cycle)].copy()
            for scale in (10,50,100):
                features=[f"log_gap_{scale}k","dem_matched","rep_matched"]
                for alpha in (5,20,100):
                    fitted=model(alpha).fit(train[features],train.actual-train.prediction)
                    raw=fitted.predict(test[features])
                    for blend in (.10,.25,.50):
                        for cap in (1,2,4):
                            adjustment=np.clip(blend*raw,-cap,cap); prediction=test.prediction.to_numpy()+adjustment
                            name=specification(base_name,scale,alpha,blend,cap)
                            for race,pred,adj in zip(test.itertuples(),prediction,adjustment):
                                rows.append({"specification":name,"base_model":base_name,"test_cycle":test_cycle,
                                    "chamber":race.chamber,"district":race.district,"actual":race.actual,
                                    "base_prediction":race.prediction,"finance_adjustment":adj,"prediction":pred,
                                    "absolute_error":abs(race.actual-pred)})
    return panel,pd.DataFrame(rows)

def prospective(panel,summary):
    base=pd.read_csv(WAR/"forecast_challenger_2026_comparison.csv")
    base=base[base.specification.isin(BASES)].copy(); base["cycle"]=2026
    finance=finance_features([2026]); test=base.merge(finance,on=["cycle","chamber","district"],validate="many_to_one")
    rows=[]
    for spec in summary.specification:
        parts=spec.split("__");base_name=parts[0];scale=int(parts[1].replace("finance_log",""));alpha=int(parts[2][1:]);blend=float(parts[3][1:]);cap=float(parts[4].replace("cap",""))
        train=panel[panel.specification.eq(base_name)];features=[f"log_gap_{scale}k","dem_matched","rep_matched"]
        fitted=model(alpha).fit(train[features],train.actual-train.prediction)
        use=test[test.specification.eq(base_name)].copy();adjust=np.clip(blend*fitted.predict(use[features]),-cap,cap)
        use["finance_adjustment"]=adjust;use["predicted_dem_margin"]=use.predicted_dem_margin+adjust
        use["combined_specification"]=spec;rows.append(use)
    return pd.concat(rows,ignore_index=True)

def main():
    panel,pred=evaluate();cycle=pred.groupby(["specification","base_model","test_cycle"],as_index=False).absolute_error.mean()
    summary=cycle.groupby(["specification","base_model"],as_index=False).agg(mean_mae=("absolute_error","mean"),latest_mae=("absolute_error","last"),worst_mae=("absolute_error","max"))
    base_errors=(panel[panel.test_cycle.isin([2018,2022])].assign(ae=lambda x:(x.actual-x.prediction).abs())
                 .groupby(["specification","test_cycle"]).ae.mean())
    summary["base_mean_mae"]=[base_errors.loc[row.base_model].mean() for row in summary.itertuples()]
    summary["base_latest_mae"]=[base_errors.loc[(row.base_model,2022)] for row in summary.itertuples()]
    summary["mean_delta_vs_base"]=summary.mean_mae-summary.base_mean_mae;summary["latest_delta_vs_base"]=summary.latest_mae-summary.base_latest_mae
    prospective_rows=prospective(panel,summary)
    prospective_rows["total_change_vs_public"]=prospective_rows.predicted_dem_margin-prospective_rows.public_margin
    prospective_rows["winner_changed_vs_public"]=(prospective_rows.predicted_dem_margin.ge(0)!=prospective_rows.public_margin.ge(0))
    audit=(prospective_rows.groupby("combined_specification",as_index=False).agg(
        max_finance_adjustment=("finance_adjustment",lambda x:x.abs().max()),
        mean_finance_adjustment=("finance_adjustment","mean"),
        max_total_change_vs_public=("total_change_vs_public",lambda x:x.abs().max()),
        winner_changes_vs_public=("winner_changed_vs_public","sum")))
    sd2=prospective_rows[(prospective_rows.chamber.eq("senate"))&prospective_rows.district.eq(2)][["combined_specification","predicted_dem_margin"]].rename(columns={"predicted_dem_margin":"sd2_margin"})
    summary=summary.merge(audit,left_on="specification",right_on="combined_specification").merge(sd2,on="combined_specification").drop(columns="combined_specification")
    summary["improves_both_holdouts"]=summary.mean_delta_vs_base.lt(0)&summary.latest_delta_vs_base.lt(0)
    summary["prospective_safe"]=(summary.sd2_margin.ge(0)&summary.max_finance_adjustment.le(2)
                                  &summary.max_total_change_vs_public.le(4)
                                  &summary.winner_changes_vs_public.eq(0))
    summary=summary.sort_values(["improves_both_holdouts","prospective_safe","mean_mae"],ascending=[False,False,True])
    panel.to_csv(WAR/"forecast_challenger_finance_stack_panel.csv",index=False);pred.to_csv(WAR/"forecast_challenger_finance_stack_predictions.csv",index=False)
    summary.to_csv(WAR/"forecast_challenger_finance_stack_summary.csv",index=False);prospective_rows.to_csv(WAR/"forecast_challenger_finance_stack_2026.csv",index=False)
    print(summary.head(25).round(3).to_string(index=False))

if __name__=="__main__":main()
