"""Run staged forecast challengers with a deliberately simple guardrail model."""
from __future__ import annotations

from pathlib import Path
import re
import warnings

import geopandas as gpd
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from analyze_white_area_voting_effects import precinct_sources
from run_forecast_experiment_tournament import prepare_data, prepare_prospective_data, cycle_balanced_weights

ROOT=Path(__file__).resolve().parents[1]
WAR=ROOT/"data"/"processed"/"war"; POLL=ROOT/"data"/"processed"/"polling"
DOC=ROOT/"project_docs"/"model"/"NEXT_FORECAST_TOURNAMENTS.md"
SEED=20260817


def apply_canonical_historical_finance(data: pd.DataFrame) -> pd.DataFrame:
    """Replace legacy/FTM finance fields with the source-prioritized mart."""
    finance=pd.read_csv(WAR/"canonical_historical_finance_races.csv")[[
        "cycle","chamber","district","canonical_finance_complete",
        "canonical_log_fundraising_ratio_d_to_r"]]
    data=data.merge(finance,on=["cycle","chamber","district"],how="left",validate="one_to_one")
    data["finance_ratio_capped"]=pd.to_numeric(
        data.canonical_log_fundraising_ratio_d_to_r,errors="coerce").clip(-3,3)
    data["ftm_finance_complete"]=data.canonical_finance_complete.fillna(0).astype(int)
    return data


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+","_",value.lower()).strip("_")


def region_shares() -> pd.DataFrame:
    panel=pd.read_csv(WAR/"regional_white_voting_precinct_panel.csv")
    map_dir=ROOT/"data"/"raw"/"alabama_elections_and_geography"
    configurations={
        2018:(2018,"al_sldl_2017_to_2021.zip","SLDLST","al_sldu_2017_to_2021.zip","SLDUST"),
        2022:(2022,"al_sldl_2021_to_2023.zip","DISTRICT","al_sldu_2021_to_2023.zip","DISTRICT"),
        2026:(2024,"tl_2025_01_sldl.zip","SLDLST","tl_2025_01_sldu.zip","SLDUST"),
    }
    rows=[]
    for cycle,(source_cycle,hfile,hcol,sfile,scol) in configurations.items():
        geo=precinct_sources()[source_cycle][0].reset_index(names="precinct_id").to_crs(5070)
        demo=panel[panel.cycle.eq(source_cycle)][["precinct_id","region","adult25_total"]]
        points=geo.merge(demo,on="precinct_id",validate="one_to_one")[["region","adult25_total","geometry"]]
        points.geometry=points.geometry.representative_point()
        for chamber,file,column in [("house",hfile,hcol),("senate",sfile,scol)]:
            districts=gpd.read_file(f"zip://{(map_dir/file).resolve()}")[[column,"geometry"]].to_crs(5070)
            joined=gpd.sjoin(points,districts,how="inner",predicate="within")
            joined["district"]=pd.to_numeric(joined[column])
            totals=joined.groupby("district").adult25_total.sum()
            wide=joined.pivot_table(index="district",columns="region",values="adult25_total",aggfunc="sum",fill_value=0)
            wide=wide.div(totals,axis=0)
            for district,r in wide.iterrows():
                item={"cycle":cycle,"chamber":chamber,"district":district,"regional_features_available":1}
                for region,value in r.items(): item[f"region_{slug(region)}_share"]=value
                rows.append(item)
    out=pd.DataFrame(rows).fillna(0)
    out.to_csv(WAR/"next_forecast_tournament_region_features.csv",index=False)
    return out


def pipeline(alpha: float) -> Pipeline:
    return Pipeline([("impute",SimpleImputer(strategy="median",add_indicator=True)),
                     ("scale",StandardScaler()),("ridge",Ridge(alpha=alpha))])


def prepare_panel(regions: pd.DataFrame) -> tuple[pd.DataFrame,list[str]]:
    data=apply_canonical_historical_finance(prepare_data())
    polls=pd.read_csv(POLL/"historical_silver_a_generic_ballot_cycles.csv")
    data=data.merge(polls[["cycle","poll_implied_national_swing"]],on="cycle",how="inner",validate="many_to_one")
    data["poll_transfer_weight"]=np.select([data.cycle.ge(2022),data.cycle.ge(2018)],[1,.5],default=0)
    data["basic_polling_baseline"]=data.prior_pres_dem_margin+data.poll_transfer_weight*data.poll_implied_national_swing
    data["poll_swing_transferred"]=data.poll_transfer_weight*data.poll_implied_national_swing
    data["poll_x_nonwhite"]=data.poll_swing_transferred*data.nonwhite_share
    data["poll_x_white_college"]=data.poll_swing_transferred*data.white_college_share
    data["chamber_house"]=data.chamber.eq("house").astype(int)
    data=data.merge(regions[regions.cycle.ne(2026)],on=["cycle","chamber","district"],how="left",validate="one_to_one")
    region_cols=sorted(c for c in regions if c.startswith("region_") and c.endswith("_share"))
    data[region_cols]=data[region_cols].fillna(0); data["regional_features_available"]=data.regional_features_available.fillna(0)
    return data,region_cols


