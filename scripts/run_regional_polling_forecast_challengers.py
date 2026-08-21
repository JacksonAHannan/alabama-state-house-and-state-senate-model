"""Test A-rated final generic-ballot environments in the legislative forecast."""
from __future__ import annotations

from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import geopandas as gpd
from sklearn.linear_model import Ridge
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from run_forecast_experiment_tournament import prepare_data, cycle_balanced_weights
from analyze_white_area_voting_effects import precinct_sources

ROOT=Path(__file__).resolve().parents[1]
WAR=ROOT/"data"/"processed"/"war"
POLL=ROOT/"data"/"processed"/"polling"
DOC=ROOT/"project_docs"/"model"/"REGIONAL_POLLING_CHALLENGERS.md"
FEATURES=["dem_incumbent_i","rep_incumbent_i","finance_ratio_capped","ftm_finance_complete",
          "nonwhite_share","white_college_share","prior_pres_swing_filled","trend_available"]


def model() -> Pipeline:
    return Pipeline([("impute",SimpleImputer(strategy="median",add_indicator=True)),
                     ("scale",StandardScaler()),("ridge",Ridge(alpha=20.0))])


def prepare() -> pd.DataFrame:
    data=prepare_data(); polls=pd.read_csv(POLL/"historical_silver_a_generic_ballot_cycles.csv")
    data=data.merge(polls[["cycle","poll_implied_national_swing","poll_error","a_rated_pollsters"]],
                    on="cycle",how="inner",validate="many_to_one")
    data["poll_weight_post2016"]=np.select([data.cycle.ge(2022),data.cycle.ge(2018)],[1,.5],default=0)
    data["poll_weight_full"]=1.0
    data["poll_weight_two_step"]=np.select([data.cycle.ge(2018),data.cycle.ge(2010)],[1,.5],default=0)
    data["poll_post2016_baseline"]=data.prior_pres_dem_margin+data.poll_weight_post2016*data.poll_implied_national_swing
    data["poll_full_baseline"]=data.prior_pres_dem_margin+data.poll_implied_national_swing
    data["poll_two_step_baseline"]=data.prior_pres_dem_margin+data.poll_weight_two_step*data.poll_implied_national_swing
    data["oracle_post2016_baseline"]=data.prior_pres_dem_margin+data.national_environment_weight*data.national_environment_swing
    data["poll_ramp_swing"]=data.poll_weight_post2016*data.poll_implied_national_swing
    data["poll_x_nonwhite"]=data.poll_ramp_swing*data.nonwhite_share
    data["poll_x_white_college"]=data.poll_ramp_swing*data.white_college_share
    return data


def evaluate(data: pd.DataFrame) -> pd.DataFrame:
    specs={
        "prior_presidential":("prior_pres_dem_margin",False),
        "oracle_post2016_environment":("oracle_post2016_baseline",False),
        "a_poll_full_transfer":("poll_full_baseline",False),
        "a_poll_two_step_transfer":("poll_two_step_baseline",False),
        "a_poll_post2016_ramp":("poll_post2016_baseline",False),
        "a_poll_post2016_ramp_plus_20pct_ridge":("poll_post2016_baseline",True),
    }
    rows=[]; cycles=sorted(data.cycle.unique())
    for cycle in cycles[1:]:
        train_all=data[data.cycle.lt(cycle)]; test_all=data[data.cycle.eq(cycle)]
        for name,(baseline,use_ridge) in specs.items():
            train=train_all.dropna(subset=[baseline,"legislative_dem_margin"])
            test=test_all.dropna(subset=[baseline,"legislative_dem_margin"])
            prediction=test[baseline].to_numpy(copy=True)
            if use_ridge:
                features=FEATURES+["poll_x_nonwhite","poll_x_white_college"]
                fit=model(); target=train.legislative_dem_margin-train[baseline]
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    fit.fit(train[features],target,ridge__sample_weight=cycle_balanced_weights(train))
                prediction += .20*fit.predict(test[features])
            for race,pred in zip(test.itertuples(),prediction):
                rows.append({"test_cycle":cycle,"chamber":race.chamber,"district":race.district,
                             "specification":name,"actual":race.legislative_dem_margin,"prediction":pred,
                             "error":race.legislative_dem_margin-pred})
    out=pd.DataFrame(rows); out["absolute_error"]=out.error.abs(); return out