def feature_stages(region_cols: list[str]) -> dict[str,list[str]]:
    demo=["nonwhite_share","white_college_share","poll_x_nonwhite","poll_x_white_college","chamber_house"]
    region=demo+region_cols+["regional_features_available"]
    finance=region+["finance_ratio_capped","ftm_finance_complete"]
    incumbency=finance+["dem_incumbent_i","rep_incumbent_i","open_seat"]
    history=incumbency+["dem_prior_recent","rep_prior_recent","dem_prior_winner","rep_prior_winner",
                        "dem_prior_candidate_overperformance","rep_prior_candidate_overperformance"]
    return {"demographics":demo,"demographics_regions":region,"demographics_regions_finance":finance,
            "demographics_regions_finance_incumbency":incumbency,"all_plus_candidate_history":history}


def evaluate(data: pd.DataFrame,stages: dict[str,list[str]]) -> pd.DataFrame:
    specs={"basic_polling_100":{"features":[],"alpha":None,"blend":0}}
    for stage,features in stages.items():
        for alpha in (20.,100.):
            for blend in (.10,.20):
                specs[f"{stage}__ridge{int(alpha)}__blend{int(blend*100)}"]={"features":features,"alpha":alpha,"blend":blend}
    rows=[]; cycles=sorted(data.cycle.unique())
    for cycle in cycles[1:]:
        train=data[data.cycle.lt(cycle)].dropna(subset=["basic_polling_baseline","legislative_dem_margin"])
        test=data[data.cycle.eq(cycle)].dropna(subset=["basic_polling_baseline","legislative_dem_margin"])
        for name,spec in specs.items():
            adjustment=np.zeros(len(test))
            if spec["features"]:
                fit=pipeline(spec["alpha"]); target=train.legislative_dem_margin-train.basic_polling_baseline
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    fit.fit(train[spec["features"]],target,ridge__sample_weight=cycle_balanced_weights(train))
                adjustment=(spec["blend"]*fit.predict(test[spec["features"]])).clip(-4,4)
            pred=test.basic_polling_baseline.to_numpy()+adjustment
            for race,p,a in zip(test.itertuples(),pred,adjustment):
                rows.append({"test_cycle":cycle,"chamber":race.chamber,"district":race.district,
                             "specification":name,"actual":race.legislative_dem_margin,"prediction":p,
                             "adjustment":a,"absolute_error":abs(race.legislative_dem_margin-p)})
    return pd.DataFrame(rows)


def summarize(detail: pd.DataFrame) -> tuple[pd.DataFrame,pd.DataFrame]:
    cycle=detail.groupby(["specification","test_cycle"],as_index=False).absolute_error.mean().rename(columns={"absolute_error":"mae"})
    base=cycle[cycle.specification.eq("basic_polling_100")].set_index("test_cycle").mae
    rows=[]
    rng=np.random.default_rng(SEED)
    for name,g in cycle.groupby("specification"):
        g=g.sort_values("test_cycle")
        delta=g.mae-g.test_cycle.map(base); recent=g[g.test_cycle.ge(2018)]
        boot=np.array([rng.choice(delta.to_numpy(),size=len(delta),replace=True).mean() for _ in range(20000)])
        delta_low,delta_high=np.quantile(boot,[.025,.975])
        complexity=0 if name.startswith("basic") else name.count("_")+1
        passes=(name!="basic_polling_100" and delta.mean()<=-.25 and
                (recent.mae-recent.test_cycle.map(base)).mean()<=-.10 and
                delta.iloc[-1]<=-.10 and delta.lt(0).sum()>=4 and delta.max()<=1 and delta_high<0)
        rows.append({"specification":name,"cycle_balanced_mae":g.mae.mean(),"delta_vs_basic":delta.mean(),
                     "delta_bootstrap_low":delta_low,"delta_bootstrap_high":delta_high,
                     "post2016_mae":recent.mae.mean(),"latest_2022_mae":g.iloc[-1].mae,
                     "cycles_improved":int(delta.lt(0).sum()),"worst_cycle_delta":delta.max(),
                     "complexity_proxy":complexity,"passes_basic_guardrail":passes})
    return pd.DataFrame(rows).sort_values(["cycle_balanced_mae","complexity_proxy"]),cycle


def past_only_selector(cycle: pd.DataFrame) -> pd.DataFrame:
    """Evaluate a selector that can use only tournaments completed before each cycle."""
    rows=[]; cycles=sorted(cycle.test_cycle.unique())
    for i,test_cycle in enumerate(cycles):
        candidates=cycle[cycle.test_cycle.lt(test_cycle)]
        selected="basic_polling_100"
        reason="fewer than two prior held-out cycles"
        if i>=2:
            means=candidates.groupby("specification").mae.mean().sort_values()
            challenger=means.index[0]
            improvement=means["basic_polling_100"]-means[challenger]
            if challenger!="basic_polling_100" and improvement>=.25:
                selected=challenger; reason=f"prior-cycle mean improvement {improvement:.2f}"
            else:
                reason=f"no challenger cleared 0.25-point prior-cycle threshold ({improvement:.2f})"
        observed=cycle[(cycle.test_cycle.eq(test_cycle)) & (cycle.specification.eq(selected))].iloc[0]
        basic=cycle[(cycle.test_cycle.eq(test_cycle)) & (cycle.specification.eq("basic_polling_100"))].iloc[0]
        rows.append({"test_cycle":test_cycle,"selected_specification":selected,"selection_reason":reason,
                     "selected_mae":observed.mae,"basic_mae":basic.mae,"delta_vs_basic":observed.mae-basic.mae})
    return pd.DataFrame(rows)


def prospective(data: pd.DataFrame,regions: pd.DataFrame,stages: dict[str,list[str]],summary: pd.DataFrame) -> pd.DataFrame:
    p=prepare_prospective_data(); p["chamber_house"]=p.chamber.eq("house").astype(int)
    p["poll_swing_transferred"]=p.national_environment_swing
    p["poll_x_nonwhite"]=p.poll_swing_transferred*p.nonwhite_share
    p["poll_x_white_college"]=p.poll_swing_transferred*p.white_college_share
    p=p.merge(regions[regions.cycle.eq(2026)].drop(columns="cycle"),on=["chamber","district"],how="left",validate="one_to_one")
    region_cols=[c for c in regions if c.startswith("region_") and c.endswith("_share")]
    p[region_cols]=p[region_cols].fillna(0); p["regional_features_available"]=p.regional_features_available.fillna(0)
    history=pd.read_csv(WAR/"2026_candidate_prior_cmo_scenario.csv")
    incumbency=pd.read_csv(WAR/"2026_candidate_incumbency.csv")
    history=history.merge(incumbency[["chamber","district","party","candidate","incumbent"]],
                          on=["chamber","district","party","candidate"],how="left",validate="one_to_one")
    party_history={}
    for party,prefix in [("D","dem"),("R","rep")]:
        h=(history[history.party.eq(party)].sort_values(["chamber","district","priority"])
           .drop_duplicates(["chamber","district"])[["chamber","district","prior_cmo_shrunk","prior_cmo_races","incumbent"]]
           .rename(columns={"prior_cmo_shrunk":f"{prefix}_prior_candidate_overperformance",
                            "prior_cmo_races":f"{prefix}_prior_recent","incumbent":f"{prefix}_prior_winner"}))
        h[f"{prefix}_prior_recent"]=(h[f"{prefix}_prior_recent"].fillna(0)>0).astype(int)
        h[f"{prefix}_prior_winner"]=h[f"{prefix}_prior_winner"].fillna(False).astype(int)
        party_history[party]=h
    p=(p.merge(party_history["D"],on=["chamber","district"],how="left",validate="one_to_one")
         .merge(party_history["R"],on=["chamber","district"],how="left",validate="one_to_one"))
    history_cols=["dem_prior_recent","rep_prior_recent","dem_prior_winner","rep_prior_winner",
                  "dem_prior_candidate_overperformance","rep_prior_candidate_overperformance"]
    p[history_cols]=p[history_cols].fillna(0)
    swing=float(p.national_environment_swing.iloc[0]); structural=p.pres_2024_dem_margin
    outputs=[]
    for weight,label in [(.75,"basic_75_conservative"),(1.,"basic_polling_100"),(1.25,"basic_125_continued_nationalization")]:
        for row,margin in zip(p.itertuples(),structural+weight*swing):
            outputs.append({"chamber":row.chamber,"district":row.district,"specification":label,
                            "predicted_dem_margin":margin,"adjustment_vs_basic_100":(weight-1)*swing})
    # Fundamentals+ is the fullest best-performing staged challenger. It is
    # intentionally published as a comparison view despite failing the basic
    # model's latest-cycle promotion guardrail.
    full_name="all_plus_candidate_history__ridge20__blend20"
    features=stages["all_plus_candidate_history"]
    train=data.dropna(subset=["legislative_dem_margin","basic_polling_baseline"]).copy()
    fit=pipeline(20.); target=train.legislative_dem_margin-train.basic_polling_baseline
    fit.fit(train[features],target,ridge__sample_weight=cycle_balanced_weights(train))
    adj=(.20*fit.predict(p[features])).clip(-4,4)
    for row,margin,a in zip(p.itertuples(),structural+swing+adj,adj):
        outputs.append({"chamber":row.chamber,"district":row.district,"specification":full_name,
                        "predicted_dem_margin":margin,"adjustment_vs_basic_100":a})
    eligible=summary[summary.passes_basic_guardrail]
    for name in eligible.specification:
        stage=name.split("__")[0]; alpha=float(name.split("ridge")[1].split("__")[0]); blend=float(name.split("blend")[1])/100
        features=stages[stage]
        if stage=="all_plus_candidate_history": continue
        fit=pipeline(alpha); target=data.legislative_dem_margin-data.basic_polling_baseline
        fit.fit(data[features],target,ridge__sample_weight=cycle_balanced_weights(data))
        adj=(blend*fit.predict(p[features])).clip(-4,4)
        for row,margin,a in zip(p.itertuples(),structural+swing+adj,adj):
            outputs.append({"chamber":row.chamber,"district":row.district,"specification":name,
                            "predicted_dem_margin":margin,"adjustment_vs_basic_100":a})
    return pd.DataFrame(outputs)