def summarize(detail: pd.DataFrame) -> pd.DataFrame:
    cycle=detail.groupby(["specification","test_cycle"],as_index=False).absolute_error.mean().rename(columns={"absolute_error":"mae"})
    benchmark=cycle[cycle.specification.eq("oracle_post2016_environment")].set_index("test_cycle").mae
    rows=[]
    for name,g in cycle.groupby("specification"):
        delta=g.mae-g.test_cycle.map(benchmark)
        rows.append({"specification":name,"forward_cycles":len(g),"cycle_balanced_mae":g.mae.mean(),
                     "delta_vs_oracle_environment":delta.mean(),"post2016_mae":g[g.test_cycle.ge(2018)].mae.mean(),
                     "latest_2022_mae":g[g.test_cycle.eq(2022)].mae.iloc[0],"cycles_better_than_oracle":int(delta.lt(0).sum()),
                     "worst_delta_vs_oracle":delta.max()})
    return pd.DataFrame(rows).sort_values("cycle_balanced_mae"),cycle


def regional_2022_test(detail: pd.DataFrame) -> tuple[pd.DataFrame,pd.DataFrame]:
    """Transfer only pre-2022 precinct regional residuals into 2022 districts."""
    panel=pd.read_csv(WAR/"regional_white_voting_precinct_panel.csv")
    trends=pd.read_csv(WAR/"regional_white_voting_cycle_trends.csv")
    prior=trends[trends.cycle.lt(2022)]
    effects=(prior.groupby("region").apply(
        lambda g: np.average(g.adjusted_dem_residual,weights=g.two_party_votes),include_groups=False)
        .clip(-.08,.08).mul(100).to_dict())
    geo=precinct_sources()[2022][0].reset_index(names="precinct_id").to_crs(5070)
    demo=panel[panel.cycle.eq(2022)][["precinct_id","region","adult25_total"]]
    geo=geo.merge(demo,on="precinct_id",validate="one_to_one")
    points=geo[["precinct_id","region","adult25_total","geometry"]].copy()
    points.geometry=points.geometry.representative_point()
    map_dir=ROOT/"data"/"raw"/"alabama_elections_and_geography"
    rows=[]
    for chamber,file,column in [("house","al_sldl_2021_to_2023.zip","DISTRICT"),
                                ("senate","al_sldu_2021_to_2023.zip","DISTRICT")]:
        districts=gpd.read_file(f"zip://{(map_dir/file).resolve()}")[[column,"geometry"]].to_crs(5070)
        joined=gpd.sjoin(points,districts,how="inner",predicate="within")
        joined["district"]=pd.to_numeric(joined[column])
        joined["effect"]=joined.region.map(effects).fillna(0)
        for district,g in joined.groupby("district"):
            rows.append({"chamber":chamber,"district":district,
                         "regional_adjustment_full":np.average(g.effect,weights=g.adult25_total),
                         "named_region_share":np.average(g.region.ne("Other Alabama"),weights=g.adult25_total)})
    shares=pd.DataFrame(rows)
    outputs=[]
    base_mae={}
    for base_name,label in [("a_poll_post2016_ramp","poll_ramp"),
                            ("a_poll_post2016_ramp_plus_20pct_ridge","poll_ridge")]:
        base=detail[(detail.test_cycle.eq(2022)) & detail.specification.eq(base_name)].merge(
            shares,on=["chamber","district"],validate="one_to_one")
        base_mae[label]=np.mean(np.abs(base.actual-base.prediction))
        for blend in [.25,.5,1.0]:
            x=base.copy(); x["regional_blend"]=blend; x["base_label"]=label
            x["specification"]=f"{label}_plus_regional_{int(blend*100)}"
            x["regional_adjustment"]=blend*x.regional_adjustment_full
            x["prediction"]=x.prediction+x.regional_adjustment
            x["absolute_error"]=(x.actual-x.prediction).abs(); outputs.append(x)
    result=pd.concat(outputs,ignore_index=True)
    summary=(result.groupby("specification",as_index=False).agg(
        mae=("absolute_error","mean"),max_abs_adjustment=("regional_adjustment",lambda x:x.abs().max()),
        mean_abs_adjustment=("regional_adjustment",lambda x:x.abs().mean())))
    summary["base_mae"]=summary.specification.str.extract(r"^(poll_ramp|poll_ridge)")[0].map(base_mae)
    summary["mae_gain_vs_base"]=summary.base_mae-summary.mae
    return result,summary