def report(summary: pd.DataFrame,prospective_df: pd.DataFrame,selector: pd.DataFrame) -> None:
    top=summary.head(12)
    table=["| Specification | Mean MAE | Delta vs basic | 95% cycle-bootstrap delta | 2018-22 | 2022 | Cycles improved | Gate |","|---|---:|---:|---:|---:|---:|---:|---|"]+[
        f"| {r.specification} | {r.cycle_balanced_mae:.2f} | {r.delta_vs_basic:+.2f} | [{r.delta_bootstrap_low:+.2f}, {r.delta_bootstrap_high:+.2f}] | {r.post2016_mae:.2f} | {r.latest_2022_mae:.2f} | {int(r.cycles_improved)} | {'pass' if r.passes_basic_guardrail else 'fail'} |" for r in top.itertuples()]
    scenarios=prospective_df[prospective_df.specification.str.startswith("basic")].groupby("specification").adjustment_vs_basic_100.first()
    text=["# Next forecast tournaments","","## Basic-model guardrail","",
          "The benchmark is deliberately simple: prior district presidential margin plus the final A-rated national generic-ballot swing under the supported post-2016 transfer rule. A complex model must improve mean MAE by at least 0.25 points, recent MAE by 0.10, 2022 by 0.10, at least four of six cycles, never lose by more than one point in a cycle, and have a cycle-bootstrap 95% upper bound below zero.","",*table,"",
          "## Past-only selection audit","",f"A selector restricted to earlier held-out cycles produced mean MAE {selector.selected_mae.mean():.2f}, versus {selector.basic_mae.mean():.2f} for always using the basic model. It selected the basic model in {selector.selected_specification.eq('basic_polling_100').sum()} of {len(selector)} cycles.","",
          "## 2026 basic views","",f"The 75% view is {scenarios['basic_75_conservative']:+.2f} points from default. The continued-nationalization 125% view is {scenarios['basic_125_continued_nationalization']:+.2f} points from default. The 125% view is explicitly untestable and cannot win the statistical tournament.","",
          "Regional variables are fitted jointly and shrunk in the tournament. Candidate-history specifications are historical research only until an equivalent 2026 feature build is available."]
    DOC.write_text("\n".join(text)+"\n",encoding="utf-8")


def main() -> None:
    regions=region_shares(); data,region_cols=prepare_panel(regions); stages=feature_stages(region_cols)
    detail=evaluate(data,stages); summary,cycle=summarize(detail); selector=past_only_selector(cycle); pro=prospective(data,regions,stages,summary)
    detail.to_csv(WAR/"next_forecast_tournament_predictions.csv",index=False)
    cycle.to_csv(WAR/"next_forecast_tournament_cycle_metrics.csv",index=False)
    summary.to_csv(WAR/"next_forecast_tournament_summary.csv",index=False)
    selector.to_csv(WAR/"next_forecast_tournament_past_only_selection.csv",index=False)
    pro.to_csv(WAR/"next_forecast_tournament_2026.csv",index=False)
    report(summary,pro,selector); print(summary.head(15).to_string(index=False)); print("\nPast-only selector\n",selector.to_string(index=False)); print("\n2026 specs",pro.specification.value_counts().to_dict())


if __name__=="__main__": main()