def write_report(summary: pd.DataFrame, regional: pd.DataFrame) -> None:
    table=["| Specification | Mean MAE | 2018–22 MAE | 2022 MAE | Delta vs oracle |","|---|---:|---:|---:|---:|"]+[
        f"| {r.specification} | {r.cycle_balanced_mae:.2f} | {r.post2016_mae:.2f} | {r.latest_2022_mae:.2f} | {r.delta_vs_oracle_environment:+.2f} |" for r in summary.itertuples()]
    polls=pd.read_csv(POLL/"historical_silver_a_generic_ballot_cycles.csv")
    current=pd.read_csv(POLL/"historical_silver_a_current_2026.csv")
    ptable=["| Cycle | Pollsters | Final A-rated margin | Actual House margin | Error |","|---:|---:|---:|---:|---:|"]+[
        f"| {int(r.cycle)} | {int(r.a_rated_pollsters)} | {r.final_poll_margin:+.2f} | {r.actual_house_margin:+.2f} | {r.poll_error:+.2f} |" for r in polls.itertuples()]
    rtable=["| Regional challenger | 2022 MAE | Gain vs polling ridge | Largest adjustment |","|---|---:|---:|---:|"]+[
        f"| {r.specification} | {r.mae:.2f} | {r.mae_gain_vs_base:+.2f} | {r.max_abs_adjustment:.2f} |" for r in regional.itertuples()]
    text=["# Regional and polling forecast challengers","","## Final A-rated generic ballots","",
          "Pollsters are screened using the current Nate Silver grades in the repository; A+, A, and A- qualify. The final nonpartisan poll from each qualifying pollster within 21 days of Election Day is retained, then pollsters are averaged equally. This is a survivorship-conditioned research series, not a historically contemporaneous rating screen.","",*ptable,"",
          f"The provisional 2026 A-rated-only snapshot is D+{current.dem_two_party_margin.mean():.2f} across {len(current)} pollsters through {pd.to_datetime(current.end_date).max().date()}. It is not a final-cycle estimate and is older than the broader B+-rated environment feed.","",
          "## Legislative backtest","",*table,"","The oracle comparator uses the eventual national House environment and is unavailable prospectively. A polling challenger that approaches it without using election results is operationally preferable even when its raw MAE is slightly higher.","",
          "## Regional transfer test","",*rtable,"","The 2022 regional test estimates effects only from 2018 and 2020 precinct results, caps them at eight points, maps precinct representative points into legislative districts, and then tests partial blends. It is a one-cycle confirmation and therefore cannot by itself select a production weight."]
    DOC.write_text("\n".join(text)+"\n",encoding="utf-8")


def main() -> None:
    data=prepare(); detail=evaluate(data); summary,cycle=summarize(detail)
    regional_detail,regional_summary=regional_2022_test(detail)
    detail.to_csv(WAR/"regional_polling_challenger_predictions.csv",index=False)
    cycle.to_csv(WAR/"regional_polling_challenger_cycle_metrics.csv",index=False)
    summary.to_csv(WAR/"regional_polling_challenger_summary.csv",index=False)
    regional_detail.to_csv(WAR/"regional_polling_challenger_regional_2022_predictions.csv",index=False)
    regional_summary.to_csv(WAR/"regional_polling_challenger_regional_2022_summary.csv",index=False)
    write_report(summary,regional_summary); print(summary.to_string(index=False)); print("\n",regional_summary.to_string(index=False))


if __name__=="__main__": main()
